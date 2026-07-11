---
name: memory_engine
description: "Use the memory_engine tools for long-term memory recall, deterministic analytics, transcript logging, and sync operations."
---

# Memory Engine Skill

Use this skill for Nouva's 2-lane memory system:

- **Semantic recall** via `pgvector` for finding relevant concepts or dates.
- **Deterministic analytics** via SQL over daily summaries for counts, trends, and date lists.
- **Operational tools** for transcript writing, raw file access, and sync orchestration.

## Tools
- `mcp_query_memory`: semantic recall tool. Returns the best matching summaries and archive path pointers for follow-up. Use for recall/context only, not for counts, ranking, aggregation, or trend analysis.
- `mcp_query_analytics`: deterministic analytics executor over daily summaries. Structured input only; the agent must parse natural language before calling it.
- `mcp_grep_memory`: search for a specific keyword or pattern inside all memory markdown files (active and/or archived).
- `mcp_read_memory_file`: read the raw content of a specific memory markdown file using its relative path.
- `mcp_write_transcript`: writes a session transcript into the memory workspace.
- `mcp_manage_transcript_session`: manages slash-command style transcript controls such as auto on/off/status and full-session write.
- `mcp_sync_memory`: runs the sync pipeline. This tool has side effects.

## Routing Rules

Use these rules to keep analytics answers deterministic:

- Use `mcp_query_analytics` for questions that require aggregation/time-series:
  - "which days / when / how many times"
  - "pattern / trend"
  - "every <weekday>"
  - "last 2 weeks / last month"
  - "what did I talk about most"
- Prefer `mcp_query_analytics` whenever the user asks for counts, top values, averages, distributions, grouped results, weekday patterns, or date aggregation.
- Before calling `mcp_query_analytics`, convert the user's question into explicit structured arguments.
- Never send raw natural-language questions to `mcp_query_analytics`.
- Use `mcp_query_memory` for detail/context recall:
  - "explain the details from that time"
  - "why / what decision / what plan"
  - "find the conversation that discussed ..."
- Do not use `mcp_query_memory` to answer counts, top values, averages, trends, distributions, or grouped/date-based analytics.
- For mixed questions, run `mcp_query_analytics` first to identify candidate dates or periods, then run `mcp_query_memory` only if the user also wants detailed context.
- Use `mcp_grep_memory` when searching for exact strings, IDs, errors, or codes that might not yield good semantic matches in vector search.
- Use `mcp_read_memory_file` to read the full content of a specific session transcript or daily summary once you have the exact relative path.
- If `mcp_query_memory` only gives you a date or archive directory hint, use `mcp_grep_memory` first to locate the exact relative file path, then call `mcp_read_memory_file`.
- Use `mcp_write_transcript` only when conversation history should be written into active memory. Do not log transcripts by default.
- Use `mcp_sync_memory` only for explicit sync, rebuild, ingestion, or maintenance operations. Do not run it as part of normal recall.

## `mcp_query_analytics` Contract

This tool accepts structured arguments only and is designed as an executor, not a natural-language parser.

Supported intents:

- `dates_for_value`: find which dates contain a value in `projects`, `tags`, `people`, or `technologies`.
- `top_values`: count top values in one array column across a date range.
- `mood_timeseries`: list mood by date across a date range.
- `mood_distribution_by_weekday`: aggregate mood counts for one weekday.
- `count_distinct_dates_for_value`: return how many distinct dates contain one value.
- `count_by_period`: return counts for one value grouped by `day`, `week`, or `month`.
- `grouped_top_values`: return top values for each `day`, `week`, or `month`.
- `average_importance`: return average `importance`, optionally filtered by one `column` + `value`.

Supported fields:

- `intent`: required.
- `column`: required for `dates_for_value`, `top_values`, `count_distinct_dates_for_value`, `count_by_period`, and `grouped_top_values`. Allowed values: `projects`, `tags`, `people`, `technologies`. Optional for `average_importance`.
- `value`: required for `dates_for_value`, `count_distinct_dates_for_value`, and `count_by_period`. Optional for `average_importance`, but required if `column` is provided.
- `start_date`, `end_date`: ISO `YYYY-MM-DD`. Required for `mood_timeseries`. Optional for `dates_for_value`, `count_distinct_dates_for_value`, and `average_importance`. Optional for `top_values` and defaults to the last 30 days if omitted. Optional for `count_by_period` and `grouped_top_values`, which default to the last 90 days if omitted.
- `weekday`: integer `0..6` where `0=Monday`.
- `weekday_name`: alternative to `weekday`, allowed values `monday..sunday`.
- `limit`: optional for `top_values` and `grouped_top_values`, range `1..50`, default `20` for `top_values` and `5` for `grouped_top_values`.
- `period`: required for `count_by_period` and `grouped_top_values`. Allowed values: `day`, `week`, `month`.

