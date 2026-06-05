---
name: codex-usage
description: Summarize local Codex usage over a requested date range or last N days, including input tokens, cached input tokens, output tokens, reasoning output tokens, request counts, model breakdowns, and OpenAI API-equivalent USD cost calculations. Use when the user asks for Codex usage, token spend, API cost estimates, GPT model cost breakdowns, or spend-justification reports from local Codex logs.
---

# Codex Usage

## Workflow

Use this skill to produce spend-ready Codex usage reports from local Codex session logs.

1. Determine the requested range.
   - For "last X days", include today as a partial day unless the user says otherwise.
   - For explicit dates, use the user's local timezone and show exact start/end dates.
   - If no range is provided, default to the last 7 days including today.

2. Run `scripts/codex_usage_report.py`.
   - It reads `~/.codex/sessions` and `~/.codex/archived_sessions`.
   - It sums `token_count.info.last_token_usage` deltas, not cumulative totals.
   - It prints a Markdown report with tables by default.
   - It writes Markdown and CSV files only when the user explicitly asks for files and `--output-dir` is supplied.

3. Verify current OpenAI API prices before giving the final report.
   - Pricing changes over time, so browse official OpenAI sources before finalizing unless the user explicitly asks not to browse.
   - Prefer `https://openai.com/api/pricing/` and model docs under `https://developers.openai.com/api/docs/models/`.
   - If the script cannot fetch pricing, compare its embedded fallback rates against official sources and disclose any fallback.

4. Report assumptions clearly.
   - Local Codex logs may not always include a model name. In that case, use the requested `--assume-model` for cost calculation and call out that unknown model rows were costed as that model.
   - Cached input is priced separately and is also part of the total input token count in Codex usage events.
   - If any request crosses a model-specific long-context threshold, disclose whether a multiplier was applied or whether manual adjustment is required.

## Quick Commands

Last 7 days, assuming GPT-5.5 for unknown model rows:

```powershell
python .\scripts\codex_usage_report.py --days 7 --assume-model gpt-5.5
```

Explicit date range:

```powershell
python .\scripts\codex_usage_report.py --start 2026-05-28 --end 2026-06-05 --assume-model gpt-5.5
```

Cost only with a different model assumption:

```powershell
python .\scripts\codex_usage_report.py --days 5 --assume-model gpt-5.4
```

## Output Expectations

Always provide:

- A concise headline with the total estimated spend and date range.
- A daily token breakdown table: requests, input, cached input, fresh input, output, reasoning output, and total tokens.
- A daily cost breakdown table: fresh input cost, cached input cost, output cost, and total USD.
- A model breakdown table: requests, tokens, and cost by detected model or assumption.
- Grand total.
- Official OpenAI pricing source links used for the calculation.

Do not generate report files unless the user asks for saved files, exports, CSVs, or deliverables. If files are requested, pass `--output-dir` and link the generated files in the final answer.

## Script Notes

The script has embedded fallback pricing for common GPT models so it can still run offline. Because spend reporting is important, use official OpenAI pricing as the authority in the final answer and update the calculation if the live price differs from the fallback table.
