import re
from typing import Optional
from loader import load_semantic_model_yaml
from resolver import build_resolved_model, ResolvedModel
from prompt_builder import build_prompt
from llm import LLM

SQL_FENCE_RE = re.compile(r"```sql\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)

def extract_sql_from_text(text: str) -> str:
    m = SQL_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    # Fallback: if the model returned bare SQL w/o fence
    return text.strip()

def generate_base_sql(
    semantic_model_yaml: str,
    user_request: str,
    llm: LLM,
    dialect: Optional[str] = None,
) -> str:
    """End-to-end: YAML -> prompt -> LLM -> SQL string."""
    model = load_semantic_model_yaml(semantic_model_yaml)
    _resolved: ResolvedModel = build_resolved_model(model)  # ready if you later want pre-hints
    prompt = build_prompt(model, user_request, dialect)
    raw = llm.complete(prompt)
    return extract_sql_from_text(raw)
