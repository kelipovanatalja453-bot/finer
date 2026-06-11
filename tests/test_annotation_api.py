"""Annotation API endpoint tests."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finer.api.server import create_app
from finer.schemas.annotation import ANNOTATION_SCHEMA_VERSION
from finer.services.annotation_store import AnnotationStore


REVIEWER = "api_reviewer"
PROMPT = "从以下文本提取 TradeAction：\n\n## 原文\n茅台 600519 目标价 2000 元\n\n## 提取要求\n..."


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    dpo = tmp_path / "dpo"
    eval_rows = [
        {
            "id": f"psg_a{i:02d}",
            "evidence_text": f"茅台 600519 目标价 {2000 + i} 元",
            "creator": "kol_x",
            "signals": {"signal_score": 2},
        }
        for i in range(20)
    ]
    pair_rows = [
        {
            "prompt": PROMPT,
            "chosen": json.dumps({"ticker": "600519", "direction": "bullish", "action_chain": [{"action_type": "long"}]}),
            "rejected": json.dumps({"ticker": "600519", "direction": "bullish", "action_chain": [{"action_type": "long", "target_price_low": 9999}]}),
            "meta": {"passage_id": f"psg_t{i:02d}"},
        }
        for i in range(3)
    ]
    write_jsonl(dpo / "eval" / "passages.jsonl", eval_rows)
    write_jsonl(dpo / "pairs.jsonl", pair_rows)

    import finer.api.routes.annotation as annotation_route

    monkeypatch.setattr(annotation_route, "_store", AnnotationStore(dpo_dir=dpo))
    return TestClient(create_app())


def gold_annotation(item_id: str):
    return {
        "id": item_id,
        "reviewer_id": REVIEWER,
        "annotation_schema_version": ANNOTATION_SCHEMA_VERSION,
        "sample_verdict": "gold",
        "expected_abstain": False,
        "gold": {
            "ticker": "600519",
            "direction": "bullish",
            "action_chain": [{"action_type": "long", "target_price_high": 2000.0}],
        },
    }


def pair_annotation(pair_id: str):
    return {
        "pair_id": pair_id,
        "reviewer_id": REVIEWER,
        "annotation_schema_version": ANNOTATION_SCHEMA_VERSION,
        "verdict": "accept",
    }


def test_tasks_and_enums_endpoints(client: TestClient):
    res = client.get("/api/annotation/tasks")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    tasks = {t["task_id"]: t for t in body["data"]["tasks"]}
    assert tasks["eval_gold"]["quality"]["incomplete_items"] == 20

    res = client.get("/api/annotation/enums")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["annotation_schema_version"] == ANNOTATION_SCHEMA_VERSION
    assert "bullish" in data["directions"]


def test_items_submit_and_formal_export_roundtrip(client: TestClient):
    res = client.get("/api/annotation/items", params={"task_id": "eval_gold", "status": "pending"})
    assert res.status_code == 200
    assert res.json()["data"]["total"] == 20

    for i in range(20):
        res = client.post(
            "/api/annotation/submit",
            json={"task_id": "eval_gold", "annotation": gold_annotation(f"psg_a{i:02d}")},
        )
        assert res.status_code == 200

    res = client.post("/api/annotation/export", json={"task_id": "eval_gold", "mode": "formal"})
    assert res.status_code == 200
    assert res.json()["data"]["exported"] == 20


def test_formal_export_blocked_error_envelope(client: TestClient):
    res = client.post("/api/annotation/export", json={"task_id": "eval_gold", "mode": "formal"})
    assert res.status_code >= 400
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["details"]["operation"] == "annotation_export"
    assert "formal export" in body["error"]["message"]


def test_submit_invalid_schema_error_envelope(client: TestClient):
    res = client.post(
        "/api/annotation/submit",
        json={
            "task_id": "eval_gold",
            "annotation": {
                "id": "psg_a00",
                "reviewer_id": REVIEWER,
                "annotation_schema_version": ANNOTATION_SCHEMA_VERSION,
                "sample_verdict": "gold",
                "expected_abstain": False,
                "gold": {"ticker": "X", "direction": "not_a_direction"},
            },
        },
    )
    assert res.status_code >= 400
    body = res.json()
    assert body["ok"] is False
    details = body["error"].get("details") or {}
    assert details.get("stage") == "F+"
    assert details.get("operation") == "annotation_submit"
    assert "fix_hint" in details


def test_pairs_review_flow_with_sample(client: TestClient):
    res = client.get(
        "/api/annotation/items",
        params={"task_id": "pairs_review", "sample_size": 2, "seed": 1},
    )
    items = res.json()["data"]["items"]
    assert len(items) == 2
    assert "茅台" in items[0]["evidence_text"]

    for item in client.get(
        "/api/annotation/items",
        params={"task_id": "pairs_review", "sample_size": 30, "seed": 20260610},
    ).json()["data"]["items"]:
        res = client.post(
            "/api/annotation/submit",
            json={"task_id": "pairs_review", "annotation": pair_annotation(item["pair_id"])},
        )
        assert res.status_code == 200

    res = client.post("/api/annotation/export", json={"task_id": "pairs_review", "mode": "formal"})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["accept"] == 3 and data["exported"] == 3


def test_context_endpoint_roundtrip(tmp_path: Path, monkeypatch):
    from finer.services.annotation_store import _content_hash

    chat = tmp_path / "chat_history_20260611.md"
    blocks = ["上一条消息说了背景。", "腾讯 0700.HK 目标价 400 元，逢低建仓。", "下一条补充了风险提示。"]
    chat.write_text(
        "\n".join(f"### [2026-06-11 10:0{i}:00] u1 (text)\n{c}" for i, c in enumerate(blocks)),
        encoding="utf-8",
    )
    dpo = tmp_path / "dpo"
    item_id = f"psg_{_content_hash(blocks[1])}"
    write_jsonl(dpo / "eval" / "passages.jsonl", [{
        "id": item_id,
        "evidence_text": blocks[1],
        "source_file": str(chat),
        "timestamp": "2026-06-11 10:01:00",
        "signals": {"signal_score": 2},
    }])
    write_jsonl(dpo / "pairs.jsonl", [])

    import finer.api.routes.annotation as annotation_route

    monkeypatch.setattr(annotation_route, "_store", AnnotationStore(dpo_dir=dpo))
    client = TestClient(create_app())

    res = client.get("/api/annotation/context", params={"item_id": item_id, "before": 2, "after": 2})
    assert res.status_code == 200
    data = res.json()["data"]
    assert [b["offset"] for b in data["blocks"]] == [-1, 0, 1]

    res = client.get("/api/annotation/context", params={"item_id": "psg_nope"})
    assert res.status_code >= 400
    assert res.json()["error"]["details"]["operation"] == "annotation_context"


def test_registry_gap_and_kol_note_endpoints(client: TestClient, tmp_path: Path, monkeypatch):
    import finer.api.routes.annotation as annotation_route

    store = annotation_route._store
    store.kol_notes_dir = tmp_path / "notes"

    res = client.post("/api/annotation/registry-gap", json={
        "alias": "速腾聚创", "suggested_ticker": "2498.HK", "market": "HK",
        "item_id": "psg_a00", "reviewer_id": REVIEWER,
    })
    assert res.status_code == 200
    assert res.json()["data"]["total"] == 1

    res = client.post("/api/annotation/kol-note", json={
        "creator": "kol_x", "category": "style",
        "text": "左侧建仓风格", "source_item_id": "psg_a00", "reviewer_id": REVIEWER,
    })
    assert res.status_code == 200
    assert res.json()["data"]["total_for_creator"] == 1

    res = client.post("/api/annotation/kol-note", json={
        "creator": "kol_x", "category": "not_a_category", "text": "x", "reviewer_id": REVIEWER,
    })
    assert res.status_code >= 400
    assert res.json()["error"]["details"]["operation"] == "annotation_kol_note"


def test_market_endpoint_degraded(client: TestClient):
    res = client.get("/api/annotation/market", params={"ticker": "0700.HK", "date": "2026-03-13"})
    assert res.status_code == 200
    assert res.json()["data"]["coverage"] == "unsupported_market"

    res = client.get("/api/annotation/market", params={"ticker": "300750.SZ", "date": "bad-date"})
    assert res.status_code >= 400
    assert res.json()["error"]["details"]["operation"] == "annotation_market"


def test_submit_stale_schema_version_rejected(client: TestClient):
    ann = gold_annotation("psg_a00")
    ann["annotation_schema_version"] = "2026-06-10.annotation.v2"
    res = client.post("/api/annotation/submit", json={"task_id": "eval_gold", "annotation": ann})
    assert res.status_code >= 400
    assert "当前 schema 版本" in res.json()["error"]["message"]


def test_eval_source_rebuild_endpoint(tmp_path: Path, monkeypatch):
    dpo = tmp_path / "dpo"
    data_root = tmp_path / "data"
    raw = data_root / "raw"
    raw.mkdir(parents=True)
    (raw / "chat_history_20260610.md").write_text(
        "### [2026-06-10 10:00:00] u1 (text)\n腾讯 0700.HK 目标价 400 元，可逢低建仓，基本面修复和利润改善都比较明确。\n",
        encoding="utf-8",
    )
    write_jsonl(dpo / "pairs.jsonl", [])

    import finer.api.routes.annotation as annotation_route

    monkeypatch.setattr(annotation_route, "_store", AnnotationStore(dpo_dir=dpo))
    client = TestClient(create_app())

    res = client.post(
        "/api/annotation/eval-source/rebuild",
        json={"src": str(data_root), "limit": 5, "seed": 1, "min_signal": 2},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["selected"] == 1
    assert Path(dpo / "eval" / "manifest.json").exists()
