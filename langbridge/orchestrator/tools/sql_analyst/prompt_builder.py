"""
Prompt construction for the SQL analyst tool.
"""
#TODO: remove

import json
import textwrap
from typing import Optional

import yaml

from semantic import SemanticModel

PROMPT_HEADER = """You are a SQL planner. Given:
1) a YAML semantic model; and
2) a natural-language request,
produce a SINGLE deterministic SQL query that sqlglot can parse. Output ONLY SQL in a fenced code block.
Rules:
- Fully qualify columns as table.column. No SELECT *.
- Use only relationships defined in the model; INNER JOIN by default.
- Expand metrics using their expression verbatim.
- Apply table filters when the request mentions their name or synonyms.
- Group only by non-aggregated selected dimensions.
- Prefer a single query; CTEs allowed: base_fact -> joined -> final.
- Do NOT invent columns/joins. If something is missing, omit it safely.
- Use ANSI-friendly constructs (CAST, COALESCE, CASE, DATE_PART, standard aggregates) that transpile cleanly.
- Avoid Postgres-only syntax such as :: type casts, EXTRACT(... FROM ...), DATE_TRUNC, ILIKE, array operators, or JSON-specific features.
- For date extracts, use datepart function instead.
"""


def build_prompt(model: SemanticModel, user_request: str, dialect: Optional[str] = None) -> str:
    """
    Construct the LLM prompt used to generate SQL from a semantic model.
    """

    yaml_text = yaml.safe_dump(json.loads(model.model_dump_json(by_alias=True)))
    dialect_part = f"Target dialect: {dialect}" if dialect else "Target dialect: ansi"
    example_hint = "Remember: output ONLY one SQL code fence."

    return textwrap.dedent(
        f"""
        {PROMPT_HEADER}

        {dialect_part}
        {example_hint}

        ### SEMANTIC MODEL (YAML)
        ```yaml
        {yaml_text}
        ```

        ### USER REQUEST
        {user_request}

        ### OUTPUT
        Provide only the SQL in a ```sql code fence.
        """
    ).strip()


__all__ = ["build_prompt"]
