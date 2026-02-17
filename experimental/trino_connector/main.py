#!/usr/bin/env python3
import argparse
import os
from dataclasses import dataclass
from getpass import getpass
from typing import Optional

import trino
from trino.auth import BasicAuthentication


@dataclass
class ConnectorTarget:
    catalog: str
    schema: str
    table: Optional[str] = None

    def identifier(self) -> str:
        if self.table:
            return f"{self.catalog}.{self.schema}.{self.table}"
        return f"{self.catalog}.{self.schema}"


def getenv_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")


def build_parser() -> argparse.ArgumentParser:
    verify_default = getenv_bool("TRINO_VERIFY", True)
    parser = argparse.ArgumentParser(
        description="Run a single SQL query against a Trino cluster using the Python client.",
    )
    parser.add_argument("--host", default=os.getenv("TRINO_HOST", "localhost"), help="Trino coordinator host (env: TRINO_HOST)")
    parser.add_argument("--port", type=int, default=int(os.getenv("TRINO_PORT", "8080")), help="Trino coordinator port (env: TRINO_PORT)")
    parser.add_argument("--user", default=os.getenv("TRINO_USER", "trino"), help="Trino user (env: TRINO_USER)")
    parser.add_argument("--password", help="Password for basic auth; omit to connect without auth or use a prompt.")
    parser.add_argument("--password-prompt", action="store_true", help="Prompt for a password instead of passing it via CLI.")
    parser.add_argument("--catalog", default=os.getenv("TRINO_CATALOG", "system"), help="Target catalog (env: TRINO_CATALOG)")
    parser.add_argument("--schema", default=os.getenv("TRINO_SCHEMA", "information_schema"), help="Target schema (env: TRINO_SCHEMA)")
    parser.add_argument("--catalog-a", default=os.getenv("TRINO_CATALOG_A", "postgres"), help="First connector catalog (env: TRINO_CATALOG_A)")
    parser.add_argument("--schema-a", default=os.getenv("TRINO_SCHEMA_A", "public"), help="First connector schema (env: TRINO_SCHEMA_A)")
    parser.add_argument("--table-a", default=os.getenv("TRINO_TABLE_A", "customers"), help="First connector table for cross-source demo (env: TRINO_TABLE_A)")
    parser.add_argument("--catalog-b", default=os.getenv("TRINO_CATALOG_B", "mysql"), help="Second connector catalog (env: TRINO_CATALOG_B)")
    parser.add_argument("--schema-b", default=os.getenv("TRINO_SCHEMA_B", "ordersdb"), help="Second connector schema (env: TRINO_SCHEMA_B)")
    parser.add_argument("--table-b", default=os.getenv("TRINO_TABLE_B", "orders"), help="Second connector table for cross-source demo (env: TRINO_TABLE_B)")
    parser.add_argument("--join-column", default=os.getenv("TRINO_JOIN_COLUMN", "customer_id"), help="Join column shared between the two demo tables (env: TRINO_JOIN_COLUMN)")
    parser.add_argument("--sample-cross-query", action="store_true", help="Ignore --query and run a sample join across the two connectors using the provided catalogs/schemas/tables.")
    parser.add_argument("--http-scheme", choices=["http", "https"], default=os.getenv("TRINO_HTTP_SCHEME", "http"), help="HTTP scheme to use (env: TRINO_HTTP_SCHEME)")
    parser.add_argument("--verify", dest="verify", action="store_true", default=verify_default, help="Verify TLS certificates (default, env: TRINO_VERIFY).")
    parser.add_argument("--no-verify", dest="verify", action="store_false", help="Skip TLS verification when using https.")
    parser.add_argument("--tenant", default=os.getenv("TRINO_TENANT", "cw_tenant_123"), help="Tenant (env: TRINO_TENANT)")
    parser.add_argument("--source", default=os.getenv("TRINO_SOURCE", ""), help="Optional source id (env: TRINO_SOURCE)")
    parser.add_argument("query", nargs="?", help="SQL query to run; wrap in quotes when needed.")
    return parser


def create_connection(args: argparse.Namespace):
    password = args.password
    if args.password_prompt and password is None:
        password = getpass("Trino password: ")

    auth = BasicAuthentication(args.user, password) if password else None
    extra_credentials = [
        ("tenant", args.tenant)
    ]
    if args.source:
        extra_credentials.append(("source", args.source))

    return trino.dbapi.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        catalog=args.catalog,
        schema=args.schema,
        http_scheme=args.http_scheme,
        auth=auth,
        extra_credential=extra_credentials,
        verify=args.verify,
    )


def build_cross_source_query(left: ConnectorTarget, right: ConnectorTarget, join_column: str) -> str:
    return (
        "SELECT c.customer_id, c.name, c.region, "
        "COUNT(o.order_id) AS orders, "
        "COALESCE(SUM(o.order_total), 0) AS total_spend "
        f"FROM {left.identifier()} c "
        f"LEFT JOIN {right.identifier()} o "
        f"ON c.{join_column} = o.{join_column} "
        "GROUP BY c.customer_id, c.name, c.region "
        "ORDER BY total_spend DESC, c.customer_id"
    )

def sample_query(
):
    return """
    WITH cust AS (
        SELECT customer_id, name, region FROM postgres.public.customers
        ),
        ordr AS (
        SELECT customer_id,
                COUNT(*) AS order_count,
                SUM(order_total) AS total_spend,
                AVG(order_total) AS avg_order,
                MAX(order_total) AS max_order
        FROM mysql.ordersdb.orders
        WHERE status IN ('shipped','processing')
        GROUP BY customer_id
        ),
        combined AS (
        SELECT c.customer_id,
                c.name,
                c.region,
                COALESCE(o.order_count, 0) AS order_count,
                COALESCE(o.total_spend, 0) AS total_spend,
                COALESCE(o.avg_order, 0) AS avg_order,
                COALESCE(o.max_order, 0) AS max_order
        FROM cust c
        LEFT JOIN ordr o ON c.customer_id = o.customer_id
        )
        SELECT customer_id,
            name,
            region,
            order_count,
            total_spend,
            avg_order,
            max_order,
            RANK() OVER (PARTITION BY region ORDER BY total_spend DESC) AS rank_in_region
        FROM combined
        WHERE total_spend > 50
        ORDER BY total_spend DESC, customer_id
"""


def print_rows(cursor, rows):
    headers = [col[0] for col in cursor.description] if cursor.description else []
    if headers:
        print("\t".join(headers))
    for row in rows:
        print("\t".join("" if value is None else str(value) for value in row))


def main():
    parser = build_parser()
    args = parser.parse_args()

    connector_a = ConnectorTarget(args.catalog_a, args.schema_a, args.table_a)
    connector_b = ConnectorTarget(args.catalog_b, args.schema_b, args.table_b)

    if args.sample_cross_query:
        query = sample_query()
        print("Running sample cross-source query:")
        print(query)
    else:
        if not args.query:
            parser.error("Please provide a SQL query to run (or use --sample-cross-query).")
        query = args.query

    with create_connection(args) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        if not rows:
            print("Query executed successfully; no rows returned.")
        else:
            print_rows(cursor, rows)


if __name__ == "__main__":
    main()
