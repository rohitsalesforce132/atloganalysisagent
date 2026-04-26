"""Analyzer — Log parsing, pattern detection, error extraction."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    APPLICATION = "application"
    DATABASE = "database"
    INFRASTRUCTURE = "infrastructure"
    NETWORK = "network"
    SECURITY = "security"
    PERFORMANCE = "performance"
    CACHE = "cache"
    SEARCH = "search"


@dataclass
class LogEntry:
    timestamp: str
    severity: Severity
    service: str
    message: str
    raw: str
    line_number: int = 0

    @property
    def is_error(self) -> bool:
        return self.severity in (Severity.ERROR, Severity.CRITICAL)

    @property
    def error_codes(self) -> list[str]:
        return re.findall(r'ERR-\d{4}', self.message)

    @property
    def http_status(self) -> Optional[int]:
        match = re.search(r'\b([45]\d{2})\b', self.message)
        return int(match.group(1)) if match else None

    @property
    def service_clean(self) -> str:
        return self.service.strip("[]")


@dataclass
class PatternMatch:
    pattern_name: str
    pattern_type: str  # "error_code", "oom", "failover", "timeout", "latency_spike", "cache_miss"
    entries: list[LogEntry]
    description: str
    severity: Severity
    affected_service: str


class LogAnalyzer:
    """Parses raw log text into structured entries and detects patterns.

    Capabilities:
    - Timestamp extraction (ISO 8601)
    - Severity classification (INFO/WARN/ERROR/CRITICAL)
    - Service identification
    - Error code extraction (ERR-NNNN)
    - HTTP status extraction
    - Pattern detection: OOM kills, failovers, timeouts, latency spikes, cache exhaustion
    - Time-range filtering
    - Service filtering
    """

    LOG_PATTERN = re.compile(
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s+'
        r'(INFO|WARN|ERROR|CRITICAL)\s+'
        r'\[([^\]]+)\]\s+'
        r'(.*)'
    )

    def parse(self, log_text: str) -> list[LogEntry]:
        entries = []
        for i, line in enumerate(log_text.strip().split('\n'), 1):
            if not line.strip():
                continue
            match = self.LOG_PATTERN.match(line)
            if match:
                ts, sev, svc, msg = match.groups()
                entries.append(LogEntry(
                    timestamp=ts,
                    severity=Severity(sev),
                    service=svc,
                    message=msg,
                    raw=line,
                    line_number=i,
                ))
        return entries

    def parse_file(self, path: str) -> list[LogEntry]:
        with open(path, 'r') as f:
            return self.parse(f.read())

    def filter_by_severity(self, entries: list[LogEntry],
                           min_severity: Severity = Severity.WARN) -> list[LogEntry]:
        order = {Severity.INFO: 0, Severity.WARN: 1, Severity.ERROR: 2, Severity.CRITICAL: 3}
        min_level = order[min_severity]
        return [e for e in entries if order[e.severity] >= min_level]

    def filter_by_service(self, entries: list[LogEntry],
                          service: str) -> list[LogEntry]:
        return [e for e in entries if service.lower() in e.service.lower()]

    def filter_by_time_range(self, entries: list[LogEntry],
                             start: str, end: str) -> list[LogEntry]:
        return [e for e in entries if start <= e.timestamp <= end]

    def detect_patterns(self, entries: list[LogEntry]) -> list[PatternMatch]:
        patterns = []
        patterns.extend(self._detect_error_codes(entries))
        patterns.extend(self._detect_oom_kills(entries))
        patterns.extend(self._detect_failovers(entries))
        patterns.extend(self._detect_timeouts(entries))
        patterns.extend(self._detect_latency_spikes(entries))
        patterns.extend(self._detect_cache_issues(entries))
        patterns.extend(self._detect_db_issues(entries))
        return patterns

    def _detect_error_codes(self, entries: list[LogEntry]) -> list[PatternMatch]:
        code_entries: dict[str, list[LogEntry]] = {}
        for e in entries:
            for code in e.error_codes:
                code_entries.setdefault(code, []).append(e)
        matches = []
        for code, ents in code_entries.items():
            matches.append(PatternMatch(
                pattern_name=code,
                pattern_type="error_code",
                entries=ents,
                description=f"Error code {code} appeared {len(ents)} time(s)",
                severity=Severity.ERROR,
                affected_service=ents[0].service_clean,
            ))
        return matches

    def _detect_oom_kills(self, entries: list[LogEntry]) -> list[PatternMatch]:
        oom_entries = [e for e in entries if "oom" in e.message.lower() or
                       "exit code 137" in e.message.lower() or
                       "memory" in e.message.lower() and "kill" in e.message.lower()]
        if not oom_entries:
            return []
        return [PatternMatch(
            pattern_name="OOM Kill",
            pattern_type="oom",
            entries=oom_entries,
            description=f"OOM kill detected: {len(oom_entries)} memory-related entries",
            severity=Severity.CRITICAL,
            affected_service=oom_entries[0].service_clean,
        )]

    def _detect_failovers(self, entries: list[LogEntry]) -> list[PatternMatch]:
        failover_entries = [e for e in entries if
                           "failover" in e.message.lower() or
                           "promoting replica" in e.message.lower() or
                           "split-brain" in e.message.lower()]
        if not failover_entries:
            return []
        return [PatternMatch(
            pattern_name="Failover Event",
            pattern_type="failover",
            entries=failover_entries,
            description=f"Failover detected: {len(failover_entries)} entries",
            severity=Severity.ERROR,
            affected_service=failover_entries[0].service_clean,
        )]

    def _detect_timeouts(self, entries: list[LogEntry]) -> list[PatternMatch]:
        timeout_entries = [e for e in entries if "timeout" in e.message.lower()]
        if not timeout_entries:
            return []
        return [PatternMatch(
            pattern_name="Timeout",
            pattern_type="timeout",
            entries=timeout_entries,
            description=f"Timeout detected: {len(timeout_entries)} entries",
            severity=Severity.ERROR,
            affected_service=timeout_entries[0].service_clean,
        )]

    def _detect_latency_spikes(self, entries: list[LogEntry]) -> list[PatternMatch]:
        latency_entries = [e for e in entries if
                          "latency spike" in e.message.lower() or
                          "slow query" in e.message.lower() or
                          re.search(r'P95.*\d+ms', e.message, re.I)]
        if not latency_entries:
            return []
        return [PatternMatch(
            pattern_name="Latency Spike",
            pattern_type="latency_spike",
            entries=latency_entries,
            description=f"Performance degradation: {len(latency_entries)} latency entries",
            severity=Severity.WARN,
            affected_service=latency_entries[0].service_clean,
        )]

    def _detect_cache_issues(self, entries: list[LogEntry]) -> list[PatternMatch]:
        cache_entries = [e for e in entries if
                        "cache" in e.message.lower() and
                        ("hit rate" in e.message.lower() or "exhausted" in e.message.lower())]
        if not cache_entries:
            return []
        return [PatternMatch(
            pattern_name="Cache Degradation",
            pattern_type="cache_issue",
            entries=cache_entries,
            description=f"Cache issues: {len(cache_entries)} entries",
            severity=Severity.WARN,
            affected_service=cache_entries[0].service_clean,
        )]

    def _detect_db_issues(self, entries: list[LogEntry]) -> list[PatternMatch]:
        db_entries = [e for e in entries if
                     "connection" in e.message.lower() and
                     ("refused" in e.message.lower() or "pool" in e.message.lower())]
        if not db_entries:
            return []
        return [PatternMatch(
            pattern_name="Database Connection Issue",
            pattern_type="db_connection",
            entries=db_entries,
            description=f"DB connection issues: {len(db_entries)} entries",
            severity=Severity.ERROR,
            affected_service=db_entries[0].service_clean,
        )]

    @property
    def summary(self) -> dict:
        return {
            "parse_pattern": self.LOG_PATTERN.pattern,
            "pattern_types": ["error_code", "oom", "failover", "timeout",
                            "latency_spike", "cache_issue", "db_connection"],
        }
