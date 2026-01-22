import re
from datetime import date, datetime
from typing import Any, Optional, Tuple

from sqlglot import exp


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


def format_literal(
    value: Any,
    data_type: Optional[str] = None,
    dialect: str = "tsql",
) -> exp.Expression:
    dialect_key = (dialect or "tsql").lower()
    if value is None:
        return exp.Null()

    if isinstance(value, bool):
        if dialect_key in {"tsql", "sqlserver", "mssql"}:
            return exp.Literal.number(1 if value else 0)
        return exp.Boolean(this=value)

    if isinstance(value, (int, float)):
        return exp.Literal.number(value)

    if isinstance(value, (date, datetime)):
        return exp.Literal.string(value.isoformat())

    value_str = str(value)
    normalized_type = (data_type or "").strip().lower()

    if normalized_type in BOOLEAN_TYPES:
        lowered = value_str.lower()
        if lowered in {"true", "1", "yes"}:
            if dialect_key in {"tsql", "sqlserver", "mssql"}:
                return exp.Literal.number(1)
            return exp.Boolean(this=True)
        if lowered in {"false", "0", "no"}:
            if dialect_key in {"tsql", "sqlserver", "mssql"}:
                return exp.Literal.number(0)
            return exp.Boolean(this=False)

    if normalized_type in NUMERIC_TYPES and _is_numeric(value_str):
        return exp.Literal.number(value_str)

    return exp.Literal.string(value_str)


def date_trunc(granularity: str, column_expr: exp.Expression, dialect: str = "tsql") -> exp.Expression:
    unit = granularity.strip().lower()
    if unit in {"week", "month", "quarter", "year", "day", "hour", "minute", "second"}:
        if (dialect or "tsql").lower() in {"postgres", "postgresql"}:
            return exp.DateTrunc(this=column_expr, unit=exp.Literal.string(unit))
        unit_var = exp.Var(this=unit)
        base = exp.Literal.number(0)
        diff = exp.DateDiff(this=column_expr, expression=base, unit=unit_var)
        return exp.DateAdd(this=base, expression=diff, unit=unit_var)
    raise ValueError(f"Unsupported granularity '{granularity}'.")

def parse_relative_date_range(
    range_str: str, dialect: str = "tsql"
) -> Optional[Tuple[exp.Expression, exp.Expression]]:
    text = range_str.strip().lower()
    dialect_key = (dialect or "tsql").lower()
    if dialect_key in {"tsql", "sqlserver", "mssql"}:
        getdate = exp.Anonymous(this="GETDATE")
        current_date = exp.Cast(this=getdate, to=exp.DataType.build("date"))
        current_ts = getdate
    else:
        current_date = exp.CurrentDate()
        current_ts = exp.CurrentTimestamp()

    if text in {"today"}:
        start = current_date
        end = exp.DateAdd(this=current_date, expression=exp.Literal.number(1), unit=exp.Var(this="day"))
        return start, end
    if text in {"yesterday"}:
        start = exp.DateAdd(this=current_date, expression=exp.Literal.number(-1), unit=exp.Var(this="day"))
        end = current_date
        return start, end
    if text in {"tomorrow"}:
        start = exp.DateAdd(this=current_date, expression=exp.Literal.number(1), unit=exp.Var(this="day"))
        end = exp.DateAdd(this=current_date, expression=exp.Literal.number(2), unit=exp.Var(this="day"))
        return start, end
    if text in {"last_7_days"}:
        start = exp.DateAdd(this=current_date, expression=exp.Literal.number(-6), unit=exp.Var(this="day"))
        end = exp.DateAdd(this=current_date, expression=exp.Literal.number(1), unit=exp.Var(this="day"))
        return start, end
    if text in {"last_30_days"}:
        start = exp.DateAdd(this=current_date, expression=exp.Literal.number(-29), unit=exp.Var(this="day"))
        end = exp.DateAdd(this=current_date, expression=exp.Literal.number(1), unit=exp.Var(this="day"))
        return start, end
    if text in {"month_to_date"}:
        start = date_trunc("month", current_date, dialect=dialect)
        end = exp.DateAdd(this=current_date, expression=exp.Literal.number(1), unit=exp.Var(this="day"))
        return start, end
    if text in {"year_to_date"}:
        start = date_trunc("year", current_date, dialect=dialect)
        end = exp.DateAdd(this=current_date, expression=exp.Literal.number(1), unit=exp.Var(this="day"))
        return start, end

    match = _RELATIVE_RE.match(text)
    if match:
        direction, amount_str, unit = match.groups()
        amount = int(amount_str)
        unit_var = exp.Var(this=unit)
        if unit == "day":
            if direction == "last":
                start = exp.DateAdd(
                    this=current_date,
                    expression=exp.Literal.number(-max(amount - 1, 0)),
                    unit=unit_var,
                )
                end = exp.DateAdd(this=current_date, expression=exp.Literal.number(1), unit=unit_var)
                return start, end
            start = current_date
            end = exp.DateAdd(this=current_date, expression=exp.Literal.number(amount), unit=unit_var)
            return start, end

        if direction == "last":
            start = exp.DateAdd(this=current_ts, expression=exp.Literal.number(-amount), unit=unit_var)
            end = current_ts
            return start, end
        start = current_ts
        end = exp.DateAdd(this=current_ts, expression=exp.Literal.number(amount), unit=unit_var)
        return start, end

    match = _THIS_LAST_NEXT_RE.match(text)
    if match:
        direction, unit = match.groups()
        unit_var = exp.Var(this=unit)
        base = exp.DateDiff(this=current_ts, expression=exp.Literal.number(0), unit=unit_var)
        if direction == "this":
            start = exp.DateAdd(this=exp.Literal.number(0), expression=base, unit=unit_var)
            end = exp.DateAdd(this=exp.Literal.number(0), expression=exp.Add(this=base, expression=exp.Literal.number(1)), unit=unit_var)
            return start, end
        if direction == "last":
            start = exp.DateAdd(this=exp.Literal.number(0), expression=exp.Sub(this=base, expression=exp.Literal.number(1)), unit=unit_var)
            end = exp.DateAdd(this=exp.Literal.number(0), expression=base, unit=unit_var)
            return start, end
        start = exp.DateAdd(this=exp.Literal.number(0), expression=exp.Add(this=base, expression=exp.Literal.number(1)), unit=unit_var)
        end = exp.DateAdd(this=exp.Literal.number(0), expression=exp.Add(this=base, expression=exp.Literal.number(2)), unit=unit_var)
        return start, end

    return None

def build_date_range_condition(
    column_expr: exp.Expression,
    date_range: Any,
    data_type: Optional[str] = None,
    dialect: str = "tsql",
) -> exp.Expression:
    print(
        f"build_date_range_condition: column_expr={column_expr}, date_range={date_range}, "
        f"data_type={data_type}, dialect={dialect}"
    )
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start = format_literal(date_range[0], data_type, dialect=dialect)
        end = format_literal(date_range[1], data_type, dialect=dialect)
        return exp.and_(
            exp.GTE(this=column_expr, expression=start),
            exp.LTE(this=column_expr, expression=end),
        )

    if isinstance(date_range, str):
        relative = parse_relative_date_range(date_range, dialect=dialect)
        if relative:
            start, end = relative
            return exp.and_(
                exp.GTE(this=column_expr, expression=start),
                exp.LT(this=column_expr, expression=end),
            )
        return exp.EQ(
            this=column_expr,
            expression=format_literal(date_range, data_type, dialect=dialect),
        )

    raise ValueError("Unsupported date range format.")


def _is_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False
