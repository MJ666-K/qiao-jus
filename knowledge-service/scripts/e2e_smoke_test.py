#!/usr/bin/env python3
"""End-to-end smoke test with printed report.

Usage:
  cd knowledge-service
  ./scripts/e2e_smoke_test.py

Env: KS_API (default http://localhost:8000)
"""
from __future__ import annotations

import os
import sys
import time

import httpx

API = os.environ.get("KS_API", "http://localhost:8000").rstrip("/")
EMAIL = os.environ.get("KS_EMAIL", "seed@demo.com")
PASSWORD = os.environ.get("KS_PASSWORD", "seed12345")

PASS = 0
FAIL = 0


def ok(name: str, detail: str = "") -> None:
    global PASS
    PASS += 1
    print(f"  ✅ {name}" + (f" — {detail}" if detail else ""))


def bad(name: str, detail: str = "") -> None:
    global FAIL
    FAIL += 1
    print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{'='*60}\n{title}\n{'='*60}")


def main() -> int:
    print(f"API: {API}")
    section("1. 健康检查")
    try:
        r = httpx.get(f"{API}/health", timeout=10)
        if r.status_code == 200 and r.json().get("status") == "ok":
            ok("GET /health", r.text)
        else:
            bad("GET /health", r.text)
    except Exception as e:
        bad("GET /health", str(e))
        print("\n请先启动后端: cd knowledge-service && ./scripts/start.sh")
        return 1

    section("2. 登录")
    token = ""
    try:
        r = httpx.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
        if r.status_code != 200:
            bad("POST /auth/login", r.text)
        else:
            token = r.json()["access_token"]
            ok("POST /auth/login", EMAIL)
    except Exception as e:
        bad("POST /auth/login", str(e))
        return 1

    headers = {"Authorization": f"Bearer {token}"}

    section("3. 知识库与文档状态")
    try:
        stats = httpx.get(f"{API}/stats", headers=headers, timeout=15).json()
        ok("GET /stats", f"文档 {stats['documents']} / 完成 {stats['documents_done']} / chunks {stats['chunks']}")
        if stats["documents_done"] == 0:
            bad("文档入库", "无 done 状态文档，请先运行 ./scripts/seed_platform_data.py 并等待 Worker 处理")
    except Exception as e:
        bad("GET /stats", str(e))

    section("4. 等待文档处理 (最多 3 分钟)")
    done_count = 0
    for i in range(18):
        docs = httpx.get(f"{API}/documents", headers=headers, params={"limit": 50}, timeout=15).json()
        done_count = sum(1 for d in docs if d["status"] == "done")
        failed = [d for d in docs if d["status"] == "failed"]
        print(f"  … 轮询 {i+1}: done={done_count}/{len(docs)} failed={len(failed)}")
        if failed:
            for d in failed[:3]:
                print(f"     ⚠ {d['title']}: {d.get('error','')[:120]}")
        if done_count >= 5:
            ok("文档处理", f"{done_count} 篇已完成")
            break
        time.sleep(10)
    else:
        bad("文档处理超时", f"仅 {done_count} 篇 done，Worker 可能仍在跑 LLM 建图")

    section("5. Hybrid 检索 (法规)")
    try:
        r = httpx.post(
            f"{API}/search",
            headers=headers,
            json={"query": "用人单位解除劳动合同的情形", "doc_type": "law", "top_k": 3},
            timeout=60,
        )
        if r.status_code != 200:
            bad("POST /search", r.text[:300])
        else:
            hits = r.json().get("hits", [])
            if hits:
                ok("法规检索", f"命中 {len(hits)} 条，首条: {hits[0].get('source','')[:50]}")
                print(f"     预览: {hits[0]['text'][:120]}…")
            else:
                bad("法规检索", "无命中（可能 embedding 未完成或 API key 无效）")
    except Exception as e:
        bad("POST /search", str(e))

    section("6. 图谱局部查询")
    for q in ("物业服务合同", "试用期", "违法解除劳动合同"):
        try:
            r = httpx.post(
                f"{API}/graph/local",
                headers=headers,
                json={"query": q, "depth": 2},
                timeout=90,
            )
            if r.status_code != 200:
                bad(f"POST /graph/local [{q}]", r.text[:200])
            else:
                ents = r.json().get("entities", [])
                if ents:
                    ok(f"图谱 [{q}]", f"命中 {len(ents)} 个实体，如 {ents[0].get('name','')}")
                else:
                    bad(f"图谱 [{q}]", "无实体（可运行 seed 脚本导入 CSV 并等待文档 done）")
        except Exception as e:
            bad(f"POST /graph/local [{q}]", str(e))

    section("7. 问答")
    try:
        r = httpx.post(
            f"{API}/search/answer",
            headers=headers,
            json={"query": "试用期最长多久？", "doc_type": "law", "top_k": 5},
            timeout=120,
        )
        if r.status_code != 200:
            bad("POST /search/answer", r.text[:300])
        else:
            ans = r.json().get("answer", "")
            if ans.strip():
                ok("问答", f"回答 {len(ans)} 字")
                print(f"     {ans[:200]}…")
            else:
                bad("问答", "空回答")
    except Exception as e:
        bad("POST /search/answer", str(e))

    section("8. 前端代理 (可选)")
    for port in (5173, 5174):
        try:
            r = httpx.get(f"http://localhost:{port}/api/health", timeout=3)
            if r.status_code == 200:
                ok(f"前端 :{port} → /api 代理", r.text)
                break
        except Exception:
            continue
    else:
        bad("前端代理", "5173/5174 均未响应，请 cd frontend && npm run dev")

    section("汇总")
    print(f"  通过: {PASS}  失败: {FAIL}")
    if FAIL:
        print("\n排查建议:")
        print("  1. tail -f /tmp/ks_worker.log  看 Celery 是否在跑")
        print("  2. 检查 .env 中 LLM_API_KEY 是否有效")
        print("  3. ./scripts/seed_platform_data.py  导入测试数据")
        print("  4. 前端地址看 vite 输出（可能是 http://localhost:5174）")
        return 1
    print("\n🎉 全部通过。浏览器打开前端，用 seed@demo.com / seed12345 登录。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
