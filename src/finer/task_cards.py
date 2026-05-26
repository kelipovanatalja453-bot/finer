from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


STAGE_DOC = Path("docs/specs/f-stage-contracts.md")
PARALLEL_DOC = Path("docs/specs/2026-05-parallel-agent-execution.md")
VIBE_DOC = Path("docs/specs/vibe-agent-operating-model.md")

STAGE_RE = re.compile(r"^## (?P<stage>F(?:1\.5|[0-8])): (?P<name>.+)$", re.MULTILINE)
LINE_RE = re.compile(r"^### Line (?P<line>[A-Z]): (?P<name>.+)$", re.MULTILINE)
HEADING_RE = re.compile(
    r"^(?P<hash>#{2,5})\s+(?P<heading>.+?)\s*$"
    r"|^\*\*(?P<bold>[^*]+)\*\*\s*$",
    re.MULTILINE,
)

SRC_DOMAIN_PREFIXES = (
    "aggregation/",
    "api/",
    "backtest/",
    "config.py",
    "enrichment/",
    "entity_registry.py",
    "errors/",
    "extraction/",
    "ingestion/",
    "llm/",
    "manifests.py",
    "market_data/",
    "ml/",
    "model_config.py",
    "parsing/",
    "paths.py",
    "pipeline/",
    "policy/",
    "schemas/",
    "services/",
    "startup.py",
    "timeline/",
)

GENERIC_STOP_CONDITIONS = (
    "Need to change architecture boundaries.",
    "Need to add a dependency.",
    "Need to touch database schema, migration, or data rebuild.",
    "Need to modify forbidden files.",
    "Tests fail for an unknown reason.",
    "The task card boundary is not specific enough.",
)


@dataclass(frozen=True)
class StageContract:
    stage: str
    name: str
    purpose: str
    allowed_input: str
    required_output: str
    owning_files: tuple[str, ...]
    owning_patterns: tuple[str, ...]
    forbidden_responsibilities: tuple[str, ...]
    acceptance: tuple[str, ...]


@dataclass(frozen=True)
class LineContract:
    line: str
    name: str
    mission: str
    owning_files: tuple[str, ...]
    owning_patterns: tuple[str, ...]
    forbidden_files: tuple[str, ...]
    forbidden_patterns: tuple[str, ...]
    forbidden_behavior: tuple[str, ...]
    outputs: tuple[str, ...]
    acceptance: tuple[str, ...]
    commands: tuple[str, ...]
    red_lines: tuple[str, ...]


@dataclass(frozen=True)
class TaskCardRequest:
    line: str
    stage: str
    targets: tuple[str, ...]
    goal: str | None = None


@dataclass(frozen=True)
class BoundaryCheck:
    status: str
    messages: tuple[str, ...]


@dataclass(frozen=True)
class GeneratedTaskCard:
    markdown: str
    boundary: BoundaryCheck


def generate_task_card(root: Path, request: TaskCardRequest) -> GeneratedTaskCard:
    """Generate a markdown task card and validate target ownership."""
    stage_contracts = load_stage_contracts(root)
    line_contracts = load_line_contracts(root)
    vibe_text = _read_required(root, VIBE_DOC)

    stage_key = normalize_stage(request.stage)
    line_key = normalize_line(request.line)

    if stage_key not in stage_contracts:
        known = ", ".join(sorted(stage_contracts))
        raise ValueError(f"unknown F-stage {request.stage!r}; known stages: {known}")
    if line_key not in line_contracts:
        known = ", ".join(sorted(line_contracts))
        raise ValueError(f"unknown parallel line {request.line!r}; known lines: {known}")

    stage = stage_contracts[stage_key]
    line = line_contracts[line_key]
    boundary = check_boundary(request.targets, stage, line)
    commands = build_verification_commands(root, stage, line, request.targets)
    vibe_stop_conditions = extract_vibe_stop_conditions(vibe_text)
    red_lines = merge_unique(
        line.red_lines,
        extract_global_red_lines(root),
        vibe_stop_conditions or GENERIC_STOP_CONDITIONS,
    )

    markdown = render_task_card(
        request=request,
        stage=stage,
        line=line,
        boundary=boundary,
        commands=commands,
        red_lines=red_lines,
    )
    return GeneratedTaskCard(markdown=markdown, boundary=boundary)


