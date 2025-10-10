import sqlglot
from typing import Optional

def to_sqlglot_ast(sql: str, dialect: Optional[str] = None):
    """Parse SQL into a sqlglot AST."""
    read = dialect or "ansi"
    return sqlglot.parse_one(sql, read=read)