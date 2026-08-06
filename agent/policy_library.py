"""Parses the synthetic resolution-policy markdown library into citable chunks.

Each policy file is YAML frontmatter followed by `## Heading {#anchor}` sections.
Every section becomes one retrievable chunk, carrying its policy's identity and
version so retrieval results can always cite `<file>.md#<anchor>`.
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from agent.config import POLICIES_DIR

SECTION_PATTERN = re.compile(r"^##\s+(?P<title>.+?)\s+\{#(?P<anchor>[a-z0-9-]+)\}\s*$", re.MULTILINE)


@dataclass
class PolicyChunk:
    policy_id: str
    policy_title: str
    exception_type: str
    version: str
    responsible_team: str
    default_severity: str
    recommended_queue: str
    human_approval_required: bool
    sla_hours: int
    section_title: str
    anchor: str
    text: str
    source_file: str
    content_hash: str = field(init=False)

    def __post_init__(self):
        self.content_hash = hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]

    @property
    def citation(self) -> str:
        return f"{self.source_file}#{self.anchor}"

    @property
    def chunk_id(self) -> str:
        return f"{self.policy_id}:{self.version}:{self.anchor}"


def _split_sections(body: str) -> list[tuple[str, str, str]]:
    matches = list(SECTION_PATTERN.finditer(body))
    sections = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[start:end].strip()
        sections.append((m.group("title"), m.group("anchor"), text))
    return sections


def parse_policy_file(path: Path) -> list[PolicyChunk]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"{path} is missing YAML frontmatter")

    _, frontmatter_raw, body = raw.split("---", 2)
    meta = yaml.safe_load(frontmatter_raw)

    chunks = []
    for title, anchor, text in _split_sections(body):
        chunks.append(
            PolicyChunk(
                policy_id=meta["policy_id"],
                policy_title=meta["title"],
                exception_type=meta["exception_type"],
                version=str(meta["version"]),
                responsible_team=meta["responsible_team"],
                default_severity=meta["default_severity"],
                recommended_queue=meta["recommended_queue"],
                human_approval_required=bool(meta["human_approval_required"]),
                sla_hours=int(meta["sla_hours"]),
                section_title=title,
                anchor=anchor,
                text=text,
                source_file=path.name,
            )
        )
    if not chunks:
        raise ValueError(f"{path} produced no sections — check heading anchor format")
    return chunks


def load_policy_library(policies_dir: Path = POLICIES_DIR) -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []
    for path in sorted(policies_dir.glob("*.md")):
        chunks.extend(parse_policy_file(path))
    return chunks
