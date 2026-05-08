import { complete, type UserMessage } from "@earendil-works/pi-ai";
import { BorderedLoader, getMarkdownTheme, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Key, Markdown, matchesKey, truncateToWidth, wrapTextWithAnsi } from "@earendil-works/pi-tui";
import { existsSync, statSync } from "node:fs";
import { readdir, readFile } from "node:fs/promises";
import { basename, isAbsolute, join, relative, resolve } from "node:path";

const EXT = "exam-study";
const DEFAULT_MAX_CONTEXT_CHARS = 70_000;
const MAX_FILES = 1200;
const MAX_QUESTIONS = 50;

type StudyMode = "answer" | "quiz" | "status";

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
	const ab620 = join(cwd, "microsoft-learn-ab-620");
	if (existsSync(ab620)) return ab620;
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

async function runModel(ctx: any, systemPrompt: string, userText: string, loadingMessage: string): Promise<string | null> {
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

async function showQuiz(ctx: any, quiz: Quiz): Promise<QuizResult> {
	return await ctx.ui.custom<QuizResult>((tui: any, theme: any, _kb: any, done: (value: QuizResult) => void) => {
		let current = 0;
		let option = 0;
		let submitted = false;
		let cachedLines: string[] | undefined;
		const selections = quiz.questions.map(() => new Set<number>());

		function refresh() {
			cachedLines = undefined;
			tui.requestRender();
		}

		function score(): number {
			return quiz.questions.reduce((sum, q, i) => sum + (sameSelection(Array.from(selections[i]), q.correctOptionIndexes) ? 1 : 0), 0);
		}

		function finish(cancelled: boolean) {
			done({
				cancelled,
				submitted,
				score: submitted ? score() : 0,
				total: quiz.questions.length,
				quiz,
				selections: selections.map((s) => Array.from(s).sort((a, b) => a - b)),
			});
		}

		function handleInput(data: string) {
			const q = quiz.questions[current];
			if (!q) return;
			if (matchesKey(data, Key.escape) || data === "q") {
				finish(!submitted);
				return;
			}
			if (matchesKey(data, Key.left) || data === "p") {
				current = Math.max(0, current - 1);
				option = 0;
				refresh();
				return;
			}
			if (matchesKey(data, Key.right) || data === "n") {
				current = Math.min(quiz.questions.length - 1, current + 1);
				option = 0;
				refresh();
				return;
			}
			if (!submitted && (matchesKey(data, Key.up) || data === "k")) {
				option = Math.max(0, option - 1);
				refresh();
				return;
			}
			if (!submitted && (matchesKey(data, Key.down) || data === "j")) {
				option = Math.min(q.options.length - 1, option + 1);
				refresh();
				return;
			}
			if (!submitted && (matchesKey(data, Key.enter) || matchesKey(data, Key.space))) {
				const value = option + 1;
				const selected = selections[current];
				if (selected.has(value)) selected.delete(value);
				else selected.add(value);
				refresh();
				return;
			}
			if (!submitted && data === "s") {
				submitted = true;
				refresh();
				return;
			}
		}

		function render(width: number): string[] {
			if (cachedLines) return cachedLines;
			const lines: string[] = [];
			const add = (s = "") => lines.push(truncateToWidth(s, width));
			const addWrapped = (s: string, indent = "") => {
				for (const line of wrapTextWithAnsi(s, Math.max(10, width - indent.length))) add(indent + line);
			};
			const q = quiz.questions[current];
			const selected = selections[current];
			const correct = new Set(q.correctOptionIndexes);

			add(theme.fg("accent", "─".repeat(width)));
			const title = quiz.title || "Study quiz";
			const progress = `Question ${current + 1}/${quiz.questions.length}`;
			add(theme.fg("accent", theme.bold(` ${title}`)) + theme.fg("dim", `  •  ${progress}`));
			if (submitted) add(theme.fg("success", ` Score: ${score()}/${quiz.questions.length}`));
			lines.push("");
			addWrapped(theme.fg("text", q.question), " ");
			lines.push("");

			for (let i = 0; i < q.options.length; i++) {
				const oneBased = i + 1;
				const isSelected = selected.has(oneBased);
				const isCorrect = correct.has(oneBased);
				const cursor = !submitted && i === option ? theme.fg("accent", ">") : " ";
				let marker = isSelected ? "[x]" : "[ ]";
				let color: "accent" | "text" | "success" | "error" | "muted" = !submitted && i === option ? "accent" : "text";
				if (submitted) {
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
				addWrapped(`${cursor} ${theme.fg(color, `${marker} ${oneBased}. ${q.options[i]}`)}`, "");
			}

			if (submitted) {
				lines.push("");
				const ok = sameSelection(Array.from(selected), q.correctOptionIndexes);
				add(theme.fg(ok ? "success" : "error", ok ? " Correct" : " Incorrect"));
				addWrapped(theme.fg("muted", `Explanation: ${q.explanation}`), " ");
				if (q.references?.length) addWrapped(theme.fg("dim", `References: ${q.references.join(", ")}`), " ");
			}

			lines.push("");
			const help = submitted
				? " ←/→ previous/next • q/Esc close"
				: " ↑↓ select • Enter/Space toggle • ←/→ previous/next • s submit • Esc cancel";
			add(theme.fg("dim", help));
			add(theme.fg("accent", "─".repeat(width)));
			cachedLines = lines;
			return lines;
		}

		return { render, invalidate: () => (cachedLines = undefined), handleInput };
	});
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

export default function examStudy(pi: ExtensionAPI) {
	pi.registerMessageRenderer(EXT, (message, _options, _theme) => {
		return new Markdown(String(message.content || ""), 0, 0, getMarkdownTheme());
	});

	pi.registerCommand("study", {
		description: "Open an exam study assistant for a folder of Markdown notes: ask questions or generate Microsoft-style quizzes. Usage: /study [folder]",
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

			const mode = (await ctx.ui.select("Exam Study Assistant", [
				"Ask a question from the study material",
				"Generate an interactive Microsoft-style quiz",
				"Show study folder status",
			])) as string | undefined;
			if (!mode) return;
			const selectedMode: StudyMode = mode.startsWith("Ask") ? "answer" : mode.startsWith("Generate") ? "quiz" : "status";

			const chunks = await loadCorpus(root);
			if (chunks.length === 0) {
				ctx.ui.notify(`No Markdown content found in ${root}`, "error");
				return;
			}

			if (selectedMode === "status") {
				const files = new Set(chunks.map((c) => c.file));
				pi.sendMessage({
					customType: EXT,
					display: true,
					content: `# Study folder status\n\n- Root: \`${root}\`\n- Markdown files: ${files.size}\n- Searchable chunks: ${chunks.length}\n\nRun \`/study ${root}\` again and choose either answer or quiz mode.`,
				});
				return;
			}

			if (selectedMode === "answer") {
				const question = await ctx.ui.editor("Ask a question", "What do I need to know about MCP tools for AB-620?");
				if (!question?.trim()) return;
				const context = selectContext(root, chunks, question);
				const system = `You are an exam study assistant. Answer only from the provided Markdown study material. If the material does not contain enough information, say so. Be concise but useful. Cite source paths from the context in a short "Sources" section.`;
				const answer = await runModel(
					ctx,
					system,
					`Question:\n${question}\n\nStudy material context:\n${context}`,
					`Answering from ${chunks.length} markdown chunks...`,
				);
				if (!answer) {
					ctx.ui.notify("Cancelled", "info");
					return;
				}
				pi.sendMessage({ customType: EXT, display: true, content: answer });
				return;
			}

			const topic = await ctx.ui.editor(
				"Quiz focus/topic (blank = broad AB-620 coverage)",
				"Integrate and extend agents in Copilot Studio",
			);
			if (topic === undefined) return;
			const countRaw = await ctx.ui.input("Number of questions", "5");
			if (countRaw === undefined) return;
			const optionsRaw = await ctx.ui.input("Number of answer options per question", "4");
			if (optionsRaw === undefined) return;
			const difficulty = (await ctx.ui.select("Difficulty", ["Intermediate", "Hard", "Mixed"])) || "Intermediate";

			const requestedQuestions = Math.max(1, Math.min(MAX_QUESTIONS, Number.parseInt(countRaw, 10) || 5));
			const requestedOptions = Math.max(2, Math.min(8, Number.parseInt(optionsRaw, 10) || 4));
			const query = topic.trim() || "AB-620 Copilot Studio AI agent builder exam objectives";
			const context = selectContext(root, chunks, query, 85_000);
			const system = `You create Microsoft certification exam practice quizzes from provided Markdown study material. Write realistic scenario-based questions similar to Microsoft exams. Use only the provided material. Some questions may have more than one correct answer where appropriate. Return STRICT JSON only, no markdown.`;
			const user = `Create a practice quiz.\n\nTopic/focus: ${query}\nNumber of questions: ${requestedQuestions}\nAnswer options per question: ${requestedOptions}\nDifficulty: ${difficulty}\n\nJSON schema:\n{\n  "title": "string",\n  "questions": [\n    {\n      "id": "Q1",\n      "question": "scenario-based question text",\n      "options": ["answer option 1", "answer option 2"],\n      "correctOptionIndexes": [1],\n      "explanation": "why the answer is correct and distractors are wrong",\n      "references": ["relative/source/path.md"]\n    }\n  ]\n}\n\nRules:\n- correctOptionIndexes are 1-based.\n- Include exactly ${requestedOptions} options per question.\n- Include exactly ${requestedQuestions} questions.\n- Make distractors plausible.\n- Avoid trivia; test applied understanding.\n\nStudy material context:\n${context}`;
			const raw = await runModel(ctx, system, user, `Generating ${requestedQuestions}-question quiz...`);
			if (!raw) {
				ctx.ui.notify("Cancelled", "info");
				return;
			}
			if (raw.startsWith("ERROR:")) {
				pi.sendMessage({ customType: EXT, display: true, content: raw });
				return;
			}

			let quiz: Quiz;
			try {
				quiz = normalizeQuiz(extractJson(raw), requestedQuestions, requestedOptions);
				if (quiz.questions.length === 0) throw new Error("No usable questions returned");
			} catch (err) {
				pi.sendMessage({
					customType: EXT,
					display: true,
					content: `# Quiz generation failed\n\n${err instanceof Error ? err.message : String(err)}\n\n## Raw model output\n\n\`\`\`\n${raw}\n\`\`\``,
				});
				return;
			}

			const result = await showQuiz(ctx, quiz);
			pi.sendMessage({ customType: EXT, display: true, content: quizSummary(result) });
		},
	});
}
