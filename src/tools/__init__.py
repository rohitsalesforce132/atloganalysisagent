"""Tools — Anthropic-style agent tools with JSON Schema definitions.

Each tool follows the Anthropic tool-use specification:
- name: unique identifier matching ^[a-zA-Z0-9_-]{1,64}$
- description: detailed explanation of what/when/how
- input_schema: JSON Schema defining parameters
- input_examples: optional example inputs

The agent orchestrator decides which tool to call based on user request,
tool descriptions, and conversation context (the agentic loop).
"""
from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.wiki_engine import WikiEngine
from src.analyzer import LogAnalyzer, Severity
from src.correlator import LogCorrelator
from src.expert import LogAnalysisExpert, AnalysisReport


@dataclass
class ToolCall:
    """A structured tool call following Anthropic's tool_use format."""
    id: str
    name: str
    input: dict


@dataclass
class ToolResult:
    """Result of executing a tool call."""
    tool_use_id: str
    output: str
    is_error: bool = False
    data: dict = field(default_factory=dict)


@dataclass
class ToolDefinition:
    """Anthropic-compatible tool definition."""
    name: str
    description: str
    input_schema: dict
    input_examples: list[dict] = field(default_factory=list)
    handler: Callable = None

    def to_anthropic_format(self) -> dict:
        """Export as Anthropic API tool definition."""
        d = {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
        if self.input_examples:
            d["input_examples"] = self.input_examples
        return d


class ToolRegistry:
    """Registry of Anthropic-style tools for the APILoganalysisExpert agent.

    Tools are organized into 4 categories:
    - ANALYZE: Log parsing, pattern detection, deep analysis
    - KNOWLEDGE: Wiki search, document ingestion, SLA lookups
    - REPORT: Summary, timeline, recommendations, markdown export
    - UTILS: Health, stats, skill listing

    Each tool has a proper JSON Schema input_schema so an LLM can
    decide when and how to call it autonomously.
    """

    def __init__(self, wiki: WikiEngine = None, expert: LogAnalysisExpert = None):
        self.wiki = wiki or WikiEngine()
        self.expert = expert or LogAnalysisExpert(self.wiki)
        self._tools: dict[str, ToolDefinition] = {}
        self._last_report: Optional[AnalysisReport] = None
        self._call_log: list[dict] = []
        self._register_all()

    def _reg(self, name: str, description: str, schema: dict,
             handler: Callable, examples: list[dict] = None):
        self._tools[name] = ToolDefinition(
            name=name, description=description,
            input_schema=schema, handler=handler,
            input_examples=examples or [],
        )

    def _log_call(self, name: str, input_data: dict, duration_ms: float):
        self._call_log.append({"tool": name, "input": input_data,
                              "timestamp": time.time(), "duration_ms": round(duration_ms, 1)})

    # ═══════════════════════════════════════════
    # ANALYZE TOOLS
    # ═══════════════════════════════════════════

    def _register_all(self):
        # ─── ANALYZE ───
        self._reg("analyze_logs", (
            "Performs deep-dive analysis of raw log text. Parses log entries, detects patterns "
            "(error codes, OOM kills, failovers, timeouts, latency spikes, cache degradation, "
            "connection pool issues), correlates patterns with wiki documentation to find root "
            "causes and resolution steps, chains related events into incident timelines, checks "
            "SLA thresholds, and generates prioritized recommendations. Returns a structured "
            "analysis with severity, confidence, and incident chains."
        ), {
            "type": "object",
            "properties": {
                "log_text": {"type": "string", "description": "Raw log text to analyze"},
                "source": {"type": "string", "description": "Source identifier (e.g., 'tmf620-api')"},
            },
            "required": ["log_text"],
        }, self._analyze_logs,
        [{"log_text": "2026-04-26T08:12:01Z ERROR [api] ERR-4001 Invalid specification\\n2026-04-26T08:18:45Z ERROR [k8s] OOMKilled"}])

        self._reg("analyze_file", (
            "Analyzes a log file by filesystem path. Equivalent to analyze_logs but reads from "
            "a file instead of inline text. Returns the same structured analysis with patterns, "
            "incident chains, root causes, and recommendations."
        ), {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative path to log file"},
            },
            "required": ["path"],
        }, self._analyze_file,
        [{"path": "/var/log/tmf620-api/incident.log"}])

        self._reg("parse_logs", (
            "Parses raw log text into structured entries without deep analysis. Returns parsed "
            "entries with timestamp, severity, service, and message. Use this for quick log "
            "inspection when you don't need pattern detection or wiki correlation."
        ), {
            "type": "object",
            "properties": {
                "log_text": {"type": "string", "description": "Raw log text to parse"},
            },
            "required": ["log_text"],
        }, self._parse_logs)

        self._reg("extract_errors", (
            "Extracts only error and critical entries from log text. Useful for quickly seeing "
            "what went wrong without the noise of INFO and WARN lines."
        ), {
            "type": "object",
            "properties": {
                "log_text": {"type": "string", "description": "Raw log text"},
            },
            "required": ["log_text"],
        }, self._extract_errors)

        self._reg("filter_by_service", (
            "Filters log entries to a specific service. Returns only entries where the service "
            "name contains the filter string (case-insensitive). Useful for focusing on one "
            "component during an incident."
        ), {
            "type": "object",
            "properties": {
                "log_text": {"type": "string", "description": "Raw log text"},
                "service": {"type": "string", "description": "Service name to filter by (e.g., 'tmf620-api', 'postgres')"},
            },
            "required": ["log_text", "service"],
        }, self._filter_by_service)

        # ─── KNOWLEDGE ───
        self._reg("wiki_search", (
            "Searches the wiki knowledge base for documentation matching a query. The wiki "
            "contains ingested runbooks, troubleshooting guides, SLAs, and specifications. "
            "Returns matching pages with relevance scores and document types."
        ), {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (e.g., 'ERR-4001', 'database failover', 'SLA latency')"},
                "doc_type": {"type": "string", "enum": ["runbook", "troubleshooting", "sla", "specification", "general"],
                             "description": "Optional filter by document type"},
                "top_k": {"type": "integer", "description": "Max results (default 5)"},
            },
            "required": ["query"],
        }, self._wiki_search,
        [{"query": "ERR-4001 invalid specification"}, {"query": "database failover", "doc_type": "runbook"}])

        self._reg("ingest_document", (
            "Ingests a document into the wiki knowledge base. Supports markdown and text files. "
            "Auto-detects document type from filename (runbook, troubleshooting, sla, specification) "
            "and auto-extracts technology tags. After ingestion, the document becomes searchable "
            "and will be used during log correlation."
        ), {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to document file (.md or .txt)"},
                "doc_type": {"type": "string", "enum": ["runbook", "troubleshooting", "sla", "specification", "general"],
                             "description": "Override auto-detected document type"},
            },
            "required": ["path"],
        }, self._ingest_document)

        self._reg("ingest_directory", (
            "Ingests all .md and .txt files from a directory into the wiki. Auto-detects types "
            "and tags. Use this to bulk-load your documentation library."
        ), {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path containing documents"},
            },
            "required": ["path"],
        }, self._ingest_directory,
        [{"path": "/docs/runbooks/"}, {"path": "references/troubleshooting/"}])

        self._reg("find_runbook", (
            "Searches specifically for runbooks matching a scenario. Runbooks contain step-by-step "
            "resolution procedures for known incidents. Returns matching runbooks with source paths."
        ), {
            "type": "object",
            "properties": {
                "scenario": {"type": "string", "description": "Incident scenario (e.g., 'emergency catalog recovery', 'OOM kill')"},
            },
            "required": ["scenario"],
        }, self._find_runbook)

        self._reg("find_resolution", (
            "Looks up resolution steps for a specific error code. Searches all wiki documents "
            "for the error code and returns pages that contain it with their document types."
        ), {
            "type": "object",
            "properties": {
                "error_code": {"type": "string", "description": "Error code (e.g., 'ERR-4001', 'ERR-5002')"},
            },
            "required": ["error_code"],
        }, self._find_resolution)

        self._reg("check_sla", (
            "Checks whether a metric value breaches an SLA threshold defined in the wiki's SLA "
            "documents. Returns the threshold value, whether it's breached, and the source document."
        ), {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "description": "Metric name (e.g., 'latency', 'availability')"},
                "value": {"type": "number", "description": "Observed value (e.g., 2800 for 2800ms)"},
            },
            "required": ["metric", "value"],
        }, self._check_sla,
        [{"metric": "latency", "value": 2800}])

        # ─── REPORT ───
        self._reg("get_summary", (
            "Returns a quick summary of the last analysis performed. Includes report ID, severity, "
            "entry counts, pattern count, incident count, SLA breaches, and overall confidence. "
            "Must run analyze_logs or analyze_file first."
        ), {
            "type": "object",
            "properties": {},
        }, self._get_summary)

        self._reg("get_patterns", (
            "Returns all patterns detected in the last analysis. Patterns include error codes, "
            "OOM kills, failovers, timeouts, latency spikes, cache issues, and DB connection problems."
        ), {
            "type": "object",
            "properties": {},
        }, self._get_patterns)

        self._reg("get_incidents", (
            "Returns all incident chains from the last analysis. Incident chains group related "
            "patterns into a single incident with a timeline, blast radius, and severity."
        ), {
            "type": "object",
            "properties": {},
        }, self._get_incidents)

        self._reg("get_recommendations", (
            "Returns prioritized recommendations from the last analysis. Recommendations are "
            "ordered by priority (HIGH/MEDIUM) and confidence score."
        ), {
            "type": "object",
            "properties": {},
        }, self._get_recommendations)

        self._reg("get_timeline", (
            "Returns the incident timeline from the last analysis. Timeline events are ordered "
            "chronologically with timestamps and descriptions."
        ), {
            "type": "object",
            "properties": {},
        }, self._get_timeline)

        self._reg("get_report", (
            "Generates a full markdown report from the last analysis. Includes executive summary, "
            "statistics, incident chains with root causes and resolution steps, SLA breaches, "
            "recommendations, and knowledge sources used."
        ), {
            "type": "object",
            "properties": {},
        }, self._get_report)

        self._reg("ask_question", (
            "Asks a question about the analyzed logs. Searches both the analysis results and "
            "wiki documentation to answer. Returns matching wiki pages and relevant report data. "
            "Must run analyze_logs or analyze_file first."
        ), {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Question about the logs (e.g., 'Why did pods crash?')"},
            },
            "required": ["question"],
        }, self._ask_question,
        [{"question": "What caused the OOM kill?"}, {"question": "How do I fix ERR-4001?"}])

        # ─── UTILS ───
        self._reg("health_check", (
            "Returns system health status including wiki load state, page count, and tool availability."
        ), {
            "type": "object",
            "properties": {},
        }, self._health_check)

        self._reg("get_stats", (
            "Returns statistics about the wiki knowledge base and any completed analysis."
        ), {
            "type": "object",
            "properties": {},
        }, self._get_stats)

        self._reg("list_tools", (
            "Lists all available tools with their names, descriptions, and call counts."
        ), {
            "type": "object",
            "properties": {},
        }, self._list_tools)

    # ═══════════════════════════════════════════
    # TOOL HANDLERS
    # ═══════════════════════════════════════════

    def _analyze_logs(self, **kw):
        start = time.time()
        log_text = kw.get("log_text", "")
        report = self.expert.analyze(log_text, kw.get("source", "inline"))
        self._last_report = report
        self._log_call("analyze_logs", {"source": kw.get("source", "inline")}, (time.time()-start)*1000)
        return ToolResult("analyze_logs", report.summary, data={
            "report_id": report.report_id, "severity": report.severity.value,
            "total_entries": report.total_entries, "errors": report.error_count,
            "warnings": report.warning_count, "patterns": len(report.patterns_detected),
            "incidents": len(report.incident_chains), "sla_breaches": len(report.sla_breaches),
            "confidence": report.confidence, "analysis_time_ms": report.analysis_time_ms,
        })

    def _analyze_file(self, **kw):
        start = time.time()
        path = kw.get("path", "")
        if not os.path.exists(path):
            return ToolResult("analyze_file", f"File not found: {path}", is_error=True)
        report = self.expert.analyze_file(path)
        self._last_report = report
        self._log_call("analyze_file", {"path": path}, (time.time()-start)*1000)
        return ToolResult("analyze_file", report.summary, data={
            "report_id": report.report_id, "severity": report.severity.value,
            "total_entries": report.total_entries, "errors": report.error_count,
            "patterns": len(report.patterns_detected),
            "incidents": len(report.incident_chains), "confidence": report.confidence,
        })

    def _parse_logs(self, **kw):
        entries = self.expert.analyzer.parse(kw.get("log_text", ""))
        return ToolResult("parse_logs", f"Parsed {len(entries)} entries", data={
            "entries": [{"ts": e.timestamp, "severity": e.severity.value,
                         "service": e.service_clean, "message": e.message[:80]}
                       for e in entries],
        })

    def _extract_errors(self, **kw):
        entries = self.expert.analyzer.parse(kw.get("log_text", ""))
        errors = self.expert.analyzer.filter_by_severity(entries, Severity.ERROR)
        return ToolResult("extract_errors", f"Found {len(errors)} errors", data={
            "errors": [{"ts": e.timestamp, "service": e.service_clean,
                        "message": e.message[:100], "error_codes": e.error_codes}
                      for e in errors],
        })

    def _filter_by_service(self, **kw):
        entries = self.expert.analyzer.parse(kw.get("log_text", ""))
        filtered = self.expert.analyzer.filter_by_service(entries, kw.get("service", ""))
        return ToolResult("filter_by_service", f"Found {len(filtered)} entries", data={
            "entries": [{"ts": e.timestamp, "severity": e.severity.value, "message": e.message[:80]}
                       for e in filtered],
        })

    def _wiki_search(self, **kw):
        results = self.wiki.search(kw.get("query", ""), top_k=kw.get("top_k", 5),
                                    doc_type=kw.get("doc_type"))
        return ToolResult("wiki_search", f"Found {len(results)} pages", data={
            "results": [{"title": p.title, "type": p.doc_type, "score": round(s, 1),
                         "source": p.source, "tags": p.tags}
                       for s, p in results],
        })

    def _ingest_document(self, **kw):
        path = kw.get("path", "")
        page = self.wiki.ingest_file(path, kw.get("doc_type", "general"))
        if page:
            return ToolResult("ingest_document", f"Ingested: {page.title} [{page.doc_type}]", data={
                "title": page.title, "doc_type": page.doc_type, "tags": page.tags,
            })
        return ToolResult("ingest_document", f"Failed: {path}", is_error=True)

    def _ingest_directory(self, **kw):
        count = self.wiki.ingest_directory(kw.get("path", ""))
        return ToolResult("ingest_directory", f"Ingested {count} documents", data={"count": count})

    def _find_runbook(self, **kw):
        pages = self.wiki.find_runbook(kw.get("scenario", ""))
        return ToolResult("find_runbook", f"Found {len(pages)} runbooks", data={
            "runbooks": [{"title": p.title, "source": p.source} for p in pages],
        })

    def _find_resolution(self, **kw):
        pages = self.wiki.find_resolution(kw.get("error_code", ""))
        return ToolResult("find_resolution", f"Found {len(pages)} pages", data={
            "pages": [{"title": p.title, "type": p.doc_type, "source": p.source} for p in pages],
        })

    def _check_sla(self, **kw):
        result = self.wiki.check_sla(kw.get("metric", ""), float(kw.get("value", 0)))
        if result:
            return ToolResult("check_sla",
                f"{'BREACHED' if result['breached'] else 'OK'}: {result['metric']}={result['value']} (threshold: {result['threshold']})",
                data=result)
        return ToolResult("check_sla", "No SLA threshold found for this metric")

    def _get_summary(self, **kw):
        r = self._last_report
        if not r:
            return ToolResult("get_summary", "No analysis performed yet. Run analyze_logs first.", is_error=True)
        return ToolResult("get_summary", r.summary, data={
            "report_id": r.report_id, "severity": r.severity.value,
            "total_entries": r.total_entries, "errors": r.error_count,
            "warnings": r.warning_count, "patterns": len(r.patterns_detected),
            "incidents": len(r.incident_chains), "sla_breaches": len(r.sla_breaches),
            "confidence": r.confidence,
        })

    def _get_patterns(self, **kw):
        if not self._last_report:
            return ToolResult("get_patterns", "No analysis yet", is_error=True)
        return ToolResult("get_patterns", f"{len(self._last_report.patterns_detected)} patterns", data={
            "patterns": self._last_report.patterns_detected,
        })

    def _get_incidents(self, **kw):
        if not self._last_report:
            return ToolResult("get_incidents", "No analysis yet", is_error=True)
        return ToolResult("get_incidents", f"{len(self._last_report.incident_chains)} incidents", data={
            "incidents": self._last_report.incident_chains,
        })

    def _get_recommendations(self, **kw):
        if not self._last_report:
            return ToolResult("get_recommendations", "No analysis yet", is_error=True)
        return ToolResult("get_recommendations", f"{len(self._last_report.recommendations)} recommendations", data={
            "recommendations": self._last_report.recommendations,
        })

    def _get_timeline(self, **kw):
        if not self._last_report:
            return ToolResult("get_timeline", "No analysis yet", is_error=True)
        timeline = []
        for chain in self._last_report.incident_chains:
            timeline.extend(chain.get("timeline", []))
        return ToolResult("get_timeline", f"{len(timeline)} events", data={"timeline": timeline})

    def _get_report(self, **kw):
        if not self._last_report:
            return ToolResult("get_report", "No analysis yet", is_error=True)
        md = self._last_report.to_markdown()
        return ToolResult("get_report", f"Report: {self._last_report.report_id}", data={
            "markdown": md, "report_id": self._last_report.report_id,
            "size_chars": len(md),
        })

    def _ask_question(self, **kw):
        question = kw.get("question", "")
        if not self._last_report:
            return ToolResult("ask_question", "No analysis yet. Run analyze_logs first.", is_error=True)
        wiki_results = self.wiki.search(question)
        return ToolResult("ask_question", f"Answer for: {question}", data={
            "wiki_matches": [{"title": p.title, "type": p.doc_type, "score": round(s, 1)}
                            for s, p in wiki_results],
            "report_summary": self._last_report.summary,
            "patterns": self._last_report.patterns_detected,
            "incidents": [{"id": c["chain_id"], "severity": c["severity"], "services": c["blast_radius"]}
                         for c in self._last_report.incident_chains],
            "recommendations": [{"title": r["title"], "priority": r["priority"]}
                               for r in self._last_report.recommendations],
        })

    def _health_check(self, **kw):
        return ToolResult("health_check", "System healthy", data={
            "wiki_loaded": self.wiki.total_pages > 0,
            "wiki_pages": self.wiki.total_pages,
            "wiki_doc_types": self.wiki.doc_types,
            "tools_available": len(self._tools),
            "analyses_performed": len(self._call_log),
        })

    def _get_stats(self, **kw):
        return ToolResult("get_stats", "Statistics", data={
            "wiki": {"total_pages": self.wiki.total_pages, "doc_types": self.wiki.doc_types},
            "last_report": self._last_report.report_id if self._last_report else None,
            "tool_calls": len(self._call_log),
            "tools_available": len(self._tools),
        })

    def _list_tools(self, **kw):
        return ToolResult("list_tools", f"{len(self._tools)} tools available", data={
            "tools": [{"name": t.name, "description": t.description[:80],
                       "has_schema": bool(t.input_schema)}
                      for t in sorted(self._tools.values(), key=lambda t: t.name)],
        })

    # ═══════════════════════════════════════════
    # EXECUTION INTERFACE
    # ═══════════════════════════════════════════

    def call(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name (equivalent to Anthropic's tool_use handling)."""
        start = time.time()
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(tool_name, f"Unknown tool: {tool_name}. "
                            f"Available: {', '.join(sorted(self._tools.keys()))}", is_error=True)
        result = tool.handler(**kwargs)
        if not isinstance(result, ToolResult):
            result = ToolResult(tool_name, str(result))
        self._log_call(tool_name, kwargs, (time.time() - start) * 1000)
        return result

    def get_tool_definitions(self) -> list[dict]:
        """Export all tools in Anthropic API format."""
        return [t.to_anthropic_format() for t in sorted(self._tools.values(), key=lambda t: t.name)]

    def get_system_prompt(self) -> str:
        """Generate system prompt with tool descriptions for LLM."""
        tools_json = json.dumps(self.get_tool_definitions(), indent=2)
        return (
            "You are APILoganalysisExpert, an expert log analysis agent with access to the following tools.\n"
            "Use these tools to analyze production logs, search documentation, and produce incident reports.\n\n"
            f"Available tools:\n{tools_json}\n\n"
            "Guidelines:\n"
            "- Always ingest relevant documentation before analyzing logs\n"
            "- Use wiki_search to find relevant docs before answering questions\n"
            "- Use analyze_logs for full analysis, parse_logs for quick inspection\n"
            "- Use get_report to generate the final markdown report\n"
            "- Cite wiki sources in your responses\n"
        )

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def call_log(self) -> list[dict]:
        return list(self._call_log)
