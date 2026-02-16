#!/usr/bin/env python3
"""Generate API client collections from FastAPI router source."""
import ast
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


GROUP_NAMES = {
    "auth.py": "Auth",
    "organizations.py": "Organizations",
    "connectors.py": "Connectors",
    "semantic_models.py": "Semantic Models",
    "semantic_query.py": "Semantic Query",
    "threads.py": "Threads",
    "agents.py": "Agents",
    "bi_dashboards.py": "BI Dashboards",
    "copilot.py": "Copilot",
    "messages.py": "Messages",
    "jobs.py": "Jobs",
}

PATH_VAR_MAP = {
    "organization_id": "ORGANIZATION_ID",
    "project_id": "PROJECT_ID",
    "connector_id": "CONNECTOR_ID",
    "connector_type": "CONNECTOR_TYPE",
    "semantic_model_id": "MODEL_ID",
    "model_id": "MODEL_ID",
    "thread_id": "THREAD_ID",
    "agent_id": "AGENT_ID",
    "connection_id": "CONNECTION_ID",
    "dashboard_id": "DASHBOARD_ID",
    "job_id": "JOB_ID",
    "provider": "PROVIDER",
    "setting_key": "SETTING_KEY",
    "schema": "SCHEMA_NAME",
    "table": "TABLE_NAME",
}

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
STAMP_MS = 1760966400000


@dataclass(frozen=True)
class Endpoint:
    file_name: str
    group_name: str
    method: str
    path: str

    @property
    def display(self) -> str:
        return f"{self.method} {self.path}"

    @property
    def sort_key(self) -> str:
        return f"{self.path}:{self.method}"


def make_id(prefix: str, key: str) -> str:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def load_router_prefix(module: ast.Module) -> str:
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id != "router":
                continue
            call = node.value
            if not isinstance(call, ast.Call):
                continue
            if not isinstance(call.func, ast.Name) or call.func.id != "APIRouter":
                continue
            for kw in call.keywords:
                if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                    if isinstance(kw.value.value, str):
                        return kw.value.value
    return ""


def normalize_path(path: str) -> str:
    while "//" in path:
        path = path.replace("//", "/")
    return path


def extract_endpoints(routers_dir: Path) -> list[Endpoint]:
    endpoints: list[Endpoint] = []
    for file in sorted(routers_dir.glob("*.py")):
        if file.name == "__init__.py":
            continue
        module = ast.parse(file.read_text(encoding="utf-8"))
        router_prefix = load_router_prefix(module)
        group_name = GROUP_NAMES.get(file.name, file.stem.replace("_", " ").title())

        for node in module.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in node.decorator_list:
                if not isinstance(deco, ast.Call):
                    continue
                if not isinstance(deco.func, ast.Attribute):
                    continue
                if not isinstance(deco.func.value, ast.Name):
                    continue
                if deco.func.value.id != "router":
                    continue
                if deco.func.attr not in HTTP_METHODS:
                    continue

                sub_path = ""
                if deco.args and isinstance(deco.args[0], ast.Constant):
                    if isinstance(deco.args[0].value, str):
                        sub_path = deco.args[0].value

                full_path = normalize_path(f"/api/v1{router_prefix}{sub_path}")
                endpoints.append(
                    Endpoint(
                        file_name=file.name,
                        group_name=group_name,
                        method=deco.func.attr.upper(),
                        path=full_path,
                    )
                )
    return sorted(endpoints, key=lambda e: (e.group_name, e.sort_key))


def with_env_vars(path: str, style: str) -> str:
    for raw_name, env_name in PATH_VAR_MAP.items():
        if style == "insomnia":
            replacement = f"{{{{ _.{env_name} }}}}"
        elif style == "postman":
            replacement = f"{{{{{env_name}}}}}"
        else:
            raise ValueError(f"Unknown style: {style}")
        path = path.replace(f"{{{raw_name}}}", replacement)
    return path


