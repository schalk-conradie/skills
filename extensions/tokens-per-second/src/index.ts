/**
 * Tokens-per-second + nicer footer extension.
 *
 * Replaces the built-in footer with a richer, multi-line status bar:
 *
 *   line 1: cwd (with ~), git branch, session name
 *   line 2: tokens (↑ in / ↓ out / cache R/W), $ cost, live tps, context %,
 *           model id + thinking level (right-aligned)
 *   line 3: warning when context window is >70% (yellow) or >90% (red)
 *
 * Live tps is a 1-second sliding window over assistant streaming output.
 * When idle, the last completed turn's average tps is shown instead.
 */

import type { AssistantMessage } from "@mariozechner/pi-ai";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { truncateToWidth, visibleWidth } from "@mariozechner/pi-tui";

const CHARS_PER_TOKEN = 4;
const WINDOW_MS = 1000;
const SAMPLE_RETENTION_MS = 3000;
const TICK_MS = 200;

type Sample = { t: number; tokens: number; exact: boolean };

export default function (pi: ExtensionAPI) {
	// ---------- live tps state ----------
	let turnStart = 0;
	let streaming = false;
	let samples: Sample[] = [];
	let lastTurnAvg: { tps: number; tokens: number; secs: number } | null = null;

	const extractText = (msg: any): string => {
		if (!msg) return "";
		if (typeof msg.content === "string") return msg.content;
		if (Array.isArray(msg.content)) {
			return msg.content
				.map((b: any) => (typeof b === "string" ? b : typeof b?.text === "string" ? b.text : ""))
				.join("");
		}
		return "";
	};

	const tokensFromMessage = (msg: any): { tokens: number; exact: boolean } => {
		const out = msg?.usage?.output;
		if (typeof out === "number" && out > 0) return { tokens: out, exact: true };
		return { tokens: Math.round(extractText(msg).length / CHARS_PER_TOKEN), exact: false };
	};

	const trimSamples = (now: number) => {
		const cutoff = now - SAMPLE_RETENTION_MS;
		let i = 0;
		while (i < samples.length && samples[i]!.t < cutoff) i++;
		if (i > 0) samples = samples.slice(i);
	};

	const computeWindowTps = (now: number): { tps: number; exact: boolean } | null => {
		if (samples.length < 2) return null;
		const latest = samples[samples.length - 1]!;
		const windowStart = now - WINDOW_MS;
		let oldest = samples[0]!;
		for (const s of samples) {
			if (s.t >= windowStart) break;
			oldest = s;
		}
		const dt = (latest.t - oldest.t) / 1000;
		if (dt <= 0) return null;
		const dTokens = latest.tokens - oldest.tokens;
		if (dTokens < 0) return null;
		return { tps: dTokens / dt, exact: latest.exact && oldest.exact };
	};

	pi.on("turn_start", async () => {
		turnStart = Date.now();
		streaming = true;
		samples = [{ t: turnStart, tokens: 0, exact: true }];
	});

	pi.on("message_update", async (event) => {
		const msg: any = (event as any).message;
		if (!msg || msg.role !== "assistant") return;
		if (!turnStart) return;
		const now = Date.now();
		const { tokens, exact } = tokensFromMessage(msg);
		const last = samples[samples.length - 1];
		if (last && last.t === now) {
			last.tokens = tokens;
			last.exact = exact;
		} else {
			samples.push({ t: now, tokens, exact });
		}
		trimSamples(now);
	});

	pi.on("message_end", async (event) => {
		const msg: any = (event as any).message;
		if (!msg || msg.role !== "assistant") return;
		if (!turnStart) return;
		const elapsed = (Date.now() - turnStart) / 1000;
		const tokens: number | undefined = msg.usage?.output;
		if (typeof tokens === "number" && tokens > 0 && elapsed > 0) {
			lastTurnAvg = { tps: tokens / elapsed, tokens, secs: elapsed };
		}
	});

	pi.on("turn_end", async () => {
		streaming = false;
		turnStart = 0;
	});

	// ---------- footer ----------
	pi.on("session_start", async (_event, ctx) => {
		ctx.ui.setFooter((tui, theme, footerData) => {
			const unsubBranch = footerData.onBranchChange(() => tui.requestRender());

			// Periodic ticker so live tps updates even between message_update events.
			const ticker = setInterval(() => {
				tui.requestRender();
			}, TICK_MS);

			return {
				dispose() {
					unsubBranch();
					clearInterval(ticker);
				},
				invalidate() {},
				render(width: number): string[] {
					// ----- gather data -----
					const cwdRaw = ctx.sessionManager.getCwd();
					const home = process.env.HOME || process.env.USERPROFILE;
					const cwd = home && cwdRaw.startsWith(home) ? `~${cwdRaw.slice(home.length)}` : cwdRaw;
					const branch = footerData.getGitBranch();
					const sessionName = ctx.sessionManager.getSessionName();

					let totalInput = 0,
						totalOutput = 0,
						totalCacheRead = 0,
						totalCacheWrite = 0,
						totalCost = 0;
					for (const e of ctx.sessionManager.getEntries()) {
						if (e.type === "message" && e.message.role === "assistant") {
							const m = e.message as AssistantMessage;
							totalInput += m.usage.input;
							totalOutput += m.usage.output;
							totalCacheRead += m.usage.cacheRead;
							totalCacheWrite += m.usage.cacheWrite;
							totalCost += m.usage.cost.total;
						}
					}

					const ctxUsage = ctx.getContextUsage();
					const contextWindow = ctxUsage?.contextWindow ?? ctx.model?.contextWindow ?? 0;
					const ctxPct = ctxUsage?.percent ?? null;

					const model = ctx.model;
					const thinking = pi.getThinkingLevel();

					// ----- live tps -----
					let tpsText: string | null = null;
					let tpsColor: "accent" | "dim" = "dim";
					if (streaming && turnStart) {
						const now = Date.now();
						const w = computeWindowTps(now);
						if (w) {
							tpsText = `${w.exact ? "" : "~"}${w.tps.toFixed(1)} tps`;
							tpsColor = "accent";
						} else {
							tpsText = "… tps";
						}
					} else if (lastTurnAvg) {
						tpsText = `${lastTurnAvg.tps.toFixed(1)} tps avg`;
					}

					// ----- formatting helpers -----
					const fmtTok = (n: number) => {
						if (n < 1000) return `${n}`;
						if (n < 10000) return `${(n / 1000).toFixed(1)}k`;
						if (n < 1_000_000) return `${Math.round(n / 1000)}k`;
						return `${(n / 1_000_000).toFixed(1)}M`;
					};

					const SEP = theme.fg("dim", " │ ");

					// ----- LINE 1: cwd/branch/session (left) + model/thinking (right) -----
					let line1Left = theme.fg("dim", cwd);
					if (branch) line1Left += "  " + theme.fg("accent", "⎇") + " " + theme.fg("muted", branch);
					if (sessionName) line1Left += theme.fg("dim", "  • " + sessionName);

					const modelId = model?.id || "no-model";
					const providerCount = footerData.getAvailableProviderCount();
					const providerPrefix =
						providerCount > 1 && model ? theme.fg("muted", `${model.provider}/`) : "";
					let line1Right = providerPrefix + theme.fg("accent", modelId);
					if (model?.reasoning) {
						const t = thinking || "off";
						const tColor = t === "off" ? "dim" : t === "high" || t === "xhigh" ? "warning" : "muted";
						line1Right += theme.fg("dim", " • ") + theme.fg(tColor, `🧠 ${t}`);
					}

					const l1lW = visibleWidth(line1Left);
					const l1rW = visibleWidth(line1Right);
					let line1: string;
					if (l1lW + 2 + l1rW <= width) {
						line1 = line1Left + " ".repeat(width - l1lW - l1rW) + line1Right;
					} else if (l1rW + 4 <= width) {
						// Truncate cwd to make room for model on right
						const avail = width - l1rW - 2;
						const truncLeft = truncateToWidth(line1Left, avail, theme.fg("dim", "…"));
						const pad = Math.max(0, width - visibleWidth(truncLeft) - l1rW);
						line1 = truncLeft + " ".repeat(pad) + line1Right;
					} else {
						line1 = truncateToWidth(line1Right, width, "");
					}

					// ----- LINE 2: tokens/cost • tps • ctx • ext statuses -----
					const tokenBits: string[] = [];
					if (totalInput) tokenBits.push(`↑${fmtTok(totalInput)}`);
					if (totalOutput) tokenBits.push(`↓${fmtTok(totalOutput)}`);
					if (totalCacheRead) tokenBits.push(`R${fmtTok(totalCacheRead)}`);
					if (totalCacheWrite) tokenBits.push(`W${fmtTok(totalCacheWrite)}`);
					const tokenGroup = tokenBits.length ? theme.fg("dim", tokenBits.join(" ")) : "";

					const groups: string[] = [];
					if (tokenGroup) groups.push(tokenGroup);
					if (totalCost) groups.push(theme.fg("muted", `$${totalCost.toFixed(3)}`));
					if (tpsText) {
						const dot = streaming ? theme.fg("accent", "● ") : "";
						groups.push(dot + theme.fg(tpsColor, tpsText));
					}

					// context %
					const pctNum = ctxPct ?? 0;
					const isCrit = ctxPct !== null && pctNum > 90;
					const isWarn = ctxPct !== null && pctNum >= 70 && !isCrit;
					const pctDisplay =
						ctxPct === null
							? `ctx ?/${fmtTok(contextWindow)}`
							: `ctx ${pctNum.toFixed(1)}%/${fmtTok(contextWindow)}`;
					let ctxStr: string;
					if (isCrit) ctxStr = theme.fg("error", theme.bold(`⛔ ${pctDisplay} compact!`));
					else if (isWarn) ctxStr = theme.fg("warning", `⚠ ${pctDisplay}`);
					else ctxStr = theme.fg("dim", pctDisplay);
					groups.push(ctxStr);

					// ext statuses appended as their own group(s)
					const extStatuses = footerData.getExtensionStatuses();
					if (extStatuses.size > 0) {
						const extText = Array.from(extStatuses.entries())
							.sort(([a], [b]) => a.localeCompare(b))
							.map(([, t]) => t.replace(/[\r\n\t]/g, " ").replace(/ +/g, " ").trim())
							.filter((t) => t.length > 0)
							.join(theme.fg("dim", "  •  "));
						if (extText) groups.push(extText);
					}

					const line2 = truncateToWidth(groups.join(SEP), width, theme.fg("dim", "…"));

					return [line1, line2];
				},
			};
		});
	});
}
