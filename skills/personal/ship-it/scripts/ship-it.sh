#!/usr/bin/env bash
# ship-it: snapshot each vertical slice without committing, then turn the
# snapshots into one commit per slice once the human has approved the work.
#
# Nothing here commits, stages, stashes or touches the working tree until
# `commit` is run. Snapshots are tree objects built with a throwaway index and
# kept alive by refs under refs/ship-it/<session>/, so the branch and the real
# index stay exactly as they were while the work is being built and reviewed.
# `commit` builds the commits in a temporary worktree whose files match each
# slice, so hooks check the slice itself, and moves the branch only once every
# slice has committed.
#
#   ship-it.sh start [--allow-dirty] [--plain]
#                                         begin a session on the current branch;
#                                         --plain checks headers without the
#                                         Conventional Commits format
#   ship-it.sh plan -                     save the approved plan (stdin)
#   ship-it.sh decision -                 append a decision to the log (stdin)
#   ship-it.sh recall                     print the plan, decisions and slices
#   ship-it.sh checkpoint <n> -           snapshot the working tree as slice n,
#                                         commit message on stdin (or a file
#                                         path outside the repo)
#   ship-it.sh msg <n> -                  replace slice n's commit message
#   ship-it.sh fold <n>                   fold changes made since the last
#                                         snapshot into slice n (and every
#                                         slice after it)
#   ship-it.sh status                     what is not yet in any slice
#   ship-it.sh list                       slices, headers and sizes
#   ship-it.sh diff <n>|all [git args]    one slice's own diff, or the lot
#   ship-it.sh commit                     one commit per slice, all or nothing
#   ship-it.sh abort                      forget the session, keep the files
#
# Written for bash 3.2 (the macOS default) and up.

set -euo pipefail