def load_stage_contracts(root: Path) -> dict[str, StageContract]:
    text = _read_required(root, STAGE_DOC)
    contracts: dict[str, StageContract] = {}
    matches = list(STAGE_RE.finditer(text))

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else _next_h2(text, match.end())
        section = text[start:end]
        stage = match.group("stage")
        owning_files = _extract_bullets_for_headings(section, ("Owning Files",))
        contracts[stage] = StageContract(
            stage=stage,
            name=match.group("name").strip(),
            purpose=_extract_inline_field(section, "Purpose"),
            allowed_input=_extract_inline_field(section, "Allowed Input"),
            required_output=_extract_inline_field(section, "Required Output"),
            owning_files=tuple(owning_files),
            owning_patterns=tuple(extract_file_patterns(owning_files)),
            forbidden_responsibilities=tuple(
                _extract_bullets_for_headings(section, ("Forbidden Responsibilities",))
            ),
            acceptance=tuple(_extract_bullets_for_headings(section, ("Acceptance Checklist",))),
        )
    return contracts


def load_line_contracts(root: Path) -> dict[str, LineContract]:
    text = _read_required(root, PARALLEL_DOC)
    contracts: dict[str, LineContract] = {}
    matches = list(LINE_RE.finditer(text))

    for index, match in enumerate(matches):
        start = match.start()
        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = _next_h2(text, match.end())
        section = text[start:end]

        owning_files = _extract_bullets_for_headings(
            section,
            (
                "Allowed files",
                "Allowed files for first-round contract work",
                "Owning files",
                "Backend owning files",
                "Frontend owning files",
            ),
        )
        forbidden_files = _extract_bullets_for_headings(section, ("Forbidden files",))
        contracts[match.group("line")] = LineContract(
            line=match.group("line"),
            name=match.group("name").strip(),
            mission=_extract_paragraph_for_heading(section, "Mission"),
            owning_files=tuple(owning_files),
            owning_patterns=tuple(extract_file_patterns(owning_files)),
            forbidden_files=tuple(forbidden_files),
            forbidden_patterns=tuple(extract_file_patterns(forbidden_files)),
            forbidden_behavior=tuple(_extract_bullets_for_headings(section, ("Forbidden behavior",))),
            outputs=tuple(_extract_bullets_for_headings(section, ("Output", "Outputs", "Output contract"))),
            acceptance=tuple(
                _extract_bullets_for_headings(
                    section,
                    ("Acceptance", "Performance acceptance", "Acceptance Criteria"),
                )
            ),
            commands=tuple(_extract_commands(section)),
            red_lines=tuple(_extract_red_line_bullets(section)),
        )
    return contracts


def normalize_stage(value: str) -> str:
    stage = value.strip().upper().replace(" ", "")
    if stage.startswith("STAGE"):
        stage = stage.removeprefix("STAGE")
    if not re.fullmatch(r"F(?:1\.5|[0-8])", stage):
        raise ValueError(f"invalid F-stage: {value!r}")
    return stage


def normalize_line(value: str) -> str:
    line = value.strip().upper()
    line = line.removeprefix("LINE").strip()
    if re.fullmatch(r"[A-Z]\d+[A-Z]?", line):
        line = line[0]
    if not re.fullmatch(r"[A-Z]", line):
        raise ValueError(f"invalid parallel line: {value!r}")
    return line


