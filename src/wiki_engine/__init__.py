"""Wiki Engine — Knowledge retrieval from documentation for log analysis.

Loads troubleshooting guides, runbooks, SLAs, and specifications as a
searchable knowledge base that the expert agent queries during analysis.
"""
from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WikiPage:
    title: str
    content: str
    doc_type: str  # "runbook", "troubleshooting", "sla", "specification"
    source: str
    tags: list[str] = field(default_factory=list)

    @property
    def word_set(self) -> set:
        return set(re.findall(r'\b\w+\b', self.content.lower()))


class WikiEngine:
    """Knowledge retrieval engine for log analysis.

    Ingests documentation (runbooks, troubleshooting guides, SLAs, specs)
    and provides semantic search for the expert agent to correlate logs
    with known issues, resolution steps, and SLA thresholds.
    """

    def __init__(self):
        self._pages: dict[str, WikiPage] = {}
        self._tag_index: dict[str, list[str]] = {}

    def ingest(self, title: str, content: str, doc_type: str,
               source: str, tags: list[str] = None) -> WikiPage:
        page = WikiPage(title=title, content=content, doc_type=doc_type,
                       source=source, tags=tags or [])
        self._pages[title] = page
        for tag in page.tags:
            self._tag_index.setdefault(tag, []).append(title)
        return page

    def ingest_file(self, path: str, doc_type: str, tags: list[str] = None) -> Optional[WikiPage]:
        import os
        if not os.path.exists(path):
            return None
        with open(path, 'r') as f:
            content = f.read()
        title = os.path.basename(path).replace('.md', '')
        return self.ingest(title, content, doc_type, path, tags)

    def ingest_directory(self, dir_path: str) -> int:
        import os
        count = 0
        for fname in sorted(os.listdir(dir_path)):
            if fname.endswith('.md') or fname.endswith('.txt'):
                path = os.path.join(dir_path, fname)
                doc_type = self._infer_type(fname)
                tags = self._extract_tags(path)
                if self.ingest_file(path, doc_type, tags):
                    count += 1
        return count

    def search(self, query: str, top_k: int = 5, doc_type: str = None) -> list[tuple[float, WikiPage]]:
        query_words = set(re.findall(r'\b\w+\b', query.lower()))
        scored = []
        for page in self._pages.values():
            if doc_type and page.doc_type != doc_type:
                continue
            page_words = page.word_set
            overlap = len(query_words & page_words)
            if overlap == 0:
                continue
            tag_bonus = sum(2 for tag in page.tags if tag in query.lower())
            score = overlap + tag_bonus
            scored.append((score, page))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    def find_resolution(self, error_code: str) -> list[WikiPage]:
        return [p for _, p in self.search(error_code, top_k=10)
                if error_code in p.content or error_code.lower() in p.content.lower()]

    def find_runbook(self, scenario: str) -> list[WikiPage]:
        return [p for _, p in self.search(scenario, top_k=10, doc_type="runbook")]

    def check_sla(self, metric: str, value: float) -> Optional[dict]:
        for _, page in self.search(f"SLA {metric} target threshold", doc_type="sla"):
            # Extract numeric targets from SLA doc
            patterns = [
                rf'{metric}[^)]*?(\d+(?:\.\d+)?)\s*(?:ms|seconds|sec|%)',
                rf'P95[^)]*?(\d+(?:\.\d+)?)\s*ms',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, page.content, re.I)
                if matches:
                    threshold = float(matches[0])
                    return {"metric": metric, "value": value, "threshold": threshold,
                            "breached": value > threshold,
                            "source": page.source}
        return None

    def _infer_type(self, filename: str) -> str:
        name = filename.lower()
        if "runbook" in name or "rb-" in name:
            return "runbook"
        if "troubleshoot" in name or "ts-" in name:
            return "troubleshooting"
        if "sla" in name:
            return "sla"
        if "spec" in name:
            return "specification"
        return "general"

    def _extract_tags(self, path: str) -> list[str]:
        tags = []
        try:
            with open(path, 'r') as f:
                content = f.read(2000).lower()
            if "kubernetes" in content or "kubectl" in content:
                tags.append("kubernetes")
            if "postgres" in content or "patroni" in content:
                tags.append("database")
            if "redis" in content:
                tags.append("cache")
            if "elasticsearch" in content:
                tags.append("search")
            if "tmf620" in content:
                tags.append("tmf620")
            if "err-" in content:
                tags.append("errors")
            if "latency" in content or "p95" in content:
                tags.append("performance")
            if "oom" in content or "memory" in content:
                tags.append("memory")
        except Exception:
            pass
        return tags

    @property
    def total_pages(self) -> int:
        return len(self._pages)

    @property
    def doc_types(self) -> dict[str, int]:
        types: dict[str, int] = {}
        for p in self._pages.values():
            types[p.doc_type] = types.get(p.doc_type, 0) + 1
        return types
