import asyncio
import os
from pathlib import Path
import sys

EXAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXAMPLE_DIR.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from langbridge import LangbridgeClient

from setup import setup_database

CONFIG_PATH = EXAMPLE_DIR / "langbridge_config.yml"


async def main() -> None:
    setup_database()

    client = LangbridgeClient.local(config_path=str(CONFIG_PATH))

    datasets = await client.datasets.list()
    print("Datasets")
    print(datasets.model_dump(mode="json"))

    preview = await client.datasets.query(
        dataset_id=datasets.items[0].id,
        limit=3,
    )
    print("Dataset preview")
    print(preview.model_dump(mode="json"))

    semantic_result = await client.semantic.query(
        "commerce_performance",
        measures=["shopify_orders.net_sales"],
        dimensions=["shopify_orders.country"],
        limit=5,
        order={"shopify_orders.net_sales": "desc"},
    )
    print("Semantic query")
    print(semantic_result.model_dump(mode="json"))

    sql_result = await client.sql.query(
        query=(
            "SELECT country, SUM(net_revenue) AS net_sales "
            "FROM orders_enriched "
            "GROUP BY country "
            "ORDER BY net_sales DESC"
        ),
        connection_name="commerce_demo",
    )
    print("Direct SQL query")
    print(sql_result.model_dump(mode="json"))

    if os.environ.get("OPENAI_API_KEY"):
        answer = await client.agents.ask("Show me top countries by net sales this quarter")
        print("Agent answer")
        print(answer.model_dump(mode="json"))
    else:
        print("Agent answer skipped because OPENAI_API_KEY is not set.")


if __name__ == "__main__":
    asyncio.run(main())