def check_boundary(
    targets: Sequence[str],
    stage: StageContract,
    line: LineContract,
) -> BoundaryCheck:
    allowed_patterns = merge_unique(stage.owning_patterns, line.owning_patterns)
    forbidden_patterns = line.forbidden_patterns
    messages: list[str] = []
    blocked = False

    for raw_target in targets:
        target = normalize_target(raw_target)
        forbidden_matches = [
            pattern for pattern in forbidden_patterns if pattern_matches_target(pattern, target)
        ]
        if forbidden_matches:
            blocked = True
            messages.append(
                f"{raw_target} matches forbidden pattern(s): {', '.join(forbidden_matches)}"
            )
            continue

        allowed_matches = [
            pattern for pattern in allowed_patterns if pattern_matches_target(pattern, target)
        ]
        if not allowed_matches:
            blocked = True
            messages.append(
                f"{raw_target} is not covered by stage/line owning files."
            )
        else:
            messages.append(
                f"{raw_target} is covered by: {', '.join(allowed_matches[:3])}"
            )

    if not targets:
        messages.append("No target files were provided; card is a skeleton only.")

    return BoundaryCheck(status="BLOCKED" if blocked else "OK", messages=tuple(messages))


def build_verification_commands(
    root: Path,
    stage: StageContract,
    line: LineContract,
    targets: Sequence[str],
) -> tuple[str, ...]:
    commands: list[str] = []
    target_tokens = _target_tokens(stage.stage, targets)
    command_tokens = _command_filter_tokens(stage.stage, target_tokens)

    for command in line.commands:
        lowered = command.lower()
        if not command_tokens or any(token in lowered for token in command_tokens):
            commands.append(command)

    discovered = discover_test_command(root, stage.stage, targets)
    if discovered:
        commands.append(discovered)

    if any("src/finer_dashboard/" in normalize_target(target) for target in targets):
        commands.append("cd src/finer_dashboard && npm run build")
        commands.append("cd src/finer_dashboard && npx tsc --noEmit")

    commands.append("git diff --check")
    return tuple(merge_unique(commands))[:12]


def discover_test_command(root: Path, stage: str, targets: Sequence[str]) -> str | None:
    tests_dir = root / "tests"
    if not tests_dir.exists():
        return None

    tokens = _target_tokens(stage, targets)
    candidates: list[Path] = []
    for test_file in sorted(tests_dir.glob("test_*.py")):
        name = test_file.name.lower()
        if any(token in name for token in tokens):
            candidates.append(test_file)

    if stage == "F8":
        candidates.extend(sorted(tests_dir.glob("test_backtest*.py")))
    elif stage == "F0":
        candidates.extend(sorted(tests_dir.glob("test_*f0*.py")))

    unique = []
    seen = set()
    for path in candidates:
        rel = path.relative_to(root).as_posix()
        if rel not in seen:
            unique.append(rel)
            seen.add(rel)

    if not unique:
        return "pytest tests/ -v"
    return f"pytest {' '.join(unique[:8])} -q"


