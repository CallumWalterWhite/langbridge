import re
from datetime import date, datetime
from typing import Any, Optional, Tuple


NUMERIC_TYPES = {"integer", "int", "decimal", "numeric", "float", "double", "real"}
BOOLEAN_TYPES = {"bool", "boolean"}
DATE_TYPES = {"date", "datetime", "timestamp", "time"}

_RELATIVE_RE = re.compile(r"^(last|next)\s+(\d+)\s+(day|week|month|quarter|year)s?$", re.I)
_THIS_LAST_NEXT_RE = re.compile(r"^(this|last|next)\s+(week|month|quarter|year)$", re.I)


def quote_identifier(value: str) -> str:
    escaped = value.replace("]", "]]")
    return f"[{escaped}]"


def quote_compound(value: str) -> str:
    parts = [part for part in value.split(".") if part]
    return ".".join(quote_identifier(part) for part in parts)


def format_literal(value: Any, data_type: Optional[str] = None) -> str:
    if value is None:
        return "NULL"

    if isinstance(value, bool):
        return "1" if value else "0"

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, (date, datetime)):
        return f"'{value.isoformat()}'"

    value_str = str(value)
    normalized_type = (data_type or "").strip().lower()

    if normalized_type in BOOLEAN_TYPES:
        if value_str.lower() in {"true", "1", "yes"}:
            return "1"
        if value_str.lower() in {"false", "0", "no"}:
            return "0"

    if normalized_type in NUMERIC_TYPES:
        if _is_numeric(value_str):
            return value_str

    escaped = value_str.replace("'", "''")
    return f"'{escaped}'"


def date_trunc(granularity: str, column_expr: str) -> str:
    unit = granularity.strip().lower()
    if unit in {"week", "month", "quarter", "year", "day", "hour", "minute", "second"}:
        return f"DATEADD({unit}, DATEDIFF({unit}, 0, {column_expr}), 0)"
    raise ValueError(f"Unsupported granularity '{granularity}'.")


def parse_relative_date_range(range_str: str) -> Optional[Tuple[str, str]]:
    text = range_str.strip().lower()
    current_date = "CAST(GETDATE() AS date)"
    current_ts = "GETDATE()"

    if text in {"today"}:
        start = current_date
        end = f"DATEADD(day, 1, {current_date})"
        return start, end
    if text in {"yesterday"}:
        start = f"DATEADD(day, -1, {current_date})"
        end = current_date
        return start, end
    if text in {"tomorrow"}:
        start = f"DATEADD(day, 1, {current_date})"
        end = f"DATEADD(day, 2, {current_date})"
        return start, end

    match = _RELATIVE_RE.match(text)
    if match:
        direction, amount_str, unit = match.groups()
        amount = int(amount_str)
        if unit == "day":
            if direction == "last":
                start = f"DATEADD(day, -{max(amount - 1, 0)}, {current_date})"
                end = f"DATEADD(day, 1, {current_date})"
                return start, end
            start = current_date
            end = f"DATEADD(day, {amount}, {current_date})"
            return start, end

        if direction == "last":
            start = f"DATEADD({unit}, -{amount}, {current_ts})"
            end = current_ts
            return start, end
        start = current_ts
        end = f"DATEADD({unit}, {amount}, {current_ts})"
        return start, end

    match = _THIS_LAST_NEXT_RE.match(text)
    if match:
        direction, unit = match.groups()
        base = f"DATEDIFF({unit}, 0, GETDATE())"
        if direction == "this":
            start = f"DATEADD({unit}, {base}, 0)"
            end = f"DATEADD({unit}, {base} + 1, 0)"
            return start, end
        if direction == "last":
            start = f"DATEADD({unit}, {base} - 1, 0)"
            end = f"DATEADD({unit}, {base}, 0)"
            return start, end
        start = f"DATEADD({unit}, {base} + 1, 0)"
        end = f"DATEADD({unit}, {base} + 2, 0)"
        return start, end

    return None


def build_date_range_condition(column_expr: str, date_range: Any, data_type: Optional[str] = None) -> str:
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start = format_literal(date_range[0], data_type)
        end = format_literal(date_range[1], data_type)
        return f"{column_expr} >= {start} AND {column_expr} <= {end}"

    if isinstance(date_range, str):
        relative = parse_relative_date_range(date_range)
        if relative:
            start, end = relative
            return f"{column_expr} >= {start} AND {column_expr} < {end}"
        # Fall back to equality if a single date string is provided.
        return f"{column_expr} = {format_literal(date_range, data_type)}"

    raise ValueError("Unsupported date range format.")


def _is_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False
