#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

try:
    import faiss  # type: ignore
except ImportError as exc:  # pragma: no cover - local dependency
    raise SystemExit("faiss is required (pip install faiss-cpu)") from exc

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - local dependency
    raise SystemExit("numpy is required (pip install numpy)") from exc


DEFAULT_OPENAI_BASE_URL = "https://api.openai.com"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_AZURE_API_VERSION = "2024-05-01-preview"


def _resolve_index_paths(index_path: str) -> tuple[Path, Path]:
    path = Path(index_path).expanduser()
    if path.is_dir():
        index_file = path / "index.faiss"
    else:
        index_file = path
    if not index_file.exists():
        raise FileNotFoundError(f"FAISS index not found at {index_file}")
    metadata_file = index_file.with_name(index_file.name + ".meta.json")
    return index_file, metadata_file


def _load_metadata(metadata_file: Path) -> dict[int, Any]:
    if not metadata_file.exists():
        return {}
    raw = json.loads(metadata_file.read_text())
    metadata = raw.get("metadata")
    if isinstance(metadata, dict):
        return {int(key): value for key, value in metadata.items()}
    if isinstance(metadata, list):
        parsed: dict[int, Any] = {}
        for entry in metadata:
            if not isinstance(entry, dict) or "id" not in entry:
                continue
            parsed[int(entry["id"])] = entry.get("metadata")
        return parsed
    return {}


def _parse_metadata_filters(value: Optional[str]) -> Optional[dict[str, Any]]:
    if not value:
        return None
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("Metadata filters must be a JSON object.")
    return parsed or None


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm


def _embed_openai(text: str, api_key: str, model: str, base_url: str) -> list[float]:
    url = f"{base_url.rstrip('/')}/v1/embeddings"
    payload = json.dumps({"model": model, "input": text}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI embeddings request failed: {detail}") from exc
    if "error" in data:
        raise RuntimeError(f"OpenAI embeddings error: {data['error']}")
    return list(data["data"][0]["embedding"])


def _embed_azure(
    text: str,
    api_key: str,
    endpoint: str,
    deployment: str,
    api_version: str,
) -> list[float]:
    url = (
        f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/embeddings"
        f"?api-version={api_version}"
    )
    payload = json.dumps({"input": text}).encode("utf-8")
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Azure embeddings request failed: {detail}") from exc
    if "error" in data:
        raise RuntimeError(f"Azure embeddings error: {data['error']}")
    return list(data["data"][0]["embedding"])


def _resolve_api_key(provider: str, explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    if provider == "openai":
        env_key = os.environ.get("OPENAI_API_KEY")
    else:
        env_key = os.environ.get("AZURE_OPENAI_API_KEY")
    if not env_key:
        raise ValueError("API key missing. Provide --api-key or set the provider env var.")
    return env_key


def _load_query_vector(args: argparse.Namespace) -> list[float]:
    if args.query_vector_file:
        raw = json.loads(Path(args.query_vector_file).read_text())
    elif args.query_vector:
        raw = json.loads(args.query_vector)
    else:
        raw = None

    if raw is None:
        api_key = _resolve_api_key(args.provider, args.api_key)
        if args.provider == "openai":
            model = args.embedding_model or DEFAULT_OPENAI_EMBEDDING_MODEL
            base_url = args.openai_base_url or DEFAULT_OPENAI_BASE_URL
            return _embed_openai(args.query_text, api_key, model, base_url)
        endpoint = args.azure_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
        deployment = args.azure_deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT")
        if not endpoint or not deployment:
            raise ValueError("Azure requires --azure-endpoint and --azure-deployment.")
        api_version = args.api_version or DEFAULT_AZURE_API_VERSION
        return _embed_azure(args.query_text, api_key, endpoint, deployment, api_version)

    if isinstance(raw, dict) and "embedding" in raw:
        raw = raw["embedding"]
    if not isinstance(raw, list):
        raise ValueError("Query vector must be a JSON array of floats.")
    return [float(value) for value in raw]


def _matches_filters(metadata: Any, filters: dict[str, Any]) -> bool:
    if not isinstance(metadata, dict):
        return False
    return all(item in metadata.items() for item in filters.items())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standalone FAISS search tester.")
    parser.add_argument("--index-path", required=True, help="Path to index.faiss or its directory.")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results to return.")
    parser.add_argument("--query-text", help="Text query to embed (requires provider API key).")
    parser.add_argument("--query-vector", help="JSON array for the query vector.")
    parser.add_argument("--query-vector-file", help="File containing a JSON array for the query vector.")
    parser.add_argument("--no-normalize", action="store_true", help="Skip vector normalization.")
    parser.add_argument("--metadata-filters", help='JSON object of exact-match filters.')
    parser.add_argument("--json", action="store_true", help="Output results as JSON.")
    parser.add_argument(
        "--provider",
        choices=("openai", "azure"),
        default="openai",
        help="Embedding provider when using --query-text.",
    )
    parser.add_argument("--api-key", help="API key for embeddings.")
    parser.add_argument("--embedding-model", help="OpenAI embedding model.")
    parser.add_argument("--openai-base-url", help="OpenAI API base URL.")
    parser.add_argument("--azure-endpoint", help="Azure OpenAI endpoint.")
    parser.add_argument("--azure-deployment", help="Azure embedding deployment name.")
    parser.add_argument("--api-version", help="Azure API version.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not args.query_text and not args.query_vector and not args.query_vector_file:
        raise SystemExit("Provide --query-text or --query-vector/--query-vector-file.")
    if args.query_text and (args.query_vector or args.query_vector_file):
        raise SystemExit("Use only one of --query-text or --query-vector/--query-vector-file.")

    index_file, metadata_file = _resolve_index_paths(args.index_path)
    index = faiss.read_index(str(index_file))
    metadata_map = _load_metadata(metadata_file)
    filters = _parse_metadata_filters(args.metadata_filters)

    query_vector = np.asarray(_load_query_vector(args), dtype="float32")
    if query_vector.ndim != 1:
        raise SystemExit("Query vector must be a 1D array.")
    if not args.no_normalize:
        query_vector = _normalize(query_vector)

    dimension = getattr(index, "d", None)
    if dimension and query_vector.shape[0] != dimension:
        raise SystemExit(f"Query dimension {query_vector.shape[0]} != index dimension {dimension}.")

    distances, indices = index.search(query_vector.reshape(1, -1), args.top_k)
    results = []
    for idx, score in zip(indices[0], distances[0]):
        if idx == -1:
            continue
        metadata = metadata_map.get(int(idx))
        if filters and not _matches_filters(metadata, filters):
            continue
        results.append({"id": int(idx), "score": float(score), "metadata": metadata})

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print(f"Index: {index_file}")
    if metadata_file.exists():
        print(f"Metadata: {metadata_file}")
    if dimension:
        print(f"Index dimension: {dimension}")
    if filters:
        print(f"Metadata filters: {filters}")
    print(f"Top-k requested: {args.top_k}")
    print(f"Results: {len(results)}")
    for offset, result in enumerate(results, start=1):
        print(f"{offset}. score={result['score']} id={result['id']} metadata={result['metadata']}")


if __name__ == "__main__":
    main()
