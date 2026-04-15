import pathlib
import sys
import uuid

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[6]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from langbridge.orchestrator.tools.semantic_search.tool import SemanticSearchTool  # noqa: E402
from langbridge.runtime.services.semantic_vector_search_service import (  # noqa: E402
    SemanticVectorSearchHit,
)


class _RecordingSemanticVectorSearchService:
    def __init__(self, hits: list[SemanticVectorSearchHit]) -> None:
        self._hits = hits
        self.calls: list[dict[str, object]] = []

    async def search_dimension(
        self,
        *,
        workspace_id,
        semantic_model_id,
        dataset_key,
        dimension_name,
        queries,
        embedding_provider=None,
        top_k=5,
    ) -> list[SemanticVectorSearchHit]:
        self.calls.append(
            {
                "workspace_id": workspace_id,
                "semantic_model_id": semantic_model_id,
                "dataset_key": dataset_key,
                "dimension_name": dimension_name,
                "queries": list(queries),
                "embedding_provider": embedding_provider,
                "top_k": top_k,
            }
        )
        return list(self._hits)


@pytest.mark.anyio
async def test_semantic_search_tool_uses_runtime_semantic_vector_service() -> None:
    workspace_id = uuid.uuid4()
    semantic_model_id = uuid.uuid4()
    service = _RecordingSemanticVectorSearchService(
        [
            SemanticVectorSearchHit(
                index_id=uuid.uuid4(),
                semantic_model_id=semantic_model_id,
                dataset_key="orders",
                dimension_name="shipping_country",
                matched_value="France",
                score=0.97,
                source_text="French market",
            )
        ]
    )
    tool = SemanticSearchTool(
        semantic_name="orders_model:orders.shipping_country",
        logger=None,
        semantic_vector_search_service=service,
        semantic_vector_search_workspace_id=workspace_id,
        semantic_vector_search_model_id=semantic_model_id,
        semantic_vector_search_dataset_key="orders",
        semantic_vector_search_dimension_name="shipping_country",
        embedding_provider=None,
    )

    results = await tool.search("orders from the French market", top_k=3)

    assert service.calls == [
        {
            "workspace_id": workspace_id,
            "semantic_model_id": semantic_model_id,
            "dataset_key": "orders",
            "dimension_name": "shipping_country",
            "queries": ["orders from the French market"],
            "embedding_provider": None,
            "top_k": 3,
        }
    ]
    assert results.to_prompt_strings() == [
        "Column: orders.shipping_country, Value: France (Score: 0.9700)"
    ]