def grouped(endpoints: Iterable[Endpoint]) -> dict[str, list[Endpoint]]:
    out: dict[str, list[Endpoint]] = defaultdict(list)
    for ep in endpoints:
        out[ep.group_name].append(ep)
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def generate_insomnia_yaml(endpoints: list[Endpoint]) -> str:
    lines: list[str] = [
        "type: collection.insomnia.rest/5.0",
        "name: Langbridge REST API",
        "meta:",
        f"  id: {make_id('wrk', 'langbridge-rest-api')}",
        f"  created: {STAMP_MS}",
        f"  modified: {STAMP_MS}",
        "  description: Complete Langbridge API collection generated from FastAPI routers",
        "collection:",
    ]

    for group_name, group_eps in grouped(endpoints).items():
        lines.extend(
            [
                f"  - name: {group_name}",
                "    meta:",
                f"      id: {make_id('fld', f'group:{group_name}')}",
                f"      created: {STAMP_MS}",
                f"      modified: {STAMP_MS}",
                '      description: ""',
                "    children:",
            ]
        )
        for ep in sorted(group_eps, key=lambda x: x.sort_key):
            raw_url = f"{{{{ _.BASE_URL }}}}{ep.path.lstrip('/')}"
            raw_url = with_env_vars(raw_url, "insomnia")
            req_id = make_id("req", f"{group_name}:{ep.method}:{ep.path}")
            lines.extend(
                [
                    f'      - url: "{raw_url}"',
                    f'        name: "{ep.method} {with_env_vars(ep.path, "insomnia")}"',
                    "        meta:",
                    f"          id: {req_id}",
                    f"          created: {STAMP_MS}",
                    f"          modified: {STAMP_MS}",
                    "          isPrivate: false",
                    '          description: ""',
                    "          sortKey: 0",
                    f"        method: {ep.method}",
                    "        headers:",
                    "          - name: User-Agent",
                    "            value: insomnia/11.6.0",
                    "          - name: Content-Type",
                    "            value: application/json",
                    "        settings:",
                    "          renderRequestBody: true",
                    "          encodeUrl: true",
                    "          followRedirects: global",
                    "          cookies:",
                    "            send: true",
                    "            store: true",
                    "          rebuildPath: true",
                ]
            )
            if ep.method in {"POST", "PUT", "PATCH"}:
                lines.extend(
                    [
                        "        body:",
                        "          mimeType: application/json",
                        "          text: |-",
                        "            {}",
                    ]
                )

    lines.extend(
        [
            "cookieJar:",
            "  name: Default Jar",
            "  meta:",
            f"    id: {make_id('jar', 'langbridge-default-jar')}",
            f"    created: {STAMP_MS}",
            f"    modified: {STAMP_MS}",
            "environments:",
            "  name: Base Environment",
            "  meta:",
            f"    id: {make_id('env', 'langbridge-base-env')}",
            f"    created: {STAMP_MS}",
            f"    modified: {STAMP_MS}",
            "    isPrivate: false",
            "  data:",
            "    BASE_URL: http://localhost:8000/",
            '    ORGANIZATION_ID: ""',
            '    PROJECT_ID: ""',
            '    CONNECTOR_ID: ""',
            '    MODEL_ID: ""',
            '    THREAD_ID: ""',
            '    AGENT_ID: ""',
            '    CONNECTION_ID: ""',
            '    DASHBOARD_ID: ""',
            '    JOB_ID: ""',
            '    CONNECTOR_TYPE: ""',
            "    PROVIDER: github",
            '    SETTING_KEY: ""',
            '    SCHEMA_NAME: ""',
            '    TABLE_NAME: ""',
            "    DEFAULT_HEADERS:",
            '      Authorization: "Bearer <token>"',
        ]
    )
    return "\n".join(lines) + "\n"


def generate_postman_json(endpoints: list[Endpoint]) -> dict:
    items: list[dict] = []
    for group_name, group_eps in grouped(endpoints).items():
        group_items: list[dict] = []
        for ep in sorted(group_eps, key=lambda x: x.sort_key):
            path = with_env_vars(ep.path, "postman")
            raw_url = "{{BASE_URL}}" + path
            request = {
                "name": f"{ep.method} {path}",
                "request": {
                    "method": ep.method,
                    "header": [
                        {"key": "Content-Type", "value": "application/json", "type": "text"},
                        {"key": "Authorization", "value": "Bearer {{TOKEN}}", "type": "text"},
                    ],
                    "url": {"raw": raw_url},
                },
                "response": [],
            }
            if ep.method in {"POST", "PUT", "PATCH"}:
                request["request"]["body"] = {
                    "mode": "raw",
                    "raw": "{}",
                    "options": {"raw": {"language": "json"}},
                }
            group_items.append(request)
        items.append({"name": group_name, "item": group_items})

    return {
        "info": {
            "_postman_id": make_id("pm", "langbridge-rest-api"),
            "name": "Langbridge REST API",
            "description": "Complete Langbridge API collection generated from FastAPI routers",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": items,
        "variable": [
            {"key": "BASE_URL", "value": "http://localhost:8000", "type": "string"},
            {"key": "TOKEN", "value": "", "type": "string"},
            {"key": "ORGANIZATION_ID", "value": "", "type": "string"},
            {"key": "PROJECT_ID", "value": "", "type": "string"},
            {"key": "CONNECTOR_ID", "value": "", "type": "string"},
            {"key": "MODEL_ID", "value": "", "type": "string"},
            {"key": "THREAD_ID", "value": "", "type": "string"},
            {"key": "AGENT_ID", "value": "", "type": "string"},
            {"key": "CONNECTION_ID", "value": "", "type": "string"},
            {"key": "DASHBOARD_ID", "value": "", "type": "string"},
            {"key": "JOB_ID", "value": "", "type": "string"},
            {"key": "CONNECTOR_TYPE", "value": "", "type": "string"},
            {"key": "PROVIDER", "value": "github", "type": "string"},
            {"key": "SETTING_KEY", "value": "", "type": "string"},
            {"key": "SCHEMA_NAME", "value": "", "type": "string"},
            {"key": "TABLE_NAME", "value": "", "type": "string"},
        ],
    }


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    routers_dir = repo_root / "langbridge" / "apps" / "api" / "langbridge_api" / "routers" / "v1"
    insomnia_path = repo_root / "docs" / "insomnia" / "langbridge_collection.yml"
    postman_path = repo_root / "docs" / "postman" / "langbridge_collection.json"

    endpoints = extract_endpoints(routers_dir)
    insomnia_path.parent.mkdir(parents=True, exist_ok=True)
    postman_path.parent.mkdir(parents=True, exist_ok=True)

    insomnia_path.write_text(generate_insomnia_yaml(endpoints), encoding="utf-8")
    postman_path.write_text(json.dumps(generate_postman_json(endpoints), indent=2) + "\n", encoding="utf-8")

    print(f"Generated {len(endpoints)} endpoints")
    print(f"Wrote {insomnia_path}")
    print(f"Wrote {postman_path}")


if __name__ == "__main__":
    main()