Examples:

- `{"intent":"top_values","column":"tags","start_date":"2025-05-01","end_date":"2025-05-31","limit":10}`
- `{"intent":"dates_for_value","column":"projects","value":"Nouverse"}`
- `{"intent":"mood_timeseries","start_date":"2026-07-01","end_date":"2026-07-10"}`
- `{"intent":"mood_distribution_by_weekday","weekday":1}`
- `{"intent":"count_distinct_dates_for_value","column":"projects","value":"Nouverse","start_date":"2025-05-01","end_date":"2025-05-31"}`
- `{"intent":"count_by_period","column":"projects","value":"Nouverse","period":"month","start_date":"2025-01-01","end_date":"2025-06-30"}`
- `{"intent":"grouped_top_values","column":"tags","period":"month","start_date":"2025-01-01","end_date":"2025-06-30","limit":5}`
- `{"intent":"average_importance","column":"projects","value":"Nouverse","start_date":"2025-05-01","end_date":"2025-05-31"}`

## `mcp_write_transcript` Notes

- Use `mode="create"` exactly once on the first user turn of a new chat session.
- Use `mode="append"` for all later turns in that same chat session.
- Preferred `session_key` pattern: `agent:main:{provider}:direct:{user_identifier_from_provider}`.
- `stable_session_id` is required and should come from the host/agent session state. Do not let the tool generate or guess it.
- Each write stores one raw transcript turn in archive-style format:
  `user: ...`
  `assistant: ...`
- `create` requires `stable_session_id`, `user_message`, `assistant_message`, `session_key`, and `source`.
- `append` requires `stable_session_id`, `user_message`, and `assistant_message`.
- `append` resolves the target file strictly by the same `stable_session_id` through the active session registry.
- Do not append by "latest transcript today" and do not treat `session_key` as a unique chat-session identifier.
- `source` should identify the channel, such as `whatsapp`, `telegram`, `webchat`, or `trae`.
- Policy guardrail: do not call `mcp_write_transcript` unless the user explicitly requested a `nouva-memory` transcript command or the current session already has `auto_write_enabled=true`.

## `mcp_manage_transcript_session` Notes

- Default transcript auto-write mode is off.
- User-facing transcript commands should use the `nouva:` prefix family:
  `/nouva-memory-auto-on`, `/nouva-memory-auto-off`, `/nouva-memory-status`, `/nouva-memory-write-transcript`.
- If the agent sees one of those commands in the user message, it should route to `mcp_manage_transcript_session` instead of treating it as a normal chat request.
- `/nouva-memory-auto-on` enables auto-write for the current `stable_session_id`.
- `/nouva-memory-auto-off` disables auto-write for the current `stable_session_id`.
- `/nouva-memory-status` returns whether auto-write is currently enabled for the current `stable_session_id`.
- `/nouva-memory-write-transcript` writes or rewrites the full transcript for the current session using `turns_json`, which must contain the complete in-memory session turn list.
- `turns_json` must decode into a JSON array of objects shaped like:
  `{"user_message":"...","assistant_message":"..."}`
- Agent behavior policy:
  - If auto-write is off, do not call `mcp_write_transcript` unless the user explicitly uses `/nouva-memory-*`.
  - If auto-write is on, `mcp_write_transcript` may be called after each completed turn for the same `stable_session_id`.

## Do / Don't

- Do use `mcp_query_memory` for recall and context reconstruction.
- Do use `mcp_query_analytics` for counts, trends, distributions, and date aggregation.
- Do convert natural language into structured analytics arguments before calling `mcp_query_analytics`.
- Do run analytics first for mixed questions that combine aggregation with detail recall.
- Don't use `mcp_query_memory` to answer aggregation questions.
- Don't send free-form natural language directly to `mcp_query_analytics`.
- Don't run sync unless the task explicitly needs memory maintenance or ingestion.
- Don't write transcripts unless persistent logging is actually required.