die() { printf 'ship-it: %s\n' "$*" >&2; exit 1; }
note() { printf 'ship-it: %s\n' "$*" >&2; }

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git work tree"
CALLER_DIR=$PWD
TOP=$(git rev-parse --show-toplevel)
cd "$TOP"
STATE=$(git rev-parse --git-path ship-it)
case "$STATE" in /*) ;; *) STATE="$TOP/$STATE" ;; esac

TYPES='feat|fix|chore|refactor|test|docs|perf|build|ci|style|revert'
COMMIT_DIR=''

# Temporary files carry this process's id, so an interrupted run never leaves
# them behind and never touches another run's files.
cleanup() {
	rm -f "$STATE"/*."$$"
	if [ -n "$COMMIT_DIR" ]; then
		git worktree remove --force "$COMMIT_DIR/wt" >/dev/null 2>&1 || :
		rm -rf "$COMMIT_DIR"
		git worktree prune
	fi
}
trap cleanup EXIT

pad() { printf '%04d' "$1"; }
is_num() { case "${1:-}" in '' | *[!0-9]*) return 1 ;; *) return 0 ;; esac; }
require_state() { [ -f "$STATE/base" ] || die "no ship-it session here; run: ship-it.sh start"; }
count() { cat "$STATE/count"; }
tree_of() { cat "$STATE/slices/$(pad "$1").tree"; }
msg_of() { printf '%s' "$STATE/slices/$(pad "$1").msg"; }
header_of() { head -n 1 "$(msg_of "$1")"; }
session_refs() { printf 'refs/ship-it/%s' "$(cat "$STATE/id")"; }
current_branch() { git symbolic-ref -q --short HEAD || printf '(detached)'; }

# Snapshots are only meaningful against the commit and branch they started on.
position_problem() {
	local branch
	branch=$(cat "$STATE/branch")
	if [ "$(current_branch)" != "$branch" ]; then
		printf "the session belongs to branch '%s' but '%s' is checked out; switch back first" "$branch" "$(current_branch)"
	elif [ "$(git rev-parse HEAD)" != "$(cat "$STATE/base")" ]; then
		printf 'HEAD has moved since the session started (a commit, reset or checkout); put it back at %s first' "$(git rev-parse --short "$(cat "$STATE/base")")"
	fi
}

require_position() {
	local problem
	problem=$(position_problem)
	[ -z "$problem" ] || die "$problem"
}

# Tree object for the working tree as it is right now: tracked edits,
# deletions and untracked files, minus anything .gitignore excludes.
worktree_tree() {
	local idx="$STATE/tmp-index.$$"
	# A fresh index makes git read every file. A copy of the real index would
	# be faster, but the copy's new timestamp hides edits made in the same
	# second as the last index write.
	GIT_INDEX_FILE="$idx" git read-tree HEAD &&
		GIT_INDEX_FILE="$idx" git add -A &&
		GIT_INDEX_FILE="$idx" git write-tree &&
		rm -f "$idx"
}

# Keep a snapshot tree reachable so `git gc` never prunes it.
protect() {
	local n=$1 tree=$2 c
	c=$(git commit-tree "$tree" -m "ship-it snapshot $(pad "$n")")
	git update-ref "$(session_refs)/slice-$(pad "$n")" "$c"
}

store_slice() {
	printf '%s\n' "$2" >"$STATE/slices/$(pad "$1").tree"
	protect "$1" "$2"
}

# Messages arrive on stdin ("-") or from a file outside the repo; a file
# inside the work tree would be swept into the snapshot itself.
read_message() {
	local src=$1 dest="$STATE/incoming.msg.$$"
	if [ "$src" = "-" ]; then
		cat >"$dest"
	else
		case "$src" in /*) ;; *) src="$CALLER_DIR/$src" ;; esac
		[ -f "$src" ] || die "commit message file '$src' does not exist"
		case "$(cd "$(dirname "$src")" && pwd -P)/" in
		"$(pwd -P)"/*) die "keep the message file outside the repo (or pipe it on stdin with '-'); '$src' would end up in the slice" ;;
		esac
		cp "$src" "$dest"
	fi
	check_message "$dest"
}

check_message() {
	local file=$1 header re desc
	[ -s "$file" ] || die "the commit message is empty"
	header=$(head -n 1 "$file")
	[ -n "$header" ] || die "the first line of the commit message is empty"
	if [ "$(cat "$STATE/style")" = conventional ]; then
		re="^($TYPES)(\([^)]+\))?!?: .+"
		[[ $header =~ $re ]] || die "header '$header' is not a conventional commit (type(scope): description, type one of: ${TYPES//|/, }); start the session with --plain if this repo does not use Conventional Commits"
		desc=${header#*: }
		case "$desc" in [A-Z][a-z]*) note "warning: description starts with a capital; the style is lowercase imperative" ;; esac
	fi
	[ ${#header} -le 72 ] || note "warning: header is ${#header} characters; aim for 72 or fewer"
	case "$header" in *.) note "warning: header ends with a full stop" ;; esac
	if [ "$(wc -l <"$file" | tr -d ' ')" -gt 1 ] && [ -n "$(sed -n 2p "$file")" ]; then
		note "warning: leave line 2 blank between the header and the body"
	fi
}

cmd_start() {
	local allow_dirty=0 style=conventional
	while [ $# -gt 0 ]; do
		case "$1" in
		--allow-dirty) allow_dirty=1 ;;
		--plain) style=plain ;;
		*) die "unknown option '$1'; usage: ship-it.sh start [--allow-dirty] [--plain]" ;;
		esac
		shift
	done
	if [ -f "$STATE/base" ]; then
		die "a session already exists with $(count) slice(s); see 'ship-it.sh recall', or 'ship-it.sh abort' to discard it"
	fi
	git rev-parse --verify -q HEAD >/dev/null || die "the repository has no commits yet; make an initial commit first"
	if [ -n "$(git status --porcelain)" ] && [ "$allow_dirty" -eq 0 ]; then
		git status --short >&2
		die "the working tree already has uncommitted changes; they would be swept into slice 1. Commit or stash them first, or pass --allow-dirty if they belong to this work"
	fi
	mkdir -p "$STATE/slices"
	# Worktrees share refs, so each session keeps its snapshots under its own id.
	printf '%s %s %s\n' "$STATE" "$(date +%s)" "$$" | git hash-object --stdin | cut -c1-12 >"$STATE/id"
	git rev-parse HEAD >"$STATE/base"
	printf '%s\n' "$(current_branch)" >"$STATE/branch"
	printf '%s\n' "$style" >"$STATE/style"
	printf '0\n' >"$STATE/count"
	store_slice 0 "$(git rev-parse 'HEAD^{tree}')"
	note "session started on $(cat "$STATE/branch") at $(git rev-parse --short HEAD)"
}

cmd_plan() {
	require_state
	[ "${1:-}" = "-" ] || die "usage: ship-it.sh plan - (the plan on stdin)"
	cat >"$STATE/plan.md"
	note "plan saved; 'ship-it.sh recall' prints it"
}

cmd_decision() {
	require_state
	[ "${1:-}" = "-" ] || die "usage: ship-it.sh decision - (the decision on stdin)"
	{
		printf -- '- '
		cat
	} >>"$STATE/decisions.md"
}

cmd_recall() {
	require_state
	printf '## Plan\n\n'
	if [ -s "$STATE/plan.md" ]; then cat "$STATE/plan.md"; else printf 'No plan saved.\n'; fi
	printf '\n## Decisions\n\n'
	if [ -s "$STATE/decisions.md" ]; then cat "$STATE/decisions.md"; else printf 'None recorded.\n'; fi
	printf '\n## Slices\n\n'
	cmd_list
}

cmd_checkpoint() {
	require_state
	require_position
	local n=${1:-} file=${2:-} c tree prev
	is_num "$n" && [ "$n" -ge 1 ] || die "usage: ship-it.sh checkpoint <slice-number> -"
	n=$((10#$n))
	c=$(count)
	if [ "$n" -eq $((c + 1)) ]; then
		:
	elif [ "$n" -eq "$c" ]; then
		note "re-snapshotting slice $n"
	else
		die "the next slice is $((c + 1)); to change slice $n after later slices exist, make the edit and run 'ship-it.sh fold $n'"
	fi
	read_message "$file"
	tree=$(worktree_tree)
	prev=$(tree_of $((n - 1)))
	[ "$tree" != "$prev" ] || die "no changes since slice $((n - 1)); nothing to snapshot"
	mv "$STATE/incoming.msg.$$" "$(msg_of "$n")"
	store_slice "$n" "$tree"
	printf '%s\n' "$n" >"$STATE/count"
	printf 'slice %s: %s\n' "$n" "$(header_of "$n")"
	git --no-pager diff --stat "$prev" "$tree"
	local added
	added=$(git diff --name-only --diff-filter=A "$prev" "$tree")
	if [ -n "$added" ]; then
		printf 'new files in this slice (check none are stray):\n'
		printf '%s\n' "$added" | sed 's/^/  /'
	fi
}

cmd_msg() {
	require_state
	local n=${1:-} file=${2:-}
	is_num "$n" || die "usage: ship-it.sh msg <slice-number> -"
	n=$((10#$n))
	[ "$n" -ge 1 ] && [ "$n" -le "$(count)" ] || die "there is no slice $n"
	read_message "$file"
	mv "$STATE/incoming.msg.$$" "$(msg_of "$n")"
	printf 'slice %s: %s\n' "$n" "$(header_of "$n")"
}

cmd_status() {
	require_state
	local c cur last problem
	c=$(count)
	problem=$(position_problem)
	[ -z "$problem" ] || note "warning: $problem"
	cur=$(worktree_tree)
	last=$(tree_of "$c")
	if [ "$cur" = "$last" ]; then
		printf 'working tree matches slice %s; nothing outside a slice\n' "$c"
	else
		printf 'changes not yet in any slice (checkpoint them as the next slice, or fold them into an earlier one):\n'
		git --no-pager diff --stat "$last" "$cur"
	fi
}

cmd_list() {
	require_state
	local c i
	c=$(count)
	printf 'branch %s, base %s, %s slice(s)\n' "$(cat "$STATE/branch")" "$(git rev-parse --short "$(cat "$STATE/base")")" "$c"
	i=1
	while [ "$i" -le "$c" ]; do
		printf '%4s  %-72s %s\n' "$i" "$(header_of "$i")" "$(git diff --shortstat "$(tree_of $((i - 1)))" "$(tree_of "$i")" | sed 's/^ *//')"
		i=$((i + 1))
	done
}

