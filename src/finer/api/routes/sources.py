"""Sources API — manage external sources (Feishu, NotebookLM) and trigger refresh."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import json
from datetime import datetime

from finer.config import load_feishu_config
from finer.ingestion.feishu_poller import FeishuPoller, SyncState
from finer.ingestion.orchestrator import sync_chat
from finer.paths import REPO_ROOT, DATA_ROOT

router = APIRouter()


class SourceGroup(BaseModel):
    id: str
    name: str
    type: str  # "feishu" or "notebooklm"
    fileCount: int = 0
    lastSync: Optional[str] = None
    notebookId: Optional[str] = None


class RefreshRequest(BaseModel):
    source_type: str  # "feishu" or "notebooklm"
    group_id: Optional[str] = None  # If None, refresh all groups of this type


class RefreshResult(BaseModel):
    status: str
    messages_scanned: int = 0
    files_processed: int = 0
    errors: List[str] = []


@router.get("/groups")
async def get_source_groups():
    """Return all configured source groups with their sync status."""
    groups: List[SourceGroup] = []

    try:
        config = load_feishu_config(REPO_ROOT)
        feishu_cfg = config.get("feishu", {})

        # Load sync state
        state_file = REPO_ROOT / feishu_cfg.get("state_file", "data/.feishu_sync_state.json")
        sync_state = {}
        if state_file.exists():
            sync_state = json.loads(state_file.read_text(encoding="utf-8"))

        # Get Feishu chats
        for chat in feishu_cfg.get("watched_chats", []):
            chat_id = chat["chat_id"]
            last_sync = sync_state.get(chat_id)

            # Count files in raw directory for this creator
            creator_id = chat.get("default_creator", "")
            creator_dir = DATA_ROOT / "raw" / creator_id
            file_count = 0
            if creator_dir.exists():
                file_count = sum(1 for f in creator_dir.rglob("*") if f.is_file())

            groups.append(SourceGroup(
                id=chat_id,
                name=chat.get("name", "Unknown Chat"),
                type="feishu",
                fileCount=file_count,
                lastSync=last_sync,
                notebookId=chat.get("notebook_id"),
            ))

    except FileNotFoundError:
        pass
    except Exception as e:
        raise HTTPException(500, f"Failed to load source groups: {e}")

    # Count total files by source type
    return {
        "groups": [g.model_dump() for g in groups],
        "totalByType": {
            "feishu": sum(g.fileCount for g in groups if g.type == "feishu"),
            "notebooklm": sum(g.fileCount for g in groups if g.type == "notebooklm"),
            "local": 0,  # Will be calculated from files API
        }
    }


@router.post("/refresh")
async def refresh_source(req: RefreshRequest):
    """
    Trigger incremental sync for specified source.
    If group_id is provided, only that group is refreshed.
    Otherwise, all groups of the specified type are refreshed.
    """
    results: List[RefreshResult] = []

    if req.source_type == "feishu":
        try:
            config = load_feishu_config(REPO_ROOT)
            feishu_cfg = config.get("feishu", {})

            state_file = REPO_ROOT / feishu_cfg.get("state_file", "data/.feishu_sync_state.json")
            state = SyncState(state_file)

            chats_to_sync = feishu_cfg.get("watched_chats", [])
            if req.group_id:
                chats_to_sync = [c for c in chats_to_sync if c["chat_id"] == req.group_id]

            for chat_cfg in chats_to_sync:
                try:
                    result = sync_chat(
                        root=REPO_ROOT,
                        chat_config=chat_cfg,
                        full_config=config,
                        state=state,
                        dry_run=False,
                        auto_nlm=True,
                    )
                    results.append(RefreshResult(
                        status="ok",
                        messages_scanned=result.get("messages_scanned", 0),
                        files_processed=result.get("files_processed", 0),
                        errors=result.get("errors", []),
                    ))
                except Exception as e:
                    results.append(RefreshResult(
                        status="error",
                        errors=[str(e)],
                    ))

            # Invalidate files cache after successful sync
            if any(r.status == "ok" and r.files_processed > 0 for r in results):
                from finer.api.routes.files_utils import _assets_cache
                _assets_cache.clear()

        except FileNotFoundError:
            raise HTTPException(400, "Feishu configuration not found")
        except Exception as e:
            raise HTTPException(500, f"Refresh failed: {e}")

    elif req.source_type == "notebooklm":
        # NotebookLM refresh would go here
        # Currently placeholder - would need NLM CLI integration
        results.append(RefreshResult(
            status="not_implemented",
            errors=["NotebookLM refresh not yet implemented"],
        ))

    else:
        raise HTTPException(400, f"Unknown source type: {req.source_type}")

    return {
        "sourceType": req.source_type,
        "refreshedGroups": len(results),
        "results": [r.model_dump() for r in results],
    }


@router.get("/status")
async def get_sync_status():
    """Get current sync status for all sources."""
    try:
        config = load_feishu_config(REPO_ROOT)
        feishu_cfg = config.get("feishu", {})

        state_file = REPO_ROOT / feishu_cfg.get("state_file", "data/.feishu_sync_state.json")
        if state_file.exists():
            sync_state = json.loads(state_file.read_text(encoding="utf-8"))
        else:
            sync_state = {}

        return {
            "lastSyncByChat": sync_state,
            "pollInterval": feishu_cfg.get("poll_interval_seconds", 300),
        }

    except FileNotFoundError:
        return {"lastSyncByChat": {}, "pollInterval": 300}
    except Exception as e:
        raise HTTPException(500, f"Failed to get sync status: {e}")
