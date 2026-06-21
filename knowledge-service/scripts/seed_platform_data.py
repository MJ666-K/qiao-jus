#!/usr/bin/env python3
"""Seed platform knowledge base from docs/data test fixtures.

Usage:
  cd knowledge-service
  ./scripts/seed_platform_data.py

Env:
  KS_API       default http://localhost:8000
  KS_EMAIL     default seed@demo.com
  KS_PASSWORD  default seed12345
  DATA_DIR     default ../docs/data
"""
from __future__ import annotations

import os
import sys
import csv
from pathlib import Path

import httpx

API = os.environ.get("KS_API", "http://localhost:8000").rstrip("/")
EMAIL = os.environ.get("KS_EMAIL", "seed@demo.com")
PASSWORD = os.environ.get("KS_PASSWORD", "seed12345")
DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[2] / "docs" / "data"))

DATASETS = [
    {
        "name": "平台法规库",
        "description": "法律法规条文，按「第X条」切分入库",
        "metadata": {"scope": "platform", "doc_type": "law", "domain": "综合"},
        "dir": "laws",
        "doc_type": "law",
    },
    {
        "name": "平台类案库",
        "description": "裁判文书与典型案例",
        "metadata": {"scope": "platform", "doc_type": "case"},
        "dir": "cases",
        "doc_type": "case",
    },
    {
        "name": "平台合规库",
        "description": "合规义务与检查清单",
        "metadata": {"scope": "platform", "doc_type": "compliance"},
        "dir": "compliance",
        "doc_type": "compliance",
    },
]


def main() -> int:
    if not DATA_DIR.is_dir():
        print(f"ERROR: data dir not found: {DATA_DIR}", file=sys.stderr)
        return 1

    with httpx.Client(base_url=API, timeout=120.0) as client:
        token = _login_or_register(client)
        headers = {"Authorization": f"Bearer {token}"}

        existing = {d["name"]: d for d in client.get("/datasets", headers=headers).json()}
        for spec in DATASETS:
            ds = existing.get(spec["name"])
            if not ds:
                ds = client.post(
                    "/datasets",
                    headers=headers,
                    json={
                        "name": spec["name"],
                        "description": spec["description"],
                        "metadata": spec["metadata"],
                    },
                ).json()
                print(f"✔ 创建知识库: {ds['name']} ({ds['id'][:8]})")
            else:
                print(f"→ 复用知识库: {ds['name']} ({ds['id'][:8]})")

            folder = DATA_DIR / spec["dir"]
            if not folder.is_dir():
                print(f"  ⚠ 跳过空目录: {folder}")
                continue
            for fp in sorted(folder.glob("*.md")):
                _upload(client, headers, ds["id"], fp, spec["doc_type"])

        _seed_graph_csv(headers, client)

    print("\n✅ 种子数据已提交。请在文档页等待 Celery 处理完成（status=done）。")
    return 0


def _seed_graph_csv(headers: dict, client: httpx.Client) -> None:
    csv_path = DATA_DIR / "graph" / "cause_evidence.csv"
    if not csv_path.is_file():
        return
    me = client.get("/auth/me", headers=headers).json()
    tenant_id = me.get("tenant_id") or (me.get("user") or {}).get("tenant_id")
    if not tenant_id:
        print("  ⚠ 无法获取 tenant_id，跳过图谱 CSV 导入")
        return
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from storage.neo4j_client import sync_seed_cause_evidence

    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    n = sync_seed_cause_evidence(tenant_id, rows)
    print(f"✔ 图谱 CSV 导入 {n} 条案由-证据关系")


def _login_or_register(client: httpx.Client) -> str:
    r = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if r.status_code == 200:
        print(f"✔ 登录: {EMAIL}")
        return r.json()["access_token"]
    r = client.post(
        "/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "tenant_name": "platform-seed"},
    )
    r.raise_for_status()
    print(f"✔ 注册并登录: {EMAIL}")
    return r.json()["access_token"]


def _upload(client: httpx.Client, headers: dict, dataset_id: str, path: Path, doc_type: str) -> None:
    with path.open("rb") as f:
        r = client.post(
            f"/documents/upload?dataset_id={dataset_id}&doc_type={doc_type}",
            headers=headers,
            files={"file": (path.name, f, "text/markdown")},
        )
    if r.status_code >= 400:
        print(f"  ✖ {path.name}: {r.text}")
        return
    doc = r.json()
    print(f"  ↑ {path.name} → {doc['id'][:8]} ({doc['status']})")


if __name__ == "__main__":
    raise SystemExit(main())