def render_task_card(
    request: TaskCardRequest,
    stage: StageContract,
    line: LineContract,
    boundary: BoundaryCheck,
    commands: Sequence[str],
    red_lines: Sequence[str],
) -> str:
    target_list = tuple(request.targets) or ("<fill target files/modules>",)
    goal = request.goal or (
        f"Implement the requested {stage.stage} task inside Line {line.line} boundaries."
    )

    line_outputs = filter_items_for_targets(line.outputs, request.targets)
    sections = [
        "# Agent Task Card",
        "",
        "## Identity",
        f"- Parallel line: Line {line.line} - {line.name}",
        f"- F-stage: {stage.stage} - {stage.name}",
        f"- Boundary status: {boundary.status}",
        "- Recommended model: execution agent for implementation; stronger model for architecture changes",
        "- Risk level: medium by default; high if schema, database, migration, auth, or cross-stage files are touched",
        "",
        "## Goal",
        goal,
        "",
        "## Context",
        "- Read `AGENTS.md` and `CLAUDE.md` first.",
        f"- Read `{PARALLEL_DOC.as_posix()}` for Line {line.line} boundaries.",
        f"- Read `{STAGE_DOC.as_posix()}` for {stage.stage} input/output and ownership.",
        f"- Line mission: {line.mission or '<fill line-specific mission>'}",
        f"- Stage purpose: {stage.purpose or '<fill stage purpose>'}",
        "",
        "## Target Files Or Modules",
        *_as_bullets(target_list),
        "",
        "## Owning Files",
        *_as_bullets(merge_unique(stage.owning_files, line.owning_files) or ("<fill owning files>",)),
        "",
        "## Forbidden Files",
        *_as_bullets(merge_unique(line.forbidden_files) or ("<no line-specific forbidden files extracted; obey stage responsibilities>",)),
        "",
        "## Boundary Check",
        *_as_bullets(boundary.messages),
        "",
        "## Input Contract",
        f"- F-stage input: {stage.allowed_input or '<fill allowed input schema>'}",
        *_prefixed_bullets("Line output/input context", line_outputs),
        "",
        "## Output Contract",
        f"- F-stage output: {stage.required_output or '<fill required output schema>'}",
        "",
        "## Forbidden Responsibilities",
        *_as_bullets(stage.forbidden_responsibilities or line.forbidden_behavior or ("<fill forbidden responsibilities>",)),
        "",
        "## Steps",
        "1. Confirm target files are still inside the owning boundary.",
        "2. Inspect existing implementation and tests before editing.",
        "3. Make the smallest scoped change that satisfies the output contract.",
        "4. Run the verification commands below and report exact results.",
        "",
        "## Acceptance Criteria",
        *_as_bullets(merge_unique(stage.acceptance, line.acceptance) or ("<fill acceptance criteria>",)),
        "",
        "## Verification Commands",
        "```bash",
        *(commands or ("pytest tests/ -v", "git diff --check")),
        "```",
        "",
        "## Red Lines / Stop Conditions",
        *_as_bullets(red_lines),
        "",
    ]
    return "\n".join(sections)


def extract_file_patterns(items: Iterable[str]) -> tuple[str, ...]:
    patterns: list[str] = []
    for item in items:
        code_spans = re.findall(r"`([^`]+)`", item)
        if code_spans:
            raw_patterns = code_spans
        else:
            raw_patterns = _plain_file_patterns(item)

        for raw in raw_patterns:
            normalized = normalize_file_pattern(raw, item)
            if normalized:
                patterns.append(normalized)
    return tuple(merge_unique(patterns))


def normalize_target(value: str) -> str:
    target = value.strip().strip("`")
    if target.startswith("./"):
        target = target[2:]
    if target.startswith("finer."):
        target = "src/" + target.replace(".", "/")
    if target.startswith(SRC_DOMAIN_PREFIXES):
        target = f"src/finer/{target}"
    return target.rstrip("/")


def normalize_file_pattern(value: str, source_item: str = "") -> str | None:
    pattern = value.strip().strip("`").strip()
    pattern = pattern.split(" -- ", 1)[0].strip()
    pattern = pattern.split(" if ", 1)[0].strip()
    pattern = pattern.rstrip(",.;")

    if not pattern:
        return None

    lowered_item = source_item.lower()
    if pattern.lower() in {"related tests", "f8 tests"} or "tests" in lowered_item and "/" not in pattern:
        return "tests/**"
    if "f0 docs" in lowered_item or "docs/specs" in pattern:
        return "docs/specs/**" if pattern.endswith("/") else pattern
    if "dashboard chart component" in lowered_item:
        return "src/finer_dashboard/src/components/**"
    if "sqlite migration" in lowered_item or "migration scripts" in lowered_item:
        return "**/migrations/**"

    if pattern.startswith("./"):
        pattern = pattern[2:]
    if pattern.startswith(SRC_DOMAIN_PREFIXES):
        pattern = f"src/finer/{pattern}"
    if pattern.endswith("/"):
        pattern = f"{pattern}**"
    return pattern


def pattern_matches_target(pattern: str, target: str) -> bool:
    pattern = pattern.rstrip("/")
    target = target.rstrip("/")
    if pattern == target:
        return True
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return target == prefix or target.startswith(f"{prefix}/")
    if "*" in pattern:
        return fnmatch.fnmatchcase(target, pattern)
    return target.startswith(f"{pattern}/") or pattern.startswith(f"{target}/")


