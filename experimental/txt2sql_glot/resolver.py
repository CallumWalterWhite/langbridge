from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from model import SemanticModel, Table, Dimension, Measure, TableFilter, Relationship, Metric

@dataclass
class ResolvedModel:
    model: SemanticModel
    # Canonical registries
    table_by_token: Dict[str, str]           # token -> canonical table name
    column_by_token: Dict[str, Tuple[str,str]]  # token -> (table, column)
    filter_by_token: Dict[str, Tuple[str,str]]  # token -> (table, filter_key)
    metric_by_token: Dict[str, str]          # token -> metric key

def _add_token(mapping: Dict[str, str], token: Optional[str], value: str):
    if not token:
        return
    mapping[token.lower()] = value

def _add_token_pair(mapping: Dict[str, Tuple[str, str]], token: Optional[str], table: str, column: str):
    if not token:
        return
    mapping[token.lower()] = (table, column)

def _explode_synonyms(names: List[Optional[str]]) -> List[str]:
    out: List[str] = []
    for n in names:
        if not n:
            continue
        out.append(n)
        # Split common multi-alias comma separated strings if someone provided them
        if "," in n:
            out.extend([x.strip() for x in n.split(",")])
    return out

def build_resolved_model(model: SemanticModel) -> ResolvedModel:
    table_by_token: Dict[str, str] = {}
    column_by_token: Dict[str, Tuple[str,str]] = {}
    filter_by_token: Dict[str, Tuple[str,str]] = {}
    metric_by_token: Dict[str, str] = {}

    # Tables + synonyms
    for tname, table in model.tables.items():
        _add_token(table_by_token, tname, tname)
        if table.synonyms:
            for syn in table.synonyms:
                _add_token(table_by_token, syn, tname)

        # Dimensions
        for dim in (table.dimensions or []):
            # canonical tokens
            dim_tokens = [dim.name, dim.alias] + (dim.synonyms or [])
            for tok in _explode_synonyms(dim_tokens):
                _add_token_pair(column_by_token, tok, tname, dim.name)

        # Measures
        for meas in (table.measures or []):
            _add_token_pair(column_by_token, meas.name, tname, meas.name)

        # Filters
        for fkey, tf in (table.filters or {}).items():
            _add_token(filter_by_token, fkey, (tname, fkey))  # type: ignore[arg-type]
            if tf.synonyms:
                for syn in tf.synonyms:
                    _add_token(filter_by_token, syn, (tname, fkey))  # type: ignore[arg-type]

    # Metrics
    for mkey, m in (model.metrics or {}).items():
        _add_token(metric_by_token, mkey, mkey)

    # Also allow column references qualified as table.column
    for tname, table in model.tables.items():
        for dim in (table.dimensions or []):
            _add_token_pair(column_by_token, f"{tname}.{dim.name}", tname, dim.name)
        for meas in (table.measures or []):
            _add_token_pair(column_by_token, f"{tname}.{meas.name}", tname, meas.name)

    return ResolvedModel(
        model=model,
        table_by_token=table_by_token,
        column_by_token=column_by_token,
        filter_by_token=filter_by_token,
        metric_by_token=metric_by_token,
    )
