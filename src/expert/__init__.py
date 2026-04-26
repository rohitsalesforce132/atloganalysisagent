"""Expert — The AI agent that produces deep-dive analysis reports."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional

from src.analyzer import LogAnalyzer, LogEntry, PatternMatch, Severity
from src.correlator import LogCorrelator, Correlation, IncidentChain
from src.wiki_engine import WikiEngine


@dataclass
class AnalysisReport:
    """Complete log analysis report from the expert agent."""
    report_id: str
    summary: str
    severity: Severity
    total_entries: int
    error_count: int
    warning_count: int
    patterns_detected: list[dict]
    incident_chains: list[dict]
    recommendations: list[dict]
    sla_breaches: list[dict]
    wiki_sources_used: list[str]
    confidence: float
    analysis_time_ms: float
    timestamp: float = field(default_factory=time.time)

    def to_markdown(self) -> str:
        """Full markdown report."""
        lines = [
            f"# Log Analysis Report — {self.report_id}",
            f"",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.timestamp))}",
            f"**Severity:** {self.severity.value}",
            f"**Confidence:** {self.confidence:.0%}",
            f"**Analysis Time:** {self.analysis_time_ms:.0f}ms",
            f"",
            f"## Executive Summary",
            f"",
            f"{self.summary}",
            f"",
            f"## Statistics",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total log entries | {self.total_entries} |",
            f"| Errors | {self.error_count} |",
            f"| Warnings | {self.warning_count} |",
            f"| Patterns detected | {len(self.patterns_detected)} |",
            f"| Incident chains | {len(self.incident_chains)} |",
            f"| SLA breaches | {len(self.sla_breaches)} |",
            f"| Wiki sources consulted | {len(self.wiki_sources_used)} |",
            f"",
        ]

        if self.incident_chains:
            lines.append("## Incident Chains")
            lines.append("")
            for chain in self.incident_chains:
                lines.append(f"### {chain['chain_id']} — {chain['severity']}")
                lines.append(f"**Blast radius:** {', '.join(chain['blast_radius'])}")
                lines.append(f"**Duration:** {chain['duration']}")
                lines.append(f"**Correlated patterns:** {chain['pattern_count']}")
                lines.append("")
                lines.append("**Timeline:**")
                for event in chain["timeline"]:
                    lines.append(f"- {event}")
                lines.append("")

                for corr in chain["correlations"]:
                    lines.append(f"#### {corr['pattern_name']} ({corr['pattern_type']})")
                    lines.append(f"- **Description:** {corr['description']}")
                    lines.append(f"- **Confidence:** {corr['confidence']:.0%}")
                    if corr["root_cause"]:
                        lines.append(f"- **Root Cause:** {corr['root_cause']}")
                    if corr["resolution_steps"]:
                        lines.append(f"- **Resolution Steps:**")
                        for step in corr["resolution_steps"][:5]:
                            lines.append(f"  1. {step}")
                    if corr["wiki_pages"]:
                        lines.append(f"- **Wiki Sources:** {', '.join(p['title'] for p in corr['wiki_pages'][:3])}")
                    if corr["sla_breach"]:
                        lines.append(f"- **⚠️ SLA Breach:** {corr['sla_breach']['metric']} = {corr['sla_breach']['value']} (threshold: {corr['sla_breach']['threshold']})")
                    lines.append("")

        if self.recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"### {i}. {rec['title']}")
                lines.append(f"**Priority:** {rec['priority']} | **Confidence:** {rec['confidence']:.0%}")
                lines.append(f"{rec['description']}")
                if rec.get("action"):
                    lines.append(f"**Action:** {rec['action']}")
                lines.append("")

        if self.wiki_sources_used:
            lines.append("## Knowledge Sources")
            lines.append("")
            for src in self.wiki_sources_used:
                lines.append(f"- {src}")
            lines.append("")

        return "\n".join(lines)


class LogAnalysisExpert:
    """The expert agent — Anthropic-style reasoning over logs + wiki knowledge.

    Workflow:
    1. Parse logs → structured entries
    2. Detect patterns → error codes, OOM, failovers, timeouts, etc.
    3. Correlate with wiki → find matching runbooks/troubleshooting/SLAs
    4. Build incident chains → group related patterns
    5. Generate recommendations → prioritize by severity + confidence
    6. Produce report → full markdown with timeline, root cause, resolution

    This is the "thinking" agent that produces human-quality analysis.
    """

    def __init__(self, wiki: WikiEngine = None):
        self.wiki = wiki or WikiEngine()
        self.analyzer = LogAnalyzer()
        self.correlator = LogCorrelator(self.wiki)

    def analyze(self, log_text: str, source: str = "logs") -> AnalysisReport:
        """Full deep-dive analysis of log text."""
        start = time.time()

        # Step 1: Parse
        entries = self.analyzer.parse(log_text)

        # Step 2: Filter to errors/warnings
        errors_warnings = self.analyzer.filter_by_severity(entries, Severity.WARN)

        # Step 3: Detect patterns
        patterns = self.analyzer.detect_patterns(entries)

        # Step 4: Correlate with wiki
        correlations = self.correlator.correlate(patterns)

        # Step 5: Build incident chains
        chains = self.correlator.build_incident_chains(correlations)

        # Step 6: Generate recommendations
        recommendations = self._generate_recommendations(correlations, chains)

        # Step 7: Check SLA breaches
        sla_breaches = [c.sla_breach for c in correlations if c.sla_breach and c.sla_breach.get("breached")]

        # Step 8: Calculate overall confidence
        confidence = self._overall_confidence(correlations)

        duration_ms = (time.time() - start) * 1000

        # Determine severity
        severity = Severity.INFO
        if any(c.pattern.severity == Severity.CRITICAL for c in correlations):
            severity = Severity.CRITICAL
        elif any(c.pattern.severity == Severity.ERROR for c in correlations):
            severity = Severity.ERROR
        elif errors_warnings:
            severity = Severity.WARN

        return AnalysisReport(
            report_id=f"LAR-{int(time.time())}",
            summary=self._generate_summary(entries, patterns, chains),
            severity=severity,
            total_entries=len(entries),
            error_count=sum(1 for e in entries if e.is_error),
            warning_count=sum(1 for e in entries if e.severity == Severity.WARN),
            patterns_detected=[{"name": p.pattern_name, "type": p.pattern_type,
                               "entries": len(p.entries), "service": p.affected_service}
                              for p in patterns],
            incident_chains=[self._chain_to_dict(ch) for ch in chains],
            recommendations=recommendations,
            sla_breaches=[{"metric": b["metric"], "value": b["value"],
                          "threshold": b["threshold"], "source": b["source"]}
                         for b in sla_breaches],
            wiki_sources_used=list(set(
                p.title for c in correlations for _, p in
                self.wiki.search(" ".join(e.message for e in c.pattern.entries[:3]), top_k=3)
            )),
            confidence=confidence,
            analysis_time_ms=round(duration_ms, 1),
        )

    def analyze_file(self, path: str) -> AnalysisReport:
        with open(path, 'r') as f:
            return self.analyze(f.read(), source=path)

    def _generate_summary(self, entries: list[LogEntry],
                          patterns: list[PatternMatch],
                          chains: list[IncidentChain]) -> str:
        error_count = sum(1 for e in entries if e.is_error)
        critical = sum(1 for e in entries if e.severity == Severity.CRITICAL)

        parts = [f"Analyzed {len(entries)} log entries"]
        if error_count:
            parts.append(f"found {error_count} errors ({critical} critical)")
        if patterns:
            parts.append(f"detected {len(patterns)} distinct patterns")
        if chains:
            parts.append(f"identified {len(chains)} incident chain(s)")
            for ch in chains:
                parts.append(f"  {ch.chain_id}: {', '.join(ch.blast_radius)}")
        return ". ".join(parts) + "."

    def _generate_recommendations(self, correlations: list[Correlation],
                                   chains: list[IncidentChain]) -> list[dict]:
        recs = []
        for chain in chains:
            for corr in chain.correlations:
                if corr.root_cause and corr.root_cause != "Root cause not explicitly documented in wiki":
                    priority = "HIGH" if corr.pattern.severity in (Severity.ERROR, Severity.CRITICAL) else "MEDIUM"
                    recs.append({
                        "title": f"Investigate {corr.pattern.pattern_name}",
                        "priority": priority,
                        "confidence": corr.confidence,
                        "description": f"Root cause identified: {corr.root_cause}",
                        "action": "; ".join(corr.resolution_steps[:3]) if corr.resolution_steps else "Review wiki documentation",
                    })

        # SLA-based recommendations
        for corr in correlations:
            if corr.sla_breach and corr.sla_breach.get("breached"):
                recs.append({
                    "title": f"SLA breach: {corr.sla_breach['metric']}",
                    "priority": "HIGH",
                    "confidence": 0.9,
                    "description": f"{corr.sla_breach['metric']} = {corr.sla_breach['value']} exceeds threshold {corr.sla_breach['threshold']}",
                    "action": "Escalate to service owner for remediation",
                })

        recs.sort(key=lambda r: (0 if r["priority"] == "HIGH" else 1, -r["confidence"]))
        return recs[:10]

    def _chain_to_dict(self, chain: IncidentChain) -> dict:
        return {
            "chain_id": chain.chain_id,
            "severity": chain.severity.value,
            "blast_radius": chain.blast_radius,
            "duration": chain.total_duration_estimate,
            "pattern_count": len(chain.correlations),
            "timeline": chain.timeline,
            "correlations": [self._corr_to_dict(c) for c in chain.correlations],
        }

    def _corr_to_dict(self, corr: Correlation) -> dict:
        return {
            "pattern_name": corr.pattern.pattern_name,
            "pattern_type": corr.pattern.pattern_type,
            "description": corr.pattern.description,
            "confidence": corr.confidence,
            "root_cause": corr.root_cause,
            "resolution_steps": corr.resolution_steps,
            "wiki_pages": corr.wiki_pages,
            "sla_breach": corr.sla_breach,
        }

    def _overall_confidence(self, correlations: list[Correlation]) -> float:
        if not correlations:
            return 0.0
        return round(sum(c.confidence for c in correlations) / len(correlations), 2)
