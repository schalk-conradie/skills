import { complete, type UserMessage } from "@earendil-works/pi-ai";
import {
	BorderedLoader,
	getMarkdownTheme,
	type ExtensionAPI,
	type ExtensionCommandContext,
} from "@earendil-works/pi-coding-agent";
import {
	Container,
	Input,
	Key,
	Markdown,
	matchesKey,
	truncateToWidth,
	visibleWidth,
	wrapTextWithAnsi,
	type Focusable,
	type KeybindingsManager,
	type OverlayHandle,
	type TUI,
} from "@earendil-works/pi-tui";
import { existsSync, statSync } from "node:fs";
import { readdir, readFile } from "node:fs/promises";
import { basename, isAbsolute, join, relative, resolve } from "node:path";

const EXT = "exam-study";
const DEFAULT_MAX_CONTEXT_CHARS = 70_000;
const MAX_FILES = 1200;
const MAX_QUESTIONS = 50;
const STUDY_FOCUS_SHORTCUTS = [Key.alt("s"), Key.ctrlAlt("s")] as const;

function matchesStudyFocusShortcut(data: string): boolean {
	return STUDY_FOCUS_SHORTCUTS.some((shortcut) => matchesKey(data, shortcut));
}

// ─── Types ───────────────────────────────────────────────────────────────────

type Chunk = {
	file: string;
	title: string;
	text: string;
};

type QuizQuestion = {
	id?: string;
	question: string;
	options: string[];
	correctOptionIndexes: number[];
	explanation: string;
	references?: string[];
};

type Quiz = {
	title?: string;
	questions: QuizQuestion[];
};

type QuizResult = {
	cancelled: boolean;
	submitted: boolean;
	score: number;
	total: number;
	quiz: Quiz;
	selections: number[][];
};

type TranscriptEntry =
	| { type: "user"; text: string }
	| { type: "assistant"; text: string; streaming?: boolean }
	| { type: "status"; text: string }
	| { type: "divider" };

// ─── Utility functions ────────────────────────────────────────────────────────

function expandHome(input: string): string {
	if (input === "~") return process.env.HOME || input;
	if (input.startsWith("~/")) return join(process.env.HOME || "", input.slice(2));
	return input;
}

function resolveStudyRoot(cwd: string, arg?: string): string {
	if (arg?.trim()) {
		const expanded = expandHome(arg.trim());
		return isAbsolute(expanded) ? expanded : resolve(cwd, expanded);
	}
	// Auto-detect common study folder patterns
	for (const candidate of ["microsoft-learn-ab-620", "microsoft-learn-pl-900", "microsoft-learn-pl-400"]) {
		const path = join(cwd, candidate);
		if (existsSync(path)) return path;
	}
	return cwd;
}

function tokenize(text: string): string[] {
	const stop = new Set([
		"the", "and", "or", "a", "an", "to", "of", "in", "for", "with", "by", "on", "from", "is", "are",
		"be", "as", "this", "that", "it", "you", "your", "how", "what", "when", "where", "which", "using",
	]);
	return (text.toLowerCase().match(/[a-z0-9][a-z0-9-]{2,}/g) || []).filter((w) => !stop.has(w));
}

async function collectMarkdownFiles(root: string): Promise<string[]> {
	const files: string[] = [];
	async function walk(dir: string) {
		if (files.length >= MAX_FILES) return;
		let entries;
		try {
			entries = await readdir(dir, { withFileTypes: true });
		} catch {
			return;
		}
		entries.sort((a, b) => a.name.localeCompare(b.name));
		for (const entry of entries) {
			if (files.length >= MAX_FILES) break;
			if (entry.name.startsWith(".")) continue;
			const full = join(dir, entry.name);
			if (entry.isDirectory()) {
				if (["node_modules", ".git", "metadata"].includes(entry.name)) continue;
				await walk(full);
			} else if (entry.isFile() && entry.name.toLowerCase().endsWith(".md")) {
				files.push(full);
			}
		}
	}
	await walk(root);
	return files;
}