cmd_diff() {
	require_state
	local n=${1:-}
	[ -n "$n" ] || die "usage: ship-it.sh diff <slice-number>|all [git diff options]"
	shift
	if [ "$n" = "all" ]; then
		git --no-pager diff "$@" "$(tree_of 0)" "$(tree_of "$(count)")"
		return
	fi
	is_num "$n" || die "usage: ship-it.sh diff <slice-number>|all [git diff options]"
	n=$((10#$n))
	[ "$n" -ge 1 ] && [ "$n" -le "$(count)" ] || die "there is no slice $n"
	git --no-pager diff "$@" "$(tree_of $((n - 1)))" "$(tree_of "$n")"
}

cmd_fold() {
	require_state
	require_position
	local n=${1:-} c last cur patch trees idx j t newt prevt
	is_num "$n" || die "usage: ship-it.sh fold <slice-number>"
	n=$((10#$n))
	c=$(count)
	[ "$n" -ge 1 ] && [ "$n" -le "$c" ] || die "there is no slice $n"
	last=$(tree_of "$c")
	cur=$(worktree_tree)
	[ "$cur" != "$last" ] || die "nothing to fold; the working tree matches slice $c"
	patch="$STATE/fold.patch.$$"
	trees="$STATE/fold.trees.$$"
	idx="$STATE/fold-index.$$"
	git diff --binary "$last" "$cur" >"$patch"
	: >"$trees"
	prevt=$(tree_of $((n - 1)))
	j=$n
	while [ "$j" -le "$c" ]; do
		rm -f "$idx"
		GIT_INDEX_FILE="$idx" git read-tree "$(tree_of "$j")"
		if ! GIT_INDEX_FILE="$idx" git apply --cached --whitespace=nowarn "$patch" 2>"$STATE/fold.err.$$"; then
			cat "$STATE/fold.err.$$" >&2
			if [ "$j" -eq "$n" ]; then
				die "the change does not apply cleanly to slice $n (it touches code a later slice changed); fold it into a later slice instead, or into slice $c"
			fi
			die "the change applies to slice $n but not to slice $j; fold it into slice $j or later instead"
		fi
		newt=$(GIT_INDEX_FILE="$idx" git write-tree)
		[ "$newt" != "$prevt" ] || die "folding into slice $n would leave slice $j with no changes of its own, which cannot be committed; nothing changed. Fold into another slice, or abort and start again with a new plan"
		printf '%s %s\n' "$j" "$newt" >>"$trees"
		prevt=$newt
		j=$((j + 1))
	done
	[ "$newt" = "$cur" ] || die "folding would not reproduce the working tree exactly; nothing changed. Fold into slice $c instead"
	while read -r j t; do store_slice "$j" "$t"; done <"$trees"
	printf 'folded into slice %s (and carried through slice %s)\n' "$n" "$c"
}

# Hooks run inside the temporary worktree, so a relative hooks path (such as
# husky's `.husky/_`, which git does not track) must point back to this one.
hooks_dir() {
	local dir
	dir=$(git rev-parse --git-path hooks)
	case "$dir" in /*) printf '%s' "$dir" ;; *) printf '%s/%s' "$TOP" "$dir" ;; esac
}

cmd_commit() {
	require_state
	require_position
	local c base branch cur last hooks wt i t got patch tip
	c=$(count)
	[ "$c" -ge 1 ] || die "there are no slices to commit"
	base=$(cat "$STATE/base")
	branch=$(cat "$STATE/branch")
	cur=$(worktree_tree)
	last=$(tree_of "$c")
	if [ "$cur" != "$last" ]; then
		git --no-pager diff --stat "$last" "$cur" >&2
		die "the working tree has changes that are not in any slice; checkpoint or fold them first, so what was reviewed is what gets committed"
	fi
	hooks=$(hooks_dir)
	COMMIT_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ship-it.XXXXXX")
	wt="$COMMIT_DIR/wt"
	git worktree add --quiet --detach --no-checkout "$wt" "$base"
	# Hooks usually need the project's installed packages, which git does not track.
	if [ -d node_modules ]; then
		ln -s "$TOP/node_modules" "$wt/node_modules"
	fi
	i=1
	while [ "$i" -le "$c" ]; do
		t=$(tree_of "$i")
		git -C "$wt" read-tree -u --reset "$t"
		if ! git -C "$wt" -c core.hooksPath="$hooks" commit -q -F "$(msg_of "$i")"; then
			die "the commit for slice $i failed, most likely a hook rejecting it. Nothing was committed and the branch has not moved. The hooks saw slice $i exactly as it would be committed, so fix the cause, fold the fix into slice $i and run commit again"
		fi
		got=$(git -C "$wt" rev-parse 'HEAD^{tree}')
		if [ "$got" != "$t" ]; then
			patch="$STATE/hook-slice-$(pad "$i").patch"
			git diff --binary "$t" "$got" >"$patch"
			git --no-pager diff --stat "$t" "$got" >&2
			die "a hook changed the contents of slice $i while committing it. Nothing was committed and the branch has not moved. The hook's change is saved in $patch; to keep it, make the same change in the working tree, fold it into slice $i and run commit again"
		fi
		printf '%s\n' "$(git -C "$wt" log -1 --format='%h %s')"
		i=$((i + 1))
	done
	tip=$(git -C "$wt" rev-parse HEAD)
	# Passing the old value makes the update fail if the branch moved meanwhile.
	if [ "$branch" = '(detached)' ]; then
		git update-ref --no-deref -m "ship-it: commit $c slice(s)" HEAD "$tip" "$base"
	else
		git update-ref -m "ship-it: commit $c slice(s)" "refs/heads/$branch" "$tip" "$base"
	fi
	git read-tree HEAD
	# Refreshing only updates cached file stats. It exits non-zero when files
	# differ, which the status check below reports.
	git update-index -q --refresh >/dev/null || :
	if [ -n "$(git status --porcelain)" ]; then
		note "warning: git status is not clean after committing:"
		git status --short >&2
	fi
	clear_state
	note "done: $c commit(s) on $branch; nothing pushed"
}

clear_state() {
	git for-each-ref --format='%(refname)' "$(session_refs)/" | while read -r r; do git update-ref -d "$r"; done
	rm -rf "$STATE"
}

cmd_abort() {
	require_state
	clear_state
	note "session discarded; the working tree and branch are exactly as they were"
}

sub=${1:-}
[ $# -gt 0 ] && shift
case "$sub" in
start) cmd_start "$@" ;;
plan) cmd_plan "$@" ;;
decision) cmd_decision "$@" ;;
recall) cmd_recall "$@" ;;
checkpoint) cmd_checkpoint "$@" ;;
msg) cmd_msg "$@" ;;
status) cmd_status "$@" ;;
list) cmd_list "$@" ;;
diff) cmd_diff "$@" ;;
fold) cmd_fold "$@" ;;
commit) cmd_commit "$@" ;;
abort) cmd_abort "$@" ;;
*)
	awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
	exit 2
	;;
esac
