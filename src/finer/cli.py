from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from pathlib import Path

from finer.pipeline import dry_run_pipeline, init_storage, register_directory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="finer",
        description="Finer — Investment Research Automation System",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── Existing commands ──────────────────────────────────────
    init_cmd = subparsers.add_parser("init-storage", help="Create canonical data directories")
    init_cmd.add_argument("--root", type=Path, default=Path.cwd())

    register_cmd = subparsers.add_parser(
        "register-dir",
        help="Register source files from a directory into content manifests",
    )
    register_cmd.add_argument("--root", type=Path, default=Path.cwd())
    register_cmd.add_argument("--creator", required=True)
    register_cmd.add_argument("--content-type", required=True)
    register_cmd.add_argument("--source-dir", type=Path, required=True)
    register_cmd.add_argument("--pattern", default="*")
    register_cmd.add_argument("--dry-run", action="store_true")

    dry_cmd = subparsers.add_parser(
        "dry-run",
        help="Run the current skeleton pipeline without OCR/ASR backends",
    )
    dry_cmd.add_argument("--root", type=Path, default=Path.cwd())

    # ── Feishu file management commands ────────────────────────
    feishu_sync_cmd = subparsers.add_parser(
        "feishu-sync",
        help="Pull new files from watched Feishu chats, classify, archive, and sync to NLM",
    )
    feishu_sync_cmd.add_argument("--root", type=Path, default=Path.cwd())
    feishu_sync_cmd.add_argument("--dry-run", action="store_true", help="Preview without downloading")
    feishu_sync_cmd.add_argument("--no-nlm", action="store_true", help="Skip NotebookLM sync")

    feishu_watch_cmd = subparsers.add_parser(
        "feishu-watch",
        help="Continuously poll Feishu chats for new files (daemon mode)",
    )
    feishu_watch_cmd.add_argument("--root", type=Path, default=Path.cwd())
    feishu_watch_cmd.add_argument("--interval", type=int, default=300, help="Poll interval in seconds")
    feishu_watch_cmd.add_argument("--no-nlm", action="store_true", help="Skip NotebookLM sync")

    inbox_cmd = subparsers.add_parser(
        "inbox-status",
        help="Show current inbox contents and sync state",
    )
    inbox_cmd.add_argument("--root", type=Path, default=Path.cwd())

    return parser


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _cmd_feishu_sync(args: argparse.Namespace) -> dict:
    from finer.ingestion.orchestrator import sync_all_chats
    return sync_all_chats(
        root=args.root,
        dry_run=args.dry_run,
        auto_nlm=not args.no_nlm,
    )


def _cmd_feishu_watch(args: argparse.Namespace) -> dict:
    from finer.ingestion.orchestrator import sync_all_chats

    interval = args.interval
    auto_nlm = not args.no_nlm
    running = True

    def _sigint_handler(sig, frame):
        nonlocal running
        print("\n⏹  Stopping watcher...")
        running = False

    signal.signal(signal.SIGINT, _sigint_handler)
    print(f"👁  Watching Feishu chats (interval: {interval}s, NLM: {auto_nlm})")
    print("   Press Ctrl+C to stop.\n")

    cycle = 0
    while running:
        cycle += 1
        print(f"── Cycle {cycle} ──")
        try:
            result = sync_all_chats(root=args.root, auto_nlm=auto_nlm)
            total_files = sum(
                r.get("files_processed", 0) for r in result.get("results", [])
            )
            print(f"   Processed {total_files} files across {result['chats_synced']} chats")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        if running:
            for _ in range(interval):
                if not running:
                    break
                time.sleep(1)

    return {"status": "stopped", "cycles": cycle}


def _cmd_inbox_status(args: argparse.Namespace) -> dict:
    import json as json_mod
    from finer.config import load_feishu_config

    root = args.root
    inbox_dir = root / "data" / "inbox"
    
    # List inbox files
    inbox_files = []
    if inbox_dir.exists():
        inbox_files = [
            {"name": f.name, "size_kb": f.stat().st_size / 1024}
            for f in sorted(inbox_dir.iterdir())
            if f.is_file() and not f.name.startswith(".")
        ]

    # Load sync state
    try:
        config = load_feishu_config(root)
        state_file = root / config.get("feishu", {}).get(
            "state_file", "data/.feishu_sync_state.json"
        )
        if state_file.exists():
            sync_state = json_mod.loads(state_file.read_text())
        else:
            sync_state = {}
    except FileNotFoundError:
        sync_state = {"error": "feishu.yaml not found"}

    return {
        "inbox_dir": str(inbox_dir),
        "pending_files": len(inbox_files),
        "files": inbox_files,
        "sync_state": sync_state,
    }


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _setup_logging(getattr(args, "verbose", False))

    if args.command == "init-storage":
        result = init_storage(args.root)
    elif args.command == "register-dir":
        result = register_directory(
            root=args.root,
            creator_id=args.creator,
            content_type=args.content_type,
            source_dir=args.source_dir,
            pattern=args.pattern,
            dry_run=args.dry_run,
        )
    elif args.command == "dry-run":
        result = dry_run_pipeline(args.root)
    elif args.command == "feishu-sync":
        result = _cmd_feishu_sync(args)
    elif args.command == "feishu-watch":
        result = _cmd_feishu_watch(args)
    elif args.command == "inbox-status":
        result = _cmd_inbox_status(args)
    else:
        parser.error(f"unknown command: {args.command}")
        return

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