function firstHeading(markdown: string, fallback: string): string {
	const match = markdown.match(/^#\s+(.+)$/m) || markdown.match(/^title:\s*['"]?(.+?)['"]?\s*$/m);
	return (match?.[1] || fallback).trim();
}

function splitIntoChunks(file: string, markdown: string): Chunk[] {
	const title = firstHeading(markdown, basename(file));
	const normalized = markdown.replace(/\r\n/g, "\n");
	const sections = normalized.split(/\n(?=##?##?\s+)/g);
	const chunks: Chunk[] = [];
	for (const section of sections) {
		const trimmed = section.trim();
		if (trimmed.length < 120) continue;
		if (trimmed.length <= 5000) {
			chunks.push({ file, title, text: trimmed });
			continue;
		}
		for (let i = 0; i < trimmed.length; i += 4500) {
			chunks.push({ file, title, text: trimmed.slice(i, i + 5000).trim() });
		}
	}
	return chunks;
}

async function loadCorpus(root: string): Promise<Chunk[]> {
	const files = await collectMarkdownFiles(root);
	const chunks: Chunk[] = [];
	for (const file of files) {
		try {
			const text = await readFile(file, "utf8");
			chunks.push(...splitIntoChunks(file, text));
		} catch {
			// ignore unreadable files
		}
	}
	return chunks;
}

function selectContext(root: string, chunks: Chunk[], query: string, maxChars = DEFAULT_MAX_CONTEXT_CHARS): string {
	const terms = tokenize(query);
	const termSet = new Set(terms);
	const scored = chunks.map((chunk, idx) => {
		const haystack = `${chunk.title}\n${chunk.file}\n${chunk.text}`.toLowerCase();
		let score = 0;
		for (const term of termSet) {
			const re = new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g");
			score += (haystack.match(re) || []).length;
		}
		if (chunk.file.includes("00-study-guide")) score += 8;
		if (chunk.file.includes("INDEX.md")) score += 4;
		if (score === 0 && terms.length === 0) score = Math.max(1, 20 - (idx % 20));
		return { chunk, score, idx };
	});

	scored.sort((a, b) => b.score - a.score || a.idx - b.idx);
	const selected: string[] = [];
	let total = 0;
	const usedFiles = new Set<string>();
	for (const { chunk, score } of scored) {
		if (score <= 0 && selected.length > 8) break;
		const rel = relative(root, chunk.file);
		const block = `\n\n---\nSOURCE: ${rel}\nTITLE: ${chunk.title}\n\n${chunk.text}`;
		if (total + block.length > maxChars) continue;
		selected.push(block);
		total += block.length;
		usedFiles.add(rel);
		if (total >= maxChars * 0.92) break;
	}
	return selected.join("\n");
}

async function runModel(ctx: ExtensionCommandContext, systemPrompt: string, userText: string, loadingMessage: string): Promise<string | null> {
	if (!ctx.model) {
		ctx.ui.notify("No model selected", "error");
		return null;
	}
	return await ctx.ui.custom<string | null>((tui: any, theme: any, _kb: any, done: (value: string | null) => void) => {
		const loader = new BorderedLoader(tui, theme, loadingMessage);
		loader.onAbort = () => done(null);

		const work = async () => {
			const auth = await ctx.modelRegistry.getApiKeyAndHeaders(ctx.model);
			if (!auth.ok || !auth.apiKey) throw new Error(auth.ok ? `No API key for ${ctx.model.provider}` : auth.error);
			const message: UserMessage = {
				role: "user",
				content: [{ type: "text", text: userText }],
				timestamp: Date.now(),
			};
			const response = await complete(
				ctx.model,
				{ systemPrompt, messages: [message] },
				{ apiKey: auth.apiKey, headers: auth.headers, signal: loader.signal },
			);
			if (response.stopReason === "aborted") return null;
			return response.content
				.filter((c): c is { type: "text"; text: string } => c.type === "text")
				.map((c) => c.text)
				.join("\n")
				.trim();
		};

		work().then(done).catch((err) => done(`ERROR: ${err instanceof Error ? err.message : String(err)}`));
		return loader;
	});
}

function extractJson(text: string): any {
	const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
	const candidate = fenced?.[1] || text;
	const first = candidate.indexOf("{");
	const last = candidate.lastIndexOf("}");
	if (first < 0 || last <= first) throw new Error("No JSON object found in model output");
	return JSON.parse(candidate.slice(first, last + 1));
}

function normalizeQuiz(raw: any, requestedQuestions: number, requestedOptions: number): Quiz {
	const questions = Array.isArray(raw?.questions) ? raw.questions : [];
	const normalized: QuizQuestion[] = questions.slice(0, requestedQuestions).map((q: any, i: number) => {
		const options = Array.isArray(q.options) ? q.options.map((o: any) => String(o)).slice(0, requestedOptions) : [];
		let correct = Array.isArray(q.correctOptionIndexes)
			? q.correctOptionIndexes.map((n: any) => Number(n)).filter((n: number) => Number.isInteger(n))
			: [];
		correct = Array.from(new Set(correct.filter((n) => n >= 1 && n <= options.length))).sort((a, b) => a - b);
		return {
			id: String(q.id || `Q${i + 1}`),
			question: String(q.question || q.prompt || "Untitled question"),
			options,
			correctOptionIndexes: correct,
			explanation: String(q.explanation || "No explanation provided."),
			references: Array.isArray(q.references) ? q.references.map((r: any) => String(r)) : [],
		};
	});
	return { title: String(raw?.title || "Study quiz"), questions: normalized.filter((q) => q.options.length > 1 && q.correctOptionIndexes.length > 0) };
}

function sameSelection(a: number[], b: number[]): boolean {
	const aa = [...a].sort((x, y) => x - y);
	const bb = [...b].sort((x, y) => x - y);
	return aa.length === bb.length && aa.every((v, i) => v === bb[i]);
}

function quizSummary(result: QuizResult): string {
	const lines: string[] = [];
	lines.push(`# ${result.quiz.title || "Study quiz"} results`);
	lines.push("");
	if (result.cancelled) {
		lines.push("Quiz cancelled before submission.");
		return lines.join("\n");
	}
	lines.push(`Score: **${result.score}/${result.total}**`);
	lines.push("");
	result.quiz.questions.forEach((q, i) => {
		const selected = result.selections[i] || [];
		const ok = sameSelection(selected, q.correctOptionIndexes);
		lines.push(`## ${i + 1}. ${ok ? "✓" : "✗"} ${q.question}`);
		lines.push(`- Your answer: ${selected.length ? selected.join(", ") : "(none)"}`);
		lines.push(`- Correct answer: ${q.correctOptionIndexes.join(", ")}`);
		lines.push(`- Explanation: ${q.explanation}`);
		if (q.references?.length) lines.push(`- References: ${q.references.join(", ")}`);
		lines.push("");
	});
	return lines.join("\n");
}

// ─── Overlay component ──────────────────────────────────────────────────────

function buildTranscriptBadge(
	theme: any,
	label: string,
	background: "userMessageBg" | "customMessageBg",
	foreground: "accent" | "success",
): string {
	return theme.bg(background, theme.fg(foreground, theme.bold(` ${label} `)));
}

class StudyOverlayComponent extends Container implements Focusable {
	private readonly input: Input;
	private readonly tui: TUI;
	private readonly theme: any;
	private readonly keybindings: KeybindingsManager;
	private readonly onSubmit: (value: string) => void;
	private readonly onDismiss: () => void;
	private readonly onUnfocus: () => void;
	private readonly readTranscript: () => TranscriptEntry[];
	private readonly getStatus: () => string | null;
	private readonly getStudyRoot: () => string;
	private readonly getChunkCount: () => number;

	private transcriptLines: string[] = [];
	private transcriptScrollOffset = 0;
	private transcriptViewportHeight = 8;
	private followTranscript = true;
	private _focused = false;
	private statusValue = "";
	private summaryValue = "";
	private hintsValue = "";

	get focused(): boolean {
		return this._focused;
	}

	set focused(value: boolean) {
		this._focused = value;
		this.input.focused = value;
	}

	constructor(
		tui: TUI,
		theme: any,
		keybindings: KeybindingsManager,
		readTranscript: () => TranscriptEntry[],
		getStatus: () => string | null,
		getStudyRoot: () => string,
		getChunkCount: () => number,
		onSubmit: (value: string) => void,
		onDismiss: () => void,
		onUnfocus: () => void,
	) {
		super();
		this.tui = tui;
		this.theme = theme;
		this.keybindings = keybindings;
		this.readTranscript = readTranscript;
		this.getStatus = getStatus;
		this.getStudyRoot = getStudyRoot;
		this.getChunkCount = getChunkCount;
		this.onSubmit = onSubmit;
		this.onDismiss = onDismiss;
		this.onUnfocus = onUnfocus;

		this.input = new Input();
		this.input.onSubmit = (value) => {
			this.followTranscript = true;
			this.onSubmit(value);
		};
		this.input.onEscape = () => {
			this.onDismiss();
		};

		// Hook into input to handle app-level keybindings
		const originalHandleInput = this.input.handleInput.bind(this.input);
		this.input.handleInput = (data: string) => {
			if (this.keybindings.matches(data, "app.clear")) {
				if (this.input.getValue().length > 0) {
					this.input.setValue("");
					this.tui.requestRender();
					return;
				}
				this.onDismiss();
				return;
			}
			if (this.keybindings.matches(data, "tui.select.cancel")) {
				this.onDismiss();
				return;
			}
			originalHandleInput(data);
		};

		this.refresh();
	}

	private frameLine(content: string, innerWidth: number): string {
		const truncated = truncateToWidth(content, innerWidth, "");
		const padding = Math.max(0, innerWidth - visibleWidth(truncated));
		return `${this.theme.fg("borderMuted", "│")}${truncated}${" ".repeat(padding)}${this.theme.fg("borderMuted", "│")}`;
	}

	private ruleLine(innerWidth: number): string {
		return this.theme.fg("borderMuted", `├${"─".repeat(innerWidth)}┤`);
	}

	private borderLine(innerWidth: number, edge: "top" | "bottom"): string {
		const left = edge === "top" ? "┌" : "└";
		const right = edge === "top" ? "┐" : "┘";
		return this.theme.fg("borderMuted", `${left}${"─".repeat(innerWidth)}${right}`);
	}

	private wrapTranscript(innerWidth: number): string[] {
		const wrapped: string[] = [];
		for (const line of this.transcriptLines) {
			if (!line) {
				wrapped.push("");
				continue;
			}
			wrapped.push(...wrapTextWithAnsi(line, Math.max(1, innerWidth)));
		}
		return wrapped;
	}

	private getDialogHeight(): number {
		const terminalRows = process.stdout.rows ?? 30;
		return Math.max(18, Math.min(32, Math.floor(terminalRows * 0.78)));
	}

	handleInput(data: string): void {
		if (matchesStudyFocusShortcut(data)) {
			this.onUnfocus();
			return;
		}

		if (matchesKey(data, Key.pageUp)) {
			this.followTranscript = false;
			this.transcriptScrollOffset = Math.max(0, this.transcriptScrollOffset - Math.max(1, this.transcriptViewportHeight - 1));
			this.tui.requestRender();
			return;
		}

		if (matchesKey(data, Key.pageDown)) {
			this.transcriptScrollOffset += Math.max(1, this.transcriptViewportHeight - 1);
			this.tui.requestRender();
			return;
		}

		this.input.handleInput(data);
	}

	private inputFrameLine(dialogWidth: number): string {
		const targetWidth = Math.max(1, dialogWidth - 2);
		const previousFocused = this.input.focused;
		this.input.focused = false;
		try {
			const inputLine = this.input.render(targetWidth)[0] ?? "";
			return `${this.theme.fg("borderMuted", "│")}${inputLine}${this.theme.fg("borderMuted", "│")}`;
		} finally {
			this.input.focused = previousFocused;
		}
	}

	override render(width: number): string[] {
		const dialogWidth = Math.max(24, width);
		const innerWidth = Math.max(22, dialogWidth - 2);
		const transcriptLines = this.wrapTranscript(innerWidth);
		const dialogHeight = this.getDialogHeight();
		const chromeHeight = 8;
		const transcriptHeight = Math.max(6, dialogHeight - chromeHeight);
		this.transcriptViewportHeight = transcriptHeight;

		const maxScroll = Math.max(0, transcriptLines.length - transcriptHeight);
		if (this.followTranscript) {
			this.transcriptScrollOffset = maxScroll;
		} else {
			this.transcriptScrollOffset = Math.max(0, Math.min(this.transcriptScrollOffset, maxScroll));
			if (this.transcriptScrollOffset >= maxScroll) {
				this.followTranscript = true;
			}
		}

		const visibleTranscript = transcriptLines.slice(
			this.transcriptScrollOffset,
			this.transcriptScrollOffset + transcriptHeight,
		);
		const transcriptPadCount = Math.max(0, transcriptHeight - visibleTranscript.length);
		const hiddenAbove = this.transcriptScrollOffset;
		const hiddenBelow = Math.max(0, maxScroll - this.transcriptScrollOffset);
		const summary =
			hiddenAbove || hiddenBelow
				? `${this.summaryValue.trim()} · ↑${hiddenAbove} ↓${hiddenBelow}`
				: this.summaryValue.trim();

		const lines = [this.borderLine(innerWidth, "top")];

		lines.push(this.frameLine(this.theme.fg("accent", this.theme.bold(this.statusValue.trim())), innerWidth));
		lines.push(this.frameLine(this.theme.fg("dim", summary), innerWidth));
		lines.push(this.ruleLine(innerWidth));

		for (const line of visibleTranscript) {
			lines.push(this.frameLine(line, innerWidth));
		}
		for (let i = 0; i < transcriptPadCount; i++) {
			lines.push(this.frameLine("", innerWidth));
		}

		lines.push(this.ruleLine(innerWidth));
		const status = this.getStatus() ?? "Ready. Enter submits; Escape dismisses.";
		lines.push(this.frameLine(this.theme.fg("warning", status), innerWidth));
		lines.push(this.inputFrameLine(dialogWidth));
		lines.push(this.frameLine(this.theme.fg("dim", this.hintsValue.trim()), innerWidth));
		lines.push(this.borderLine(innerWidth, "bottom"));

		return lines;
	}

	setDraft(value: string): void {
		this.input.setValue(value);
		this.tui.requestRender();
	}

	getDraft(): string {
		return this.input.getValue();
	}

	refresh(): void {
		const root = this.getStudyRoot();
		const chunks = this.getChunkCount();
		const rootLabel = root === process.env.HOME ? "~" : root.replace(process.env.HOME + "/", "~/");
		this.statusValue = `Study · ${rootLabel} · ${chunks} chunks`;

		const entries = this.readTranscript();
		const exchanges = entries.filter((e) => e.type === "assistant" && !e.streaming).length;
		const active = entries.some((e) => e.type === "assistant" && e.streaming) ? " · streaming" : " · idle";
		this.summaryValue = `${exchanges} exchange${exchanges === 1 ? "" : "s"}${active}`;

		this.hintsValue = "Enter submit · Alt+S toggle focus · Esc dismiss · PgUp/PgDn scroll · /quiz /status /clear /help";

		// Build transcript display lines
		const lines: string[] = [];
		const userBadge = buildTranscriptBadge(this.theme, "You", "userMessageBg", "accent");
		const assistantBadge = buildTranscriptBadge(this.theme, "Study", "customMessageBg", "success");

		for (const entry of entries) {
			if (entry.type === "divider") {
				if (lines.length > 0) lines.push("");
				lines.push(this.theme.fg("borderMuted", "────────────────────────────────────────"));
				continue;
			}

			if (entry.type === "status") {
				if (lines.length > 0) lines.push("");
				lines.push(this.theme.fg("dim", this.theme.italic(entry.text)));
				continue;
			}

			if (entry.type === "user") {
				if (lines.length > 0) lines.push("");
				lines.push(`${userBadge} ${entry.text}`);
				continue;
			}

			if (entry.type === "assistant") {
				if (lines.length > 0) lines.push("");
				const badge = entry.streaming ? `${assistantBadge} ${this.theme.fg("warning", "▍")}` : assistantBadge;
				lines.push(badge);
				const bodyLines = entry.text.split("\n");
				for (const bl of bodyLines) {
					lines.push(`    ${bl}`);
				}
				continue;
			}
		}

		this.transcriptLines = lines;
		this.tui.requestRender();
	}
}

// ─── Quiz overlay component ──────────────────────────────────────────────────

class QuizOverlayComponent implements Focusable {
	private quiz: Quiz;
	private theme: any;
	private tui: TUI;
	private current = 0;
	private option = 0;
	private submitted = false;
	private cachedLines: string[] | undefined;
	private selections: Set<number>[];
	public onComplete: ((result: QuizResult) => void) | null = null;
	focused = false;

	constructor(quiz: Quiz, theme: any, tui: TUI) {
		this.quiz = quiz;
		this.theme = theme;
		this.tui = tui;
		this.selections = quiz.questions.map(() => new Set<number>());
	}

	private refresh() {
		this.cachedLines = undefined;
		this.tui.requestRender();
	}

	private score(): number {
		return this.quiz.questions.reduce((sum, q, i) => sum + (sameSelection(Array.from(this.selections[i]), q.correctOptionIndexes) ? 1 : 0), 0);
	}

	private finish(cancelled: boolean) {
		this.onComplete?.({
			cancelled,
			submitted: this.submitted,
			score: this.submitted ? this.score() : 0,
			total: this.quiz.questions.length,
			quiz: this.quiz,
			selections: this.selections.map((s) => Array.from(s).sort((a, b) => a - b)),
		});
	}

	handleInput(data: string): void {
		const q = this.quiz.questions[this.current];
		if (!q) return;

		if (matchesKey(data, Key.escape) || data === "q") {
			this.finish(!this.submitted);
			return;
		}
		if (matchesKey(data, Key.left) || data === "p") {
			this.current = Math.max(0, this.current - 1);
			this.option = 0;
			this.refresh();
			return;
		}
		if (matchesKey(data, Key.right) || data === "n") {
			this.current = Math.min(this.quiz.questions.length - 1, this.current + 1);
			this.option = 0;
			this.refresh();
			return;
		}
		if (!this.submitted && (matchesKey(data, Key.up) || data === "k")) {
			this.option = Math.max(0, this.option - 1);
			this.refresh();
			return;
		}
		if (!this.submitted && (matchesKey(data, Key.down) || data === "j")) {
			this.option = Math.min(q.options.length - 1, this.option + 1);
			this.refresh();
			return;
		}
		if (!this.submitted && (matchesKey(data, Key.enter) || matchesKey(data, Key.space))) {
			const value = this.option + 1;
			const selected = this.selections[this.current];
			if (selected.has(value)) selected.delete(value);
			else selected.add(value);
			this.refresh();
			return;
		}
		if (!this.submitted && data === "s") {
			this.submitted = true;
			this.refresh();
			return;
		}
	}

	render(width: number): string[] {
		if (this.cachedLines) return this.cachedLines;
		const lines: string[] = [];
		const add = (s = "") => lines.push(truncateToWidth(s, width));
		const addWrapped = (s: string, indent = "") => {
			for (const line of wrapTextWithAnsi(s, Math.max(10, width - indent.length))) add(indent + line);
		};
		const q = this.quiz.questions[this.current];
		const selected = this.selections[this.current];
		const correct = new Set(q.correctOptionIndexes);

		add(this.theme.fg("accent", "─".repeat(width)));
		const title = this.quiz.title || "Study quiz";
		const progress = `Question ${this.current + 1}/${this.quiz.questions.length}`;
		add(this.theme.fg("accent", this.theme.bold(` ${title}`)) + this.theme.fg("dim", `  •  ${progress}`));
		if (this.submitted) add(this.theme.fg("success", ` Score: ${this.score()}/${this.quiz.questions.length}`));
		lines.push("");
		addWrapped(this.theme.fg("text", q.question), " ");
		lines.push("");

		for (let i = 0; i < q.options.length; i++) {
			const oneBased = i + 1;
			const isSelected = selected.has(oneBased);
			const isCorrect = correct.has(oneBased);
			const cursor = !this.submitted && i === this.option ? this.theme.fg("accent", ">") : " ";
			let marker = isSelected ? "[x]" : "[ ]";
			let color: "accent" | "text" | "success" | "error" | "muted" = !this.submitted && i === this.option ? "accent" : "text";
			if (this.submitted) {
				if (isCorrect) {
					marker = "[✓]";
					color = "success";
				} else if (isSelected) {
					marker = "[✗]";
					color = "error";
				} else {
					color = "muted";
				}
			}
			addWrapped(`${cursor} ${this.theme.fg(color, `${marker} ${oneBased}. ${q.options[i]}`)}`, "");
		}

		if (this.submitted) {
			lines.push("");
			const ok = sameSelection(Array.from(selected), q.correctOptionIndexes);
			add(this.theme.fg(ok ? "success" : "error", ok ? " Correct" : " Incorrect"));
			addWrapped(this.theme.fg("muted", `Explanation: ${q.explanation}`), " ");
			if (q.references?.length) addWrapped(this.theme.fg("dim", `References: ${q.references.join(", ")}`), " ");
		}

		lines.push("");
		const help = this.submitted
			? " ←/→ previous/next • q/Esc back to study"
			: " ↑↓ select • Enter/Space toggle • ←/→ previous/next • s submit • Esc back";
		add(this.theme.fg("dim", help));
		add(this.theme.fg("accent", "─".repeat(width)));
		this.cachedLines = lines;
		return lines;
	}

	invalidate(): void {
		this.cachedLines = undefined;
	}
}

// ─── Overlay runtime ─────────────────────────────────────────────────────────

type OverlayRuntime = {
	handle?: OverlayHandle;
	refresh?: () => void;
	close?: () => void;
	finish?: () => void;
	setDraft?: (value: string) => void;
	closed?: boolean;
};

// ─── Main extension ──────────────────────────────────────────────────────────

export default function examStudy(pi: ExtensionAPI) {
	// State persisted across overlay open/close
	let studyRoot = "";
	let chunks: Chunk[] = [];
	let transcript: TranscriptEntry[] = [];
	let overlayStatus: string | null = null;
	let overlayDraft = "";
	let overlayRuntime: OverlayRuntime | null = null;
	let lastCtx: ExtensionCommandContext | null = null;
	let busy = false;

	pi.registerMessageRenderer(EXT, (message, _options, _theme) => {
		return new Markdown(String(message.content || ""), 0, 0, getMarkdownTheme());
	});

	function setOverlayStatus(status: string | null, ctx?: ExtensionCommandContext): void {
		overlayStatus = status;
		syncUi(ctx);
	}

	function syncUi(ctx?: ExtensionCommandContext | null): void {
		const activeCtx = ctx ?? lastCtx;
		if (activeCtx?.hasUI) {
			activeCtx.ui.setWidget("study", undefined);
			overlayRuntime?.refresh?.();
		}
	}

	function dismissOverlay(): void {
		overlayRuntime?.close?.();
		overlayRuntime = null;
	}

	function toggleOverlayFocus(): void {
		const handle = overlayRuntime?.handle;
		if (!handle) return;
		handle.setHidden(false);
		if (handle.isFocused()) {
			handle.unfocus();
		} else {
			handle.focus();
		}
		overlayRuntime?.refresh?.();
	}

	function focusOverlay(): void {
		const handle = overlayRuntime?.handle;
		if (!handle) return;
		handle.setHidden(false);
		handle.focus();
		overlayRuntime?.refresh?.();
	}

	function addTranscriptEntry(entry: TranscriptEntry): void {
		transcript.push(entry);
	}

	async function ensureOverlay(ctx: ExtensionCommandContext): Promise<void> {
		if (!ctx.hasUI) return;
		lastCtx = ctx;

		if (overlayRuntime?.handle) {
			focusOverlay();
			return;
		}

		const runtime: OverlayRuntime = {};
		const closeRuntime = () => {
			if (runtime.closed) return;
			runtime.closed = true;
			runtime.handle?.hide();
			if (overlayRuntime === runtime) {
				overlayRuntime = null;
			}
			runtime.finish?.();
		};

		runtime.close = closeRuntime;
		overlayRuntime = runtime;

		void ctx.ui
			.custom<void>(
				async (tui, theme, keybindings, done) => {
					runtime.finish = () => {
						done();
					};

					const overlay = new StudyOverlayComponent(
						tui,
						theme,
						keybindings,
						() => transcript,
						() => overlayStatus,
						() => studyRoot,
						() => chunks.length,
						(value) => {
							void submitFromOverlay(ctx, value);
						},
						() => {
							overlayDraft = overlay.getDraft();
							closeRuntime();
						},
						() => {
							overlayRuntime?.handle?.unfocus();
							overlayRuntime?.refresh?.();
						},
					);

					overlay.focused = runtime.handle?.isFocused() ?? true;
					overlay.setDraft(overlayDraft);
					runtime.setDraft = (value) => {
						overlay.setDraft(value);
					};
					runtime.refresh = () => {
						overlay.focused = runtime.handle?.isFocused() ?? false;
						overlay.refresh();
					};
					runtime.close = () => {
						overlayDraft = overlay.getDraft();
						closeRuntime();
					};

					if (runtime.closed) {
						done();
					}

					return overlay;
				},
				{
					overlay: true,
					overlayOptions: {
						width: "78%",
						minWidth: 72,
						maxHeight: "78%",
						anchor: "top-center",
						margin: { top: 1, left: 2, right: 2 },
						nonCapturing: true,
					},
					onHandle: (handle) => {
						runtime.handle = handle;
						handle.focus();
						if (runtime.closed) {
							closeRuntime();
						}
					},
				},
			)
			.catch((error) => {
				if (overlayRuntime === runtime) {
					overlayRuntime = null;
				}
				ctx.ui.notify(error instanceof Error ? error.message : String(error), "error");
			});
	}

	function parseOverlayCommand(value: string): { name: string; args: string } | null {
		const trimmed = value.trim();
		const match = trimmed.match(/^\/(quiz|status|clear|help|topic)(?:\s+(.*))?$/);
		if (!match) return null;
		return { name: match[1], args: match[2]?.trim() ?? "" };
	}

	async function submitFromOverlay(ctx: ExtensionCommandContext, value: string): Promise<void> {
		const text = value.trim();
		if (!text) {
			setOverlayStatus("Enter a question or /command before submitting.", ctx);
			return;
		}

		// Check for overlay commands first
		const cmd = parseOverlayCommand(text);
		if (cmd) {
			overlayDraft = "";
			overlayRuntime?.setDraft?.("");
			await handleOverlayCommand(cmd.name, cmd.args, ctx);
			return;
		}

		// Regular question
		overlayDraft = "";
		overlayRuntime?.setDraft?.("");
		await answerQuestion(ctx, text);
	}

	async function handleOverlayCommand(name: string, args: string, ctx: ExtensionCommandContext): Promise<void> {
		if (name === "help") {
			addTranscriptEntry({ type: "divider" });
			addTranscriptEntry({ type: "status", text: "Available commands:" });
			addTranscriptEntry({ type: "status", text: "  /quiz [topic]  — Generate an interactive Microsoft-style quiz" });
			addTranscriptEntry({ type: "status", text: "  /topic <path>  — Change study folder" });
			addTranscriptEntry({ type: "status", text: "  /status        — Show study folder status" });
			addTranscriptEntry({ type: "status", text: "  /clear         — Clear transcript" });
			addTranscriptEntry({ type: "status", text: "  /help          — Show this help" });
			addTranscriptEntry({ type: "status", text: "  Or just type a question to get an answer from your study material" });
			syncUi(ctx);
			return;
		}

		if (name === "status") {
			const files = new Set(chunks.map((c) => c.file));
			addTranscriptEntry({ type: "divider" });
			addTranscriptEntry({ type: "status", text: `Root: ${studyRoot}` });
			addTranscriptEntry({ type: "status", text: `Markdown files: ${files.size}` });
			addTranscriptEntry({ type: "status", text: `Searchable chunks: ${chunks.length}` });
			syncUi(ctx);
			return;
		}

		if (name === "clear") {
			transcript = [];
			syncUi(ctx);
			return;
		}

		if (name === "topic") {
			if (args.trim()) {
				const newRoot = resolveStudyRoot(ctx.cwd, args.trim());
				if (!existsSync(newRoot) || !statSync(newRoot).isDirectory()) {
					addTranscriptEntry({ type: "status", text: `Folder not found: ${newRoot}` });
					syncUi(ctx);
					return;
				}
				studyRoot = newRoot;
				chunks = await loadCorpus(studyRoot);
				addTranscriptEntry({ type: "divider" });
				addTranscriptEntry({ type: "status", text: `Switched to: ${studyRoot} (${chunks.length} chunks)` });
			} else {
				addTranscriptEntry({ type: "status", text: `Current: ${studyRoot} (${chunks.length} chunks)` });
			}
			syncUi(ctx);
			return;
		}

		if (name === "quiz") {
			await generateQuiz(ctx, args.trim() || undefined);
			return;
		}
	}

	async function answerQuestion(ctx: ExtensionCommandContext, question: string): Promise<void> {
		if (busy) {
			setOverlayStatus("Still processing previous request...", ctx);
			return;
		}

		if (chunks.length === 0) {
			addTranscriptEntry({ type: "divider" });
			addTranscriptEntry({ type: "user", text: question });
			addTranscriptEntry({ type: "assistant", text: "No study material loaded. Use /topic <path> to set a study folder first." });
			syncUi(ctx);
			return;
		}

		busy = true;
		addTranscriptEntry({ type: "divider" });
		addTranscriptEntry({ type: "user", text: question });
		addTranscriptEntry({ type: "assistant", text: "", streaming: true });
		setOverlayStatus("⏳ answering...", ctx);
		syncUi(ctx);

		try {
			const context = selectContext(studyRoot, chunks, question);
			const system = `You are an exam study assistant. Answer only from the provided Markdown study material. If the material does not contain enough information, say so. Be concise but useful. Cite source paths from the context in a short "Sources" section.`;
			const answer = await runModel(
				ctx,
				system,
				`Question:\n${question}\n\nStudy material context:\n${context}`,
				`Answering from ${chunks.length} markdown chunks...`,
			);

			if (!answer) {
				// Remove the streaming placeholder
				transcript = transcript.filter((e) => !(e.type === "assistant" && e.streaming));
				addTranscriptEntry({ type: "assistant", text: "Question cancelled." });
				setOverlayStatus("Cancelled.", ctx);
			} else if (answer.startsWith("ERROR:")) {
				transcript = transcript.filter((e) => !(e.type === "assistant" && e.streaming));
				addTranscriptEntry({ type: "assistant", text: answer });
				setOverlayStatus("Error occurred.", ctx);
			} else {
				transcript = transcript.filter((e) => !(e.type === "assistant" && e.streaming));
				addTranscriptEntry({ type: "assistant", text: answer });
				setOverlayStatus("Ready for next question.", ctx);

				// Also save to main chat
				pi.sendMessage({ customType: EXT, display: true, content: answer });
			}
		} catch (err) {
			transcript = transcript.filter((e) => !(e.type === "assistant" && e.streaming));
			addTranscriptEntry({ type: "assistant", text: `ERROR: ${err instanceof Error ? err.message : String(err)}` });
			setOverlayStatus("Error occurred.", ctx);
		} finally {
			busy = false;
			syncUi(ctx);
		}
	}

	async function generateQuiz(ctx: ExtensionCommandContext, topic?: string): Promise<void> {
		if (busy) {
			setOverlayStatus("Still processing previous request...", ctx);
			return;
		}

		if (chunks.length === 0) {
			addTranscriptEntry({ type: "status", text: "No study material loaded. Use /topic <path> to set a study folder first." });
			syncUi(ctx);
			return;
		}

		busy = true;
		addTranscriptEntry({ type: "divider" });
		addTranscriptEntry({ type: "status", text: topic ? `Generating quiz on: ${topic}...` : "Generating quiz..." });
		setOverlayStatus("⏳ generating quiz...", ctx);
		syncUi(ctx);

		try {
			const requestedQuestions = 5;
			const requestedOptions = 4;
			const query = topic || "exam objectives and key concepts";
			const context = selectContext(studyRoot, chunks, query, 85_000);
			const system = `You create Microsoft certification exam practice quizzes from provided Markdown study material. Write realistic scenario-based questions similar to Microsoft exams. Use only the provided material. Some questions may have more than one correct answer where appropriate. Return STRICT JSON only, no markdown.`;
			const user = `Create a practice quiz.\n\nTopic/focus: ${query}\nNumber of questions: ${requestedQuestions}\nAnswer options per question: ${requestedOptions}\nDifficulty: Intermediate\n\nJSON schema:\n{\n  "title": "string",\n  "questions": [\n    {\n      "id": "Q1",\n      "question": "scenario-based question text",\n      "options": ["answer option 1", "answer option 2"],\n      "correctOptionIndexes": [1],\n      "explanation": "why the answer is correct and distractors are wrong",\n      "references": ["relative/source/path.md"]\n    }\n  ]\n}\n\nRules:\n- correctOptionIndexes are 1-based.\n- Include exactly ${requestedOptions} options per question.\n- Include exactly ${requestedQuestions} questions.\n- Make distractors plausible.\n- Avoid trivia; test applied understanding.\n\nStudy material context:\n${context}`;
			const raw = await runModel(ctx, system, user, `Generating ${requestedQuestions}-question quiz...`);

			if (!raw) {
				addTranscriptEntry({ type: "status", text: "Quiz generation cancelled." });
				setOverlayStatus("Cancelled.", ctx);
				busy = false;
				syncUi(ctx);
				return;
			}

			if (raw.startsWith("ERROR:")) {
				addTranscriptEntry({ type: "status", text: `Quiz generation failed: ${raw}` });
				setOverlayStatus("Quiz failed.", ctx);
				busy = false;
				syncUi(ctx);
				return;
			}

			let quiz: Quiz;
			try {
				quiz = normalizeQuiz(extractJson(raw), requestedQuestions, requestedOptions);
				if (quiz.questions.length === 0) throw new Error("No usable questions returned");
			} catch (err) {
				addTranscriptEntry({
					type: "status",
					text: `Quiz parsing failed: ${err instanceof Error ? err.message : String(err)}`,
				});
				setOverlayStatus("Quiz failed.", ctx);
				busy = false;
				syncUi(ctx);
				return;
			}

			// Hide the study overlay temporarily and show the quiz
			overlayRuntime?.handle?.hide();

			const quizResult = await ctx.ui.custom<QuizResult>((tui: any, theme: any, _kb: any, done: (value: QuizResult) => void) => {
				const quizComponent = new QuizOverlayComponent(quiz, theme, tui);
				quizComponent.onComplete = done;
				return quizComponent;
			});

			// Show the study overlay again
			overlayRuntime?.handle?.setHidden(false);
			focusOverlay();

			// Add quiz results to transcript
			const summary = quizSummary(quizResult);
			addTranscriptEntry({ type: "divider" });
			addTranscriptEntry({ type: "status", text: `Quiz: ${quiz.title || "Study quiz"} — Score: ${quizResult.cancelled ? "cancelled" : `${quizResult.score}/${quizResult.total}`}` });

			// Also save quiz result to main chat
			pi.sendMessage({ customType: EXT, display: true, content: summary });

			setOverlayStatus("Quiz complete. Ready for next question.", ctx);
		} catch (err) {
			addTranscriptEntry({ type: "status", text: `Quiz error: ${err instanceof Error ? err.message : String(err)}` });
			setOverlayStatus("Quiz failed.", ctx);
		} finally {
			busy = false;
			syncUi(ctx);
		}
	}

	// ─── Keyboard shortcuts ────────────────────────────────────────────────

	for (const shortcut of STUDY_FOCUS_SHORTCUTS) {
		pi.registerShortcut(shortcut, {
			description: "Toggle Study overlay focus while leaving it open.",
			handler: async (_ctx) => {
				toggleOverlayFocus();
			},
		});
	}

	// ─── Session lifecycle ──────────────────────────────────────────────────

	pi.on("session_shutdown", async () => {
		dismissOverlay();
	});

	// ─── Command ────────────────────────────────────────────────────────────

	pi.registerCommand("study", {
		description: "Open an exam study assistant with a persistent overlay. Ask questions, generate quizzes (/quiz), and more. Usage: /study [folder]",
		handler: async (args, ctx) => {
			if (!ctx.hasUI) {
				ctx.ui.notify("/study requires interactive mode", "error");
				return;
			}

			const root = resolveStudyRoot(ctx.cwd, args);
			if (!existsSync(root) || !statSync(root).isDirectory()) {
				ctx.ui.notify(`Study folder not found: ${root}`, "error");
				return;
			}

			// Load corpus if needed (fresh or root changed)
			if (studyRoot !== root || chunks.length === 0) {
				studyRoot = root;
				chunks = await loadCorpus(studyRoot);
				if (chunks.length === 0) {
					ctx.ui.notify(`No Markdown content found in ${root}`, "error");
					return;
				}
				transcript = [];
				addTranscriptEntry({ type: "status", text: `Loaded ${chunks.length} chunks from ${studyRoot}` });
				addTranscriptEntry({ type: "status", text: "Type a question, or use /quiz, /status, /clear, /help" });
			}

			await ensureOverlay(ctx);
		},
	});
}
