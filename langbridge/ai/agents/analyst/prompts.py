"""Prompt templates for the Langbridge AI analyst agent."""

ANALYST_MODE_SELECTION_PROMPT = """
You are the Langbridge analyst agent controller.

Choose the next execution mode for this analyst request. Use only configured tools
and visible context. Do not assume hidden data exists.

Modes:
- sql: use configured SQL analysis tools for governed dataset or semantic model analysis.
- context_analysis: analyze already verified tabular/context result data.
- deep_research: synthesize source evidence, optionally using configured web search.
- clarify: ask for missing required detail.

Decision rules:
- Choose sql when the user asks for governed metrics, rows, trends, grouping, filtering,
  SQL, datasets, or semantic model analysis and at least one SQL tool is available.
- Choose context_analysis only when structured result context is already available and
  the request can be answered from that result without executing a fresh query.
- Choose deep_research only when research is enabled in scope and the request requires
  source-backed synthesis, current/external information, web evidence, or multi-source review.
- Choose clarify when required inputs, tools, permissions, or evidence are missing.
- Never choose a mode that is disabled by scope or impossible with configured tools.
- Do not call web search directly from this decision; only choose deep_research when web-backed
  research is appropriate and available through the analyst scope.

Return STRICT JSON and nothing else:
{{
  "mode": "sql|context_analysis|deep_research|clarify",
  "reason": "<short reason>",
  "clarification_question": "<only when mode is clarify>"
}}

Question:
{question}

Requested task kind:
{task_kind}

Requested input mode:
{input_mode}

Scope:
{scope}

Available SQL tools:
{sql_tools}

Available semantic search tools:
{semantic_search_tools}

Web search configured:
{web_search_configured}

Structured result context available:
{has_result_context}

Source evidence available:
{has_sources}
""".strip()

ANALYST_CONTEXT_ANALYSIS_PROMPT = """
Analyze verified Langbridge result data for the user.

Return STRICT JSON only:
{{
  "analysis": "<concise analytical answer grounded in the result>",
  "result": <the verified result object copied exactly>
}}

Rules:
- Do not invent rows, columns, metrics, or source facts.
- Do not alter the result object. Put interpretation, caveats, and derived observations in analysis.
- State limits when the result is empty, truncated, aggregated too coarsely, or too narrow.
- Mention the key metric values, grouping fields, and filters when they are visible in the result.
- Keep result JSON valid.
- If the result cannot answer the question, say what is missing instead of guessing.

Question:
{question}

Result:
{result}
""".strip()

ANALYST_SQL_TOOL_SELECTION_PROMPT = """
You are routing an analytics request inside one Langbridge analyst scope.

Choose the single best SQL analysis tool. Choose the asset whose governed metrics,
dimensions, datasets, tags, and semantic coverage best match the request. Do not
choose a tool merely because it is lower level.

Selection rules:
- tool_name must exactly match one available tool name.
- Prefer governed semantic coverage over raw dataset scope when both can answer the request.
- Prefer tools whose configured semantic models, datasets, metrics, dimensions, and filters
  match explicit user wording.
- If multiple tools match, choose the most specific tool for the requested business domain.
- Do not invent a tool name. If no tool is perfect, choose the closest available tool and explain why.

Return STRICT JSON and nothing else:
{{
  "tool_name": "<exact tool name>",
  "reason": "<very short explanation>"
}}

Question:
{question}

Filters:
{filters}

SQL analysis tools:
{tools}
""".strip()

ANALYST_SQL_RESPONSE_PROMPT = """
Summarize verified SQL analysis for a Langbridge user.

Return STRICT JSON only:
{{
  "analysis": "<answer grounded in SQL, result, and outcome>"
}}

Rules:
- Do not invent rows or metrics.
- Do not claim success when outcome records an error or empty result.
- Mention empty results, validation failures, permission limits, and execution errors plainly.
- Explain the result in business terms first; mention SQL only when it clarifies scope or limits.
- If result rows are present, summarize the most important values and trends without fabricating causes.
- If the SQL only approximates the question, state that limit.

Question:
{question}

SQL:
{sql}

Result:
{result}

Outcome:
{outcome}
""".strip()

ANALYST_DEEP_RESEARCH_PROMPT = """
Synthesize source-backed research for a Langbridge user.

Return STRICT JSON only:
{{
  "synthesis": "<concise synthesis grounded only in provided sources>",
  "findings": [
    {{"insight": "<finding>", "source": "<exact source url or source id>"}}
  ],
  "follow_ups": ["<optional follow-up>"]
}}

Rules:
- Use only provided sources.
- Every finding must cite an exact source url or source id from Sources.
- Do not merge conflicting claims into one finding; call out disagreement or uncertainty.
- If evidence is weak, stale, duplicated, or one-sided, say what is missing in synthesis.
- Prefer concise synthesis over source-by-source summaries.
- Do not include uncited claims.
- Do not use outside knowledge.

Question:
{question}

Sources:
{sources}
""".strip()

__all__ = [
    "ANALYST_CONTEXT_ANALYSIS_PROMPT",
    "ANALYST_DEEP_RESEARCH_PROMPT",
    "ANALYST_MODE_SELECTION_PROMPT",
    "ANALYST_SQL_RESPONSE_PROMPT",
    "ANALYST_SQL_TOOL_SELECTION_PROMPT",
]