def extract_global_red_lines(root: Path) -> tuple[str, ...]:
    text = _read_required(root, PARALLEL_DOC)
    section = _section_by_heading_text(text, "2.5 Data And Database Red Lines")
    return tuple(_bullet_lines(section))


def extract_vibe_stop_conditions(text: str) -> tuple[str, ...]:
    match = re.search(r"## Stop Conditions\n(?P<body>.*?)(?:```|$)", text, re.DOTALL)
    if not match:
        return ()
    return tuple(_bullet_lines(match.group("body")))


def merge_unique(*groups: Iterable[str]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            clean = item.strip()
            if not clean or clean in seen:
                continue
            merged.append(clean)
            seen.add(clean)
    return tuple(merged)


def filter_items_for_targets(items: Sequence[str], targets: Sequence[str]) -> tuple[str, ...]:
    if not targets:
        return tuple(merge_unique(items))

    target_text = " ".join(normalize_target(target).lower() for target in targets)
    active_tags = {
        tag
        for tag in ("feishu", "local", "nlm", "notebook", "wechat", "bilibili")
        if tag in target_text
    }
    filtered: list[str] = []
    for item in items:
        lower = item.lower()
        item_tags = _infer_context_tags(lower)
        if not item_tags or item_tags & active_tags:
            filtered.append(item)
    return tuple(merge_unique(filtered))


def _infer_context_tags(lowered_item: str) -> set[str]:
    tags = {
        tag
        for tag in ("feishu", "local", "nlm", "notebook", "wechat", "bilibili")
        if tag in lowered_item
    }
    if "article/video" in lowered_item:
        tags.add("wechat")
    if "video/audio" in lowered_item or "subtitle" in lowered_item:
        tags.add("bilibili")
    if "dedupe result" in lowered_item:
        tags.add("local")
    return tags


def _command_filter_tokens(stage: str, tokens: Sequence[str]) -> tuple[str, ...]:
    generic = {
        stage.lower(),
        "adapter",
        "f0",
        "f8",
        "ingestion",
        "intake",
        "route",
        "routes",
        "schema",
        "standardize",
    }
    filtered = tuple(token for token in tokens if token not in generic)
    if stage == "F8" and "backtest" in tokens:
        return merge_unique(filtered, ("backtest",))
    return filtered


def _read_required(root: Path, path: Path) -> str:
    full_path = root / path
    if not full_path.exists():
        raise FileNotFoundError(f"required spec not found: {full_path}")
    return full_path.read_text(encoding="utf-8")


def _next_h2(text: str, start: int) -> int:
    match = re.search(r"^## ", text[start:], re.MULTILINE)
    return start + match.start() if match else len(text)


def _iter_heading_blocks(section: str) -> Iterable[tuple[str, str]]:
    matches = list(HEADING_RE.finditer(section))
    for index, match in enumerate(matches):
        heading = match.group("heading") or match.group("bold") or ""
        heading = heading.strip().strip(":")
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        yield heading, section[start:end]


def _extract_inline_field(section: str, field: str) -> str:
    pattern = re.compile(rf"^- \*\*{re.escape(field)}\*\*:\s*(?P<value>.+)$", re.MULTILINE)
    match = pattern.search(section)
    return match.group("value").strip() if match else ""


def _extract_paragraph_for_heading(section: str, heading_name: str) -> str:
    wanted = heading_name.lower()
    for heading, body in _iter_heading_blocks(section):
        if wanted == heading.lower():
            lines = []
            for line in body.splitlines():
                stripped = line.strip()
                if not stripped:
                    if lines:
                        break
                    continue
                if stripped.startswith(("-", "|", "```")):
                    if lines:
                        break
                    continue
                lines.append(stripped)
            return " ".join(lines)
    return ""


def _extract_bullets_for_headings(section: str, heading_names: Sequence[str]) -> list[str]:
    wanted = tuple(name.lower() for name in heading_names)
    bullets: list[str] = []
    for heading, body in _iter_heading_blocks(section):
        lower = heading.lower()
        if any(name in lower for name in wanted):
            bullets.extend(_bullet_lines(body))
    return bullets


def _extract_commands(section: str) -> list[str]:
    commands: list[str] = []
    for heading, body in _iter_heading_blocks(section):
        lower = heading.lower()
        if "recommended commands" not in lower and "acceptance commands" not in lower:
            continue
        for block in re.findall(r"```(?:bash|sh)?\n(.*?)```", body, re.DOTALL):
            for line in block.splitlines():
                command = line.strip()
                if command and not command.startswith("#"):
                    commands.append(command)
    return commands


def _extract_red_line_bullets(section: str) -> list[str]:
    red_lines: list[str] = []
    for heading, body in _iter_heading_blocks(section):
        if "red line" in heading.lower():
            bullets = _bullet_lines(body)
            if bullets:
                red_lines.extend(bullets)
            else:
                red_lines.extend(_paragraph_lines(body))
    return red_lines


def _section_by_heading_text(text: str, heading: str) -> str:
    pattern = re.compile(rf"^### {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    next_heading = re.search(r"^### ", text[match.end():], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    return text[match.end():end]


def _bullet_lines(text: str) -> list[str]:
    bullets: list[str] = []
    current: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            if current:
                bullets.append(current)
            current = stripped[2:].strip()
        elif current and line.startswith(("  ", "\t")) and stripped:
            current = f"{current} {stripped}"
        elif current and not stripped:
            continue
        elif current:
            bullets.append(current)
            current = None
    if current:
        bullets.append(current)
    return bullets


def _paragraph_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith(("```", "|"))
    ]


def _plain_file_patterns(item: str) -> list[str]:
    lowered = item.lower()
    if "tests" in lowered:
        return ["tests/**"]
    if "docs/specs" in item:
        return ["docs/specs/**"]
    if "dashboard chart component" in lowered:
        return ["src/finer_dashboard/src/components/**"]
    if "sqlite migration" in lowered or "migration scripts" in lowered:
        return ["**/migrations/**"]

    matches = re.findall(r"(?:src|tests|docs|data|configs)/[A-Za-z0-9_./*\-\[\]]+", item)
    return matches


def _target_tokens(stage: str, targets: Sequence[str]) -> tuple[str, ...]:
    tokens = {stage.lower()}
    if stage == "F0":
        tokens.add("f0")
        tokens.add("intake")
    elif stage == "F8":
        tokens.add("backtest")

    for target in targets:
        normalized = normalize_target(target).lower()
        for part in re.split(r"[/_.\-\[\]]+", normalized):
            if len(part) >= 3 and part not in {"src", "finer", "api", "routes", "tests", "test"}:
                tokens.add(part)
    return tuple(sorted(tokens))


def _as_bullets(items: Iterable[str]) -> tuple[str, ...]:
    return tuple(f"- {item}" for item in items)


def _prefixed_bullets(prefix: str, items: Iterable[str]) -> tuple[str, ...]:
    return tuple(f"- {prefix}: {item}" for item in items)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_agent_task_card.py",
        description="Generate and validate a Finer parallel-agent task card.",
    )
    parser.add_argument("--line", required=True, help="Parallel line, e.g. A, D, Line D, D1")
    parser.add_argument("--stage", required=True, help="F-stage, e.g. F0, F8")
    parser.add_argument(
        "--target",
        action="append",
        dest="targets",
        required=True,
        help="Target file or module. Repeat for multiple targets.",
    )
    parser.add_argument("--goal", help="Optional one-line task goal.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    request = TaskCardRequest(
        line=args.line,
        stage=args.stage,
        targets=tuple(args.targets),
        goal=args.goal,
    )

    try:
        generated = generate_task_card(args.root.resolve(), request)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(generated.markdown)
    return 2 if generated.boundary.status == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
