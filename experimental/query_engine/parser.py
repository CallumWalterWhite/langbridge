"""Tokenizer and parser for the LangBridge SQL-inspired query language."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence

from .exceptions import ParseError
from .model import (
    ColumnRef,
    JoinClause,
    Literal,
    Predicate,
    PredicateOperand,
    SelectItem,
    SelectQuery,
    TableReference,
    Wildcard,
)


@dataclass(frozen=True)
class Token:
    """A lexical token."""

    type: str
    value: str


TOKEN_PATTERN = re.compile(
    r"(?P<SPACE>\s+)"
    r"|(?P<STRING>'(?:''|[^'])*')"
    r"|(?P<NUMBER>\d+(?:\.\d+)?)"
    r"|(?P<IDENT>[A-Za-z_][\w$]*|`[^`]+`)"
    r"|(?P<COMMA>,)"
    r"|(?P<DOT>\.)"
    r"|(?P<LPAREN>\()"
    r"|(?P<RPAREN>\))"
    r"|(?P<ASTERISK>\*)"
    r"|(?P<OP><>|!=|<=|>=|=|<|>)"
)

KEYWORDS = {
    "SELECT",
    "FROM",
    "JOIN",
    "ON",
    "AS",
    "WHERE",
    "AND",
    "INNER",
    "LEFT",
    "RIGHT",
    "FULL",
}


def tokenize(sql: str) -> List[Token]:
    """Tokenize a query string into a sequence of :class:`Token` objects."""

    tokens: List[Token] = []
    position = 0
    length = len(sql)

    while position < length:
        match = TOKEN_PATTERN.match(sql, position)
        if not match:
            raise ParseError(f"Unexpected character at position {position}: {sql[position]!r}")

        kind = match.lastgroup
        text = match.group()
        position = match.end()

        if kind == "SPACE":
            continue
        if kind == "STRING":
            tokens.append(Token("STRING", text[1:-1].replace("''", "'")))
            continue
        if kind == "NUMBER":
            tokens.append(Token("NUMBER", text))
            continue
        if kind == "IDENT":
            value = text
            if value.startswith("`") and value.endswith("`"):
                value = value[1:-1]
            tokens.append(Token("IDENT", value))
            continue
        tokens.append(Token(kind, text))

    return tokens


def _is_keyword(token: Optional[Token], keyword: str) -> bool:
    return bool(token and token.type == "IDENT" and token.value.upper() == keyword)


class QueryParser:
    """Parse LangBridge SQL-like statements into :class:`SelectQuery` objects."""

    def __init__(self, tokens: Sequence[Token]):
        self._tokens = list(tokens)
        self._index = 0

    @classmethod
    def parse(cls, sql: str) -> SelectQuery:
        tokens = tokenize(sql)
        parser = cls(tokens)
        return parser._parse_select()

    # Basic token helpers ---------------------------------------------------

    def _peek(self) -> Optional[Token]:
        if self._index >= len(self._tokens):
            return None
        return self._tokens[self._index]

    def _advance(self) -> Token:
        token = self._peek()
        if token is None:
            raise ParseError("Unexpected end of input")
        self._index += 1
        return token

    def _match_type(self, token_type: str) -> Optional[Token]:
        token = self._peek()
        if token and token.type == token_type:
            self._advance()
            return token
        return None

    def _expect_type(self, token_type: str) -> Token:
        token = self._match_type(token_type)
        if not token:
            raise ParseError(f"Expected token {token_type}")
        return token

    def _match_keyword(self, keyword: str) -> bool:
        token = self._peek()
        if _is_keyword(token, keyword):
            self._advance()
            return True
        return False

    def _expect_keyword(self, keyword: str) -> None:
        if not self._match_keyword(keyword):
            raise ParseError(f"Expected keyword {keyword}")

    def _parse_identifier(self) -> str:
        token = self._expect_type("IDENT")
        return token.value

    # Grammar parsing -------------------------------------------------------

    def _parse_select(self) -> SelectQuery:
        self._expect_keyword("SELECT")
        select_items = self._parse_select_list()
        self._expect_keyword("FROM")
        from_table = self._parse_table_reference()

        joins: List[JoinClause] = []
        while True:
            join_clause = self._parse_optional_join()
            if not join_clause:
                break
            joins.append(join_clause)

        where_predicates = self._parse_optional_where()

        if self._peek() is not None:
            raise ParseError(f"Unexpected token {self._peek()!r} at end of query")

        return SelectQuery(
            select_items=select_items,
            from_table=from_table,
            joins=joins,
            where_predicates=where_predicates,
        )

    def _parse_select_list(self) -> List[SelectItem]:
        items: List[SelectItem] = []
        while True:
            items.append(self._parse_select_item())
            if not self._match_type("COMMA"):
                break
        return items

    def _parse_select_item(self) -> SelectItem:
        token = self._peek()
        if token is None:
            raise ParseError("Unexpected end of input in select list")

        if token.type == "ASTERISK":
            self._advance()
            return SelectItem(value=Wildcard())

        if token.type != "IDENT":
            raise ParseError(f"Unexpected token {token.value!r} in select list")

        identifier = self._parse_identifier()
        if self._match_type("DOT"):
            if self._match_type("ASTERISK"):
                alias = self._parse_optional_alias()
                return SelectItem(value=Wildcard(table_alias=identifier), alias=alias)
            column_name = self._parse_identifier()
            column_ref = ColumnRef(table_alias=identifier, column=column_name)
        else:
            raise ParseError("Column references must include a table alias (e.g. alias.column)")

        alias = self._parse_optional_alias()
        return SelectItem(value=column_ref, alias=alias)

    def _parse_optional_alias(self) -> Optional[str]:
        if self._match_keyword("AS"):
            return self._parse_identifier()

        token = self._peek()
        if token and token.type == "IDENT" and token.value.upper() not in KEYWORDS:
            return self._parse_identifier()
        return None

    def _parse_table_reference(self) -> TableReference:
        parts = self._parse_qualified_name()
        if len(parts) < 2:
            raise ParseError(
                "Table reference must include the data source and table name "
                "(e.g. bigquery.dataset.table)"
            )
        source = parts[0]
        path = tuple(parts[1:])
        alias = self._parse_optional_alias() or path[-1]
        return TableReference(source=source, path=path, alias=alias)

    def _parse_optional_join(self) -> Optional[JoinClause]:
        token = self._peek()
        if token is None:
            return None

        join_type = "INNER"
        if token.type == "IDENT":
            keyword = token.value.upper()
            if keyword in {"INNER", "LEFT", "RIGHT", "FULL"}:
                join_type = self._advance().value.upper()
                self._expect_keyword("JOIN")
            elif keyword == "JOIN":
                self._advance()
            else:
                return None
        else:
            return None

        table = self._parse_table_reference()
        self._expect_keyword("ON")
        predicates = [self._parse_predicate()]
        while self._match_keyword("AND"):
            predicates.append(self._parse_predicate())

        return JoinClause(join_type=join_type, table=table, predicates=predicates)

    def _parse_optional_where(self) -> List[Predicate]:
        if not self._match_keyword("WHERE"):
            return []

        predicates = [self._parse_predicate()]
        while self._match_keyword("AND"):
            predicates.append(self._parse_predicate())
        return predicates

    def _parse_predicate(self) -> Predicate:
        left = self._parse_predicate_operand()
        operator_token = self._match_type("OP")
        if not operator_token:
            raise ParseError("Expected comparison operator in predicate")
        right = self._parse_predicate_operand()
        return Predicate(left=left, operator=operator_token.value.upper(), right=right)

    def _parse_predicate_operand(self) -> PredicateOperand:
        token = self._peek()
        if token is None:
            raise ParseError("Unexpected end of input in predicate")

        if token.type == "STRING":
            self._advance()
            return Literal(token.value)

        if token.type == "NUMBER":
            self._advance()
            value: Any
            if "." in token.value:
                value = float(token.value)
            else:
                value = int(token.value)
            return Literal(value)

        if token.type == "IDENT":
            identifier = self._parse_identifier()
            if self._match_type("DOT"):
                column = self._parse_identifier()
                return ColumnRef(table_alias=identifier, column=column)
            upper = identifier.upper()
            if upper == "TRUE":
                return Literal(True)
            if upper == "FALSE":
                return Literal(False)
            if upper == "NULL":
                return Literal(None)
            raise ParseError(
                "Predicate columns must be qualified with a table alias (alias.column). "
                f"Found {identifier!r}."
            )

        raise ParseError(f"Unexpected token {token.value!r} in predicate")

    def _parse_qualified_name(self) -> List[str]:
        parts = [self._parse_identifier()]
        while self._match_type("DOT"):
            parts.append(self._parse_identifier())
        return parts


__all__ = [
    "QueryParser",
    "TOKEN_PATTERN",
    "Token",
    "tokenize",
]
