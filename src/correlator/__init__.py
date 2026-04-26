"""Correlator — Cross-references logs with wiki knowledge and detects incident chains."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from src.analyzer import LogEntry, PatternMatch, Severity
from src.wiki_engine import WikiEngine


@dataclass
class Correlation:
    """A link between a log pattern and wiki knowledge."""
    pattern: PatternMatch
    wiki_pages: list[dict]  # [{title, doc_type, relevance}]
    root_cause: str = ""
    resolution_steps: list[str] = field(default_factory=list)
    sla_breach: Optional[dict] = None
    confidence: float = 0.0  # 0-1 how confident in this correlation


@dataclass
class IncidentChain:
    """A sequence of correlated events forming an incident."""
    chain_id: str
    correlations: list[Correlation]
    timeline: list[str]
    blast_radius: list[str]  # affected services
    severity: Severity
    total_duration_estimate: str = ""

    @property
    def total_entries(self) -> int:
        return sum(len(c.pattern.entries) for c in self.correlations)

    @property
    def worst_confidence(self) -> float:
        if not self.correlations:
            return 0.0
        return min(c.confidence for c in self.correlations)


class LogCorrelator:
    """Cross-references detected patterns with wiki knowledge.

    The correlator is the brain of the analysis:
    1. Takes patterns detected by LogAnalyzer
    2. Searches wiki for matching troubleshooting/runbook entries
    3. Extracts root cause and resolution steps from wiki
    4. Checks SLA thresholds for performance patterns
    5. Chains related patterns into incidents
    6. Scores confidence based on wiki match quality
    """

    def __init__(self, wiki: WikiEngine):
        self.wiki = wiki
        self._correlations: list[Correlation] = []

    def correlate(self, patterns: list[PatternMatch]) -> list[Correlation]:
        """Correlate all patterns with wiki knowledge."""
        correlations = []
        for pattern in patterns:
            corr = self._correlate_pattern(pattern)
            if corr:
                correlations.append(corr)
        self._correlations = correlations
        return correlations

    def _correlate_pattern(self, pattern: PatternMatch) -> Optional[Correlation]:
        # Build search query from pattern
        query_parts = [pattern.pattern_name, pattern.affected_service]

        # Add error codes if present
        for entry in pattern.entries[:3]:
            query_parts.extend(entry.error_codes)
            # Extract key terms from message
            if "oom" in entry.message.lower():
                query_parts.extend(["memory", "OOM", "Kubernetes"])
            if "failover" in entry.message.lower():
                query_parts.extend(["failover", "database", "recovery"])
            if "timeout" in entry.message.lower():
                query_parts.extend(["timeout", "performance"])
            if "latency" in entry.message.lower():
                query_parts.extend(["latency", "P95", "performance"])

        query = " ".join(query_parts)
        wiki_results = self.wiki.search(query, top_k=5)

        wiki_pages = [{"title": p.title, "doc_type": p.doc_type,
                       "relevance": round(score, 1),
                       "source": p.source}
                      for score, p in wiki_results]

        # Extract resolution steps from top wiki match
        resolution_steps = []
        root_cause = ""
        if wiki_results:
            top_page = wiki_results[0][1]
            root_cause = self._extract_root_cause(top_page.content, pattern)
            resolution_steps = self._extract_resolution_steps(top_page.content)

        # Check SLA breach for performance patterns
        sla_breach = None
        if pattern.pattern_type in ("latency_spike", "timeout"):
            sla_breach = self._check_sla_breach(pattern)

        # Confidence score
        confidence = self._score_confidence(pattern, wiki_results)

        return Correlation(
            pattern=pattern,
            wiki_pages=wiki_pages,
            root_cause=root_cause,
            resolution_steps=resolution_steps,
            sla_breach=sla_breach,
            confidence=confidence,
        )

    def _extract_root_cause(self, wiki_content: str, pattern: PatternMatch) -> str:
        # Look for "Root Cause:" sections
        import re
        rc_match = re.search(r'\*\*Root Cause:\*\*\s*(.+?)(?:\n|$)', wiki_content)
        if rc_match:
            return rc_match.group(1).strip()
        # Look for first sentence after "Symptom"
        sym_match = re.search(r'(?:Symptom|Symptoms?)[:\s]+(.+?)(?:\n|$)', wiki_content, re.I)
        if sym_match:
            return sym_match.group(1).strip()[:200]
        return "Root cause not explicitly documented in wiki"

    def _extract_resolution_steps(self, wiki_content: str) -> list[str]:
        import re
        steps = []
        # Match numbered steps: "1. ..." or "Step 1: ..."
        for match in re.finditer(r'(?:^|\n)\s*(?:\d+\.|Step\s+\d+:)\s*(.+?)(?:\n|$)', wiki_content):
            step = match.group(1).strip()
            if step and len(step) > 5:
                steps.append(step)
        # Also match bullet steps after "Resolution"
        in_resolution = False
        for line in wiki_content.split('\n'):
            if 'resolution' in line.lower():
                in_resolution = True
                continue
            if in_resolution and line.strip().startswith('-'):
                steps.append(line.strip().lstrip('- ').strip())
            elif in_resolution and not line.strip().startswith('-') and steps:
                break
        return steps[:10]

    def _check_sla_breach(self, pattern: PatternMatch) -> Optional[dict]:
        import re
        for entry in pattern.entries:
            # Extract numeric values
            latency_match = re.search(r'(\d+)\s*ms', entry.message)
            if latency_match:
                value = float(latency_match.group(1))
                return self.wiki.check_sla("latency", value)
        return None

    def _score_confidence(self, pattern: PatternMatch,
                          wiki_results: list) -> float:
        if not wiki_results:
            return 0.2  # Low confidence without wiki support

        top_score = wiki_results[0][0]
        max_possible = len(pattern.pattern_name.split()) * 2 + 10

        base = min(top_score / max(max_possible, 1), 1.0)

        # Boost for specific error codes matching
        for _, page in wiki_results[:2]:
            for code in pattern.entries[0].error_codes if pattern.entries else []:
                if code in page.content:
                    base = min(base + 0.15, 1.0)

        # Boost for runbook match
        for _, page in wiki_results[:2]:
            if page.doc_type == "runbook":
                base = min(base + 0.1, 1.0)

        return round(base, 2)

    def build_incident_chains(self, correlations: list[Correlation]) -> list[IncidentChain]:
        """Chain related correlations into incidents."""
        if not correlations:
            return []

        chains = []
        used = set()

        for i, corr in enumerate(correlations):
            if i in used:
                continue
            chain_corrs = [corr]
            used.add(i)

            # Find related correlations (same service or shared wiki pages)
            for j, other in enumerate(correlations):
                if j in used:
                    continue
                if self._are_related(corr, other):
                    chain_corrs.append(other)
                    used.add(j)

            # Determine chain severity
            max_sev = max(chain_corrs, key=lambda c: self._sev_order(c.pattern.severity))
            services = list(set(c.pattern.affected_service for c in chain_corrs))

            chain_id = f"INC-{len(chains)+1:03d}"
            timeline = [f"[{c.pattern.entries[0].timestamp}] {c.pattern.description}"
                       for c in chain_corrs if c.pattern.entries]

            chains.append(IncidentChain(
                chain_id=chain_id,
                correlations=chain_corrs,
                timeline=timeline,
                blast_radius=services,
                severity=max_sev.pattern.severity,
                total_duration_estimate=self._estimate_duration(chain_corrs),
            ))

        return chains

    def _are_related(self, a: Correlation, b: Correlation) -> bool:
        if a.pattern.affected_service == b.pattern.affected_service:
            return True
        a_pages = {p["title"] for p in a.wiki_pages}
        b_pages = {p["title"] for p in b.wiki_pages}
        if a_pages & b_pages:
            return True
        return False

    @staticmethod
    def _sev_order(sev: Severity) -> int:
        return {Severity.INFO: 0, Severity.WARN: 1, Severity.ERROR: 2, Severity.CRITICAL: 3}[sev]

    @staticmethod
    def _estimate_duration(correlations: list[Correlation]) -> str:
        timestamps = []
        for c in correlations:
            for e in c.pattern.entries:
                timestamps.append(e.timestamp)
        if len(timestamps) >= 2:
            return f"{timestamps[0]} → {timestamps[-1]}"
        return "Unknown"
