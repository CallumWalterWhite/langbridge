# Local SDK Federated Query Notebook

This example shows the Langbridge local runtime federating three live sources at query time:

- a Postgres sales database
- a Postgres CRM database
- a local CSV with campaign attribution tags

The notebook demonstrates both direct federated SQL and semantic querying across those sources through `LangbridgeClient.local(...)`.

## What is in this example

- `docker-compose.yml`
  Starts the two Postgres databases and loads the seed data.
- `seeds/sales`
  Sales schema and seed scripts.
- `seeds/crm`
  CRM schema and seed scripts.
- `marketing_campaign.csv`
  Local campaign attribution data keyed by `contact_external_id`.
- `langbridge_config.yml`
  Local runtime config describing the three sources and the federated semantic model.
- `example.ipynb`
  Notebook walkthrough for dataset previews, semantic queries, and direct federated SQL.

## Install

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install notebook ipykernel pandas
```

Register a notebook kernel if needed:

```bash
python -m ipykernel install --user --name langbridge-sdk-demo --display-name "Langbridge SDK Demo"
```

## Start the source systems

From this example folder:

```bash
docker compose up -d --wait
```

This starts:

- `sales-db` on `localhost:5432`
- `crm-db` on `localhost:5433`

To tear the demo down later:

```bash
docker compose down -v
```

## Run the notebook

From the repository root:

```bash
jupyter notebook examples/sdk/federated_query/example.ipynb
```

## What the notebook demonstrates

1. Bootstrapping the local runtime with `LangbridgeClient.local(config_path="langbridge_config.yml")`
2. Previewing each source-backed dataset through the runtime dataset service
3. Running a semantic query that combines sales revenue with CRM segments and CSV campaign names
4. Running a direct federated SQL join across all three sources at runtime

## Join path

The example is intentionally keyed around the shared CRM contact identifier:

- `sales.customers.crm_contact_external_id`
- `crm.contacts.contact_external_id`
- `marketing_campaign.csv.contact_external_id`

That makes the federation story explicit: revenue lives in the sales database, lifecycle and segment live in the CRM database, and campaign tagging lives in the CSV.
