# SQL Analyst Tool

The SQL analyst tool follows a three-stage pipeline:

1. **Canonical SQL generation** – Convert the user request and semantic model metadata into a PostgreSQL SELECT statement using the configured LLM client.
2. **Transpile** – Convert the canonical PostgreSQL SQL into the target execution dialect via [`sqlglot.transpile`](https://github.com/tobymao/sqlglot).
3. **Execute** – Run the transpiled SQL through the injected connector abstraction and surface the result schema and rows.

The tool is configured with four dependencies:

| Dependency | Purpose |
|------------|---------|
| `LLMProvider` | Generates canonical PostgreSQL SQL from structured prompts. |
| `SemanticModel` | Describes entities, joins, metrics, and dimensions. Used to craft prompts and validate routing. |
| `DatabaseConnector` | Executes SQL against the backing data warehouse. |
| `dialect` | Target dialect for the connector (`"snowflake"`, `"bigquery"`, `"postgres"`, etc.). |

When `run()` (or `arun()`) is called with an `AnalystQueryRequest`, the tool:

1. Builds a structured prompt that includes the semantic model schema, available metrics/dimensions, and user filters.
2. Asks the LLM for **PostgreSQL SQL only** – no comments, prose, or DDL.
3. Validates the generated SQL with `sqlglot.parse_one` (read dialect `postgres`).
4. Transpiles the SQL to the configured dialect with `sqlglot.transpile`.
5. Executes the transpiled SQL via the connector.
6. Returns an `AnalystQueryResponse` containing canonical SQL, executable SQL, execution metadata, and query results.

Errors detected during validation, transpilation, or execution are wrapped into the response with a descriptive message while preserving canonical SQL for diagnosis.

