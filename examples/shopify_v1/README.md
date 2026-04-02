# Shopify V1 Examples

This folder contains two focused Shopify examples for the explicit V1 dataset
model.

## Included Examples

- `live_resource_paths/`
  Demonstrates live API datasets with dataset-owned `source.resource`,
  explicit `source.flatten`, and explicit child-resource-path datasets.

- `sync_resource_paths/`
  Demonstrates synced API datasets with dataset-owned `sync.resource`,
  explicit `sync.flatten`, explicit child-resource-path datasets, and
  multiple sync commands.

## Shared Setup

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
pip install -e .
```

Export Shopify credentials for both examples:

```bash
export SHOPIFY_SHOP_DOMAIN=acme.myshopify.com
export SHOPIFY_ACCESS_TOKEN=shpat_...
```

If you need a helper to fetch an Admin API token, reuse the existing script in
`examples/shopify_sync/get_shopify_access_token.py`.
