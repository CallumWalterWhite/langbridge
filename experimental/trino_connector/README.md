# Trino client test

Minimal Python helper for running ad-hoc queries against a Trino cluster using the official `trino` client.

## Setup
- (Optional) create a virtual environment: `python -m venv .venv && .\.venv\Scripts\activate`
- Install dependencies: `pip install -r requirements.txt`

## Usage
- Provide connection details via flags or environment variables, then pass the SQL to run:
  - `python main.py --host <coordinator> --port 8080 --user <user> --catalog hive --schema default "SELECT * FROM sample_table LIMIT 5"`
- To avoid putting secrets in your shell history, use `--password-prompt` instead of `--password`.
- Use `--sample-cross-query` to automatically run a join between the two demo data sources (see docker compose section below).

### Environment variables
- Shared connection: `TRINO_HOST`, `TRINO_PORT`, `TRINO_USER`, `TRINO_CATALOG`, `TRINO_SCHEMA`, `TRINO_HTTP_SCHEME`, `TRINO_VERIFY`
- Cross-source helpers: `TRINO_CATALOG_A`, `TRINO_SCHEMA_A`, `TRINO_TABLE_A`, `TRINO_CATALOG_B`, `TRINO_SCHEMA_B`, `TRINO_TABLE_B`, `TRINO_JOIN_COLUMN`
- CLI flags always override environment defaults.

### Notes
- For HTTPS endpoints with self-signed certs, pass `--no-verify` to skip TLS verification.
- The script prints column headers followed by rows separated by tabs; redirect output as needed.

## Local demo: two databases + Trino
Docker compose in this folder spins up Postgres and MySQL with sample data, plus Trino configured with two connectors.

1) From `trino_client_test/`, start the stack:  
   `docker compose up -d`

2) Once healthy, run a cross-source query with defaults (joins Postgres customers to MySQL orders):  
   `python main.py --host localhost --port 8080 --user trino --sample-cross-query`

3) Tweak catalogs/schemas/tables with flags if you change the compose setup, e.g. `--catalog-a postgres --schema-a public --table-a customers --catalog-b mysql --schema-b ordersdb --table-b orders`.

4) Tear down when finished:  
   `docker compose down -v`

### What the compose stack provides
- Postgres (`postgres` catalog) database `customersdb` with table `public.customers`.
- MySQL (`mysql` catalog) database/schema `ordersdb` with table `ordersdb.orders`.
- Trino at `localhost:8080` with connectors for both. No auth is configured by default.
