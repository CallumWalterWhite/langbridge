# Local SDK Semantic Query Notebook

This example is a notebook-first walkthrough for the local SDK adapter.

It uses the SDK against the real local runtime service composition.

It exercises:

- `LangbridgeClient`
- `client.datasets.list()`
- `client.datasets.query(dataset_id=...)`
- `client.semantic.query()`
- `client.sql.query()`
- `client.agents.ask()`

The notebook runs entirely against a local SQLite demo warehouse through the SDK's local runtime adapter. It is set up as a small but believable commerce analytics sandbox rather than a toy hello-world.

## What is in this example

- [example.ipynb](/home/callumwhi/langbridge/examples/sdk/semantic_query/example.ipynb)
  A Jupyter notebook that previews datasets, runs analytical SQL, and asks an analytics agent for a natural-language summary.
- [setup.py](/home/callumwhi/langbridge/examples/sdk/semantic_query/setup.py)
  Seeds a richer local commerce database with generated customers, products, orders, order items, support tickets, and an `orders_enriched` analytics view.
- [langbridge_config.yml](/home/callumwhi/langbridge/examples/sdk/semantic_query/langbridge_config.yml)
  Defines the local runtime, sqlite connector, semantic model, local LLM connection, and default analytics agent.
- [example_sdk_usage.py](/home/callumwhi/langbridge/examples/sdk/semantic_query/example_sdk_usage.py)
  Shows the intended async SDK flow with `LangbridgeClient.local(config_path=...)`, including preview, semantic query, direct SQL, and agent-style querying.

## Install

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install notebook ipykernel pandas matplotlib
```

`LangbridgeClient.local(...)` boots the runtime, federation, and connector packages as part of the example flow, so installing the repository root is the simplest way to ensure dependencies like `duckdb`, `pyarrow`, and connector runtimes are present.

To enable the real local analytics agent, export an LLM key before running the example:

```bash
export OPENAI_API_KEY=...
```

Register the environment as a notebook kernel if needed:

```bash
python -m ipykernel install --user --name langbridge-sdk-demo --display-name "Langbridge SDK Demo"
```

## Run the example

Seed the local warehouse:

```bash
python examples/sdk/semantic_query/setup.py
```

The setup script recreates `example.db` on each run so the example stays repeatable.

The setup script creates:

- 36 customers across multiple countries, tiers, and segments
- 10 products across apparel, footwear, and accessories
- 198 orders with generated order items, discounts, refunds, and channel mix
- 47 support tickets linked to customer activity
- An `orders_enriched` view for analytics-style querying

Start Jupyter:

```bash
jupyter notebook examples/sdk/semantic_query/example.ipynb
```

## What the notebook demonstrates

1. Bootstrapping a local runtime instance with `LangbridgeClient.local(config_path="langbridge_config.yml")`
2. Listing configured datasets with `client.datasets.list()`
3. Previewing a configured dataset through the runtime dataset service
4. Querying `commerce_performance` semantically with `client.semantic.query(...)`
5. Running analytical SQL against the local warehouse with `client.sql.query(...)`
6. Asking a configured local analytics agent for semantic-style summaries with `client.agents.ask(...)`

## Notes

- This example is local-runtime only. It does not depend on the remote API adapter.
- The config-backed local runtime now boots real dataset, semantic, SQL, and agent runtime services rather than shortcut paths.
- The agent examples are grounded in the seeded data and use the agent plus LLM connection declared in `langbridge_config.yml`.
- The config file in this folder is illustrative and aligned with the seeded warehouse structure.
