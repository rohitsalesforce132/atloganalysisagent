# STAR.md — APILoganalysisExpert: Wiki-Aware Log Analysis Agent

## Opening Line
> "I built a wiki-aware log analysis agent called APILoganalysisExpert that combines a knowledge engine with a log analysis expert into a single Anthropic-style agent. It has 4 subsystems — a Wiki Knowledge Engine that ingests runbooks, troubleshooting guides, SLAs, and API specifications into a searchable knowledge base; a Log Analyzer that parses raw logs and detects 7 pattern types including OOM kills, database failovers, and timeout cascades; a Correlator that cross-references detected patterns with wiki documentation to extract root causes and resolution steps with confidence scoring; and an Expert Agent that chains events into incident timelines with SLA breach detection. All 21 operations are exposed as Anthropic-compatible tools with proper JSON Schema definitions, input examples, and detailed descriptions — following the exact tool-use specification from Anthropic's documentation. 43 tests, zero failures, tested against real TMF620 incident logs with production reference documents."

## Situation
Production incidents generate log floods across multiple services. Engineers manually grep, search Confluence for runbooks, check SLA docs, and try to correlate events — all under P1 time pressure. Existing tools (ELK, Datadog) show what happened, not why or how to fix it. The new generation of AI agents (Claude, GPT) can reason about logs, but they need structured tools to access institutional knowledge. Anthropic's tool-use specification defines how agents should expose capabilities — with JSON Schema, detailed descriptions, and the agentic loop where the model decides which tool to call.

## Task
Build a unified agent that combines a wiki knowledge engine (for documentation retrieval) with a log analysis expert (for pattern detection and incident correlation), all exposed through Anthropic-compatible tool definitions with proper JSON Schema, detailed descriptions, and input examples. The agent must work with real production documents and real incident logs.

## Action
Designed and implemented 4 subsystems as a unified agent with 21 tools:

1. **Wiki Knowledge Engine** (`src/wiki_engine/`) — Ingests documents (runbooks, troubleshooting guides, SLAs, specifications) from files and directories. Auto-detects document type from filename. Auto-extracts technology tags (Kubernetes, PostgreSQL, Redis, TMF620). Searches by keyword overlap + tag bonus. Extracts SLA thresholds from structured tables. Finds resolution steps from numbered/bulleted lists.

2. **Log Analyzer** (`src/analyzer/`) — Parses raw logs with ISO 8601 timestamps. Classifies severity (INFO/WARN/ERROR/CRITICAL). Extracts error codes (ERR-NNNN), HTTP status codes, and service names. Detects 7 pattern types: error codes, OOM kills (exit code 137), database failovers (Patroni, split-brain), timeout cascades, latency spikes (P95), cache degradation (hit rate drops), and connection pool exhaustion. Supports filtering by severity, service, and time range.

3. **Log Correlator** (`src/correlator/`) — Cross-references detected patterns with wiki knowledge. Builds search queries from pattern context. Extracts root cause from "Root Cause:" sections in wiki docs. Extracts resolution steps from numbered lists. Checks SLA thresholds for performance patterns. Scores confidence (0-1) based on wiki match quality + error code specificity + runbook match bonus. Chains related correlations into incident chains (shared service or shared wiki pages).

4. **Tool Registry** (`src/tools/`) — 21 Anthropic-compatible tools organized into 4 categories:
   - ANALYZE: `analyze_logs`, `analyze_file`, `parse_logs`, `extract_errors`, `filter_by_service`
   - KNOWLEDGE: `wiki_search`, `ingest_document`, `ingest_directory`, `find_runbook`, `find_resolution`, `check_sla`
   - REPORT: `get_summary`, `get_patterns`, `get_incidents`, `get_recommendations`, `get_timeline`, `get_report`, `ask_question`
   - UTILS: `health_check`, `get_stats`, `list_tools`

   Each tool has: `name` (matching ^[a-zA-Z0-9_-]{1,64}$), `description` (50+ chars explaining what/when/how), `input_schema` (JSON Schema), and optional `input_examples`. The `get_tool_definitions()` method exports all tools in Anthropic API format. The `get_system_prompt()` generates a complete system prompt with tool descriptions for LLM consumption.

## Result
- **43 tests, 0 failures** — all subsystems + tools + end-to-end workflows
- **21 Anthropic-compatible tools** with JSON Schema and detailed descriptions
- **Real production documents** in `references/` (runbooks, troubleshooting, SLAs, specifications)
- **Real TMF620 incident log** (38 lines, 6+ error codes, OOM, failover, split-brain, latency spike)
- **Zero external dependencies** — pure Python standard library

## Follow-Up Questions

**Q: How do the Anthropic-style tools work?**
Each tool is defined with a name, description, and JSON Schema input_schema — exactly as Anthropic's API expects. When an LLM receives a user request like "Why did my pods crash?", it reads the tool descriptions and decides to call `analyze_file` with the log path, then `find_runbook` with "OOM kill", then `get_report`. The `get_tool_definitions()` method returns the exact JSON you'd pass to the Anthropic API's `tools` parameter.

**Q: Why JSON Schema for tool definitions?**
JSON Schema lets the LLM know exactly what parameters to provide — which are required, what types they expect, and valid enum values. This prevents hallucinated parameters and ensures the model calls tools correctly. Anthropic's tool-use spec requires it.

**Q: How does the agentic loop work?**
1. User sends request + tool definitions to the LLM
2. LLM decides which tool to call and with what parameters
3. Application executes the tool via `registry.call(tool_name, **params)`
4. Result returned as `tool_result` to the LLM
5. LLM decides next action (call another tool or respond)
6. Repeat until the LLM has enough information to answer

**Q: How would you connect this to a real LLM?**
Export tool definitions via `get_tool_definitions()`, generate system prompt via `get_system_prompt()`, then send both to the Anthropic API. Handle `tool_use` stop reasons by calling `registry.call()` with the extracted parameters. Feed results back as `tool_result` blocks.

## Key Skills Demonstrated
- Agent tool design (Anthropic tool-use specification, JSON Schema)
- Knowledge base engineering (wiki-driven root cause analysis)
- Production log analysis (7 pattern types, incident chaining)
- API design (Anthropic-compatible tool registry)
- SRE practices (SLA breach detection, runbook automation)
