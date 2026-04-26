---
name: cortex-analyst
description: Wiki-aware log analysis agent. Ingest runbooks, troubleshooting guides, SLAs, and API specs. Analyze production logs, detect 12 pattern types (error codes, OOM kills, failovers, timeouts, latency spikes, cache degradation, DB connection issues). Cross-reference patterns with wiki docs for root cause analysis and resolution steps. Generate incident reports with SLA breach detection. Exposes 21 Anthropic-style tools with JSON Schema definitions. Tested against TMF620 telecom incident logs.
version: 1.0.0
homepage: https://github.com/rohitsalesforce132/cortex-analyst
metadata: {"openclaw":{"emoji":"🧠","requires":{"anyBins":["python3"],"optionalBins":["pytest"],"configPaths":["~/.openclaw/workspace/cortex-analyst/references/"],"os":["darwin","linux"]}}}
---

# Cortex Analyst — Wiki-Aware Log Analysis Agent

Log analysis agent that combines knowledge retrieval (runbooks, SLAs, troubleshooting) with pattern detection and incident correlation. Exposes everything through 21 Anthropic-compatible tools.

## Prerequisites

```bash
# No pip installs needed — pure Python standard library
cd ~/.openclaw/workspace/cortex-analyst
python3 -c "from src.tools import ToolRegistry; print('OK')"
```

Repo: [github.com/rohitsalesforce132/cortex-analyst](https://github.com/rohitsalesforce132/cortex-analyst)

## Scope

This skill provides deep-dive production log analysis with wiki knowledge correlation. Use when:
- Analyzing production incident logs (any format: tmf620, kubernetes, application logs)
- Finding root causes by cross-referencing logs with runbooks/troubleshooting docs
- Checking SLA breaches against documented thresholds
- Generating incident reports with timelines and recommendations
- Answering questions about what went wrong and how to fix it

NOT for: real-time log streaming (batch analysis only), log aggregation (use ELK), alerting (use PagerDuty).

## Setup

```python
import sys
sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace/cortex-analyst"))

from src.tools import ToolRegistry
from src.wiki_engine import WikiEngine

# Create agent
wiki = WikiEngine()
agent = ToolRegistry(wiki=wiki)

# Load documentation (do once, reuse agent)
agent.call("ingest_directory", path="references/runbooks/")
agent.call("ingest_directory", path="references/troubleshooting/")
agent.call("ingest_directory", path="references/sla/")
```

## Tools (21 — Anthropic-compatible)

All tools return `ToolResult` with `output` (human text), `is_error` (bool), and `data` (structured dict).

### ANALYZE Tools

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `analyze_logs` | Full deep-dive analysis of raw log text | `log_text` |
| `analyze_file` | Analyze a log file by path | `path` |
| `parse_logs` | Quick parse without deep analysis | `log_text` |
| `extract_errors` | Extract only ERROR/CRITICAL entries | `log_text` |
| `filter_by_service` | Filter logs by service name | `log_text`, `service` |

### KNOWLEDGE Tools

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `wiki_search` | Search wiki documentation | `query` |
| `ingest_document` | Add one document to wiki | `path` |
| `ingest_directory` | Bulk-load docs from folder | `path` |
| `find_runbook` | Find runbooks for a scenario | `scenario` |
| `find_resolution` | Find resolution for error code | `error_code` |
| `check_sla` | Check metric against SLA threshold | `metric`, `value` |

### REPORT Tools

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `get_summary` | Quick analysis summary | (none — needs prior analysis) |
| `get_patterns` | All detected patterns | (none) |
| `get_incidents` | Incident chains with timelines | (none) |
| `get_recommendations` | Prioritized action items | (none) |
| `get_timeline` | Chronological event timeline | (none) |
| `get_report` | Full markdown report | (none) |
| `ask_question` | Q&A over analysis + wiki | `question` |

### UTILITY Tools

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `health_check` | System health status | (none) |
| `get_stats` | Wiki + analysis statistics | (none) |
| `list_tools` | List all available tools | (none) |

## Usage Examples

### Example 1: Analyze a production incident

```python
# Load docs + analyze in 3 lines
agent.call("ingest_directory", path="/docs/runbooks/")
agent.call("ingest_directory", path="/docs/troubleshooting/")
result = agent.call("analyze_file", path="/var/log/incident.log")

# Get results
report = agent.call("get_report")
print(report.data["markdown"])  # Full markdown report
```

### Example 2: Quick error lookup

```python
agent.call("ingest_directory", path="references/troubleshooting/")
result = agent.call("find_resolution", error_code="ERR-4001")
for page in result.data["pages"]:
    print(f"{page['title']}: {page['source']}")
```

### Example 3: SLA breach check

```python
agent.call("ingest_document", path="references/sla/tmf620-sla.md")
result = agent.call("check_sla", metric="latency", value=2800)
# → "BREACHED: latency=2800.0 (threshold: 500.0)"
```

### Example 4: Ask questions about analyzed logs

```python
agent.call("analyze_logs", log_text=log_data)
answer = agent.call("ask_question", question="Why did pods crash?")
print(answer.data["wiki_matches"])      # Matching wiki pages
print(answer.data["incidents"])         # Related incidents
print(answer.data["recommendations"])   # Action items
```

### Example 5: Export tool definitions for Anthropic API

```python
tools = agent.get_tool_definitions()   # JSON Schema format
prompt = agent.get_system_prompt()      # System prompt with tool descriptions

# Pass to Anthropic API
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    tools=tools,
    system=prompt,
    messages=[{"role": "user", "content": "Analyze /var/log/incident.log"}]
)
```

## Pattern Detection (7 types)

| Pattern Type | What It Detects | Example |
|-------------|----------------|---------|
| `error_code` | ERR-NNNN codes | ERR-4001, ERR-5002 |
| `oom` | OOM kills, exit code 137 | "OOMKilled", "memory" + "kill" |
| `failover` | DB/cache failovers | "failover", "promoting replica", "split-brain" |
| `timeout` | Service timeouts | "timeout after 5000ms" |
| `latency_spike` | P95/P99 spikes | "P95 latency spike: 2800ms" |
| `cache_issue` | Cache degradation | "cache hit rate dropped to 42%" |
| `db_connection` | Connection pool issues | "connection refused", "pool exhausted" |

## Knowledge Base Structure

```
references/
├── runbooks/              # Step-by-step incident procedures
├── troubleshooting/       # Error code resolution guides
├── sla/                   # Service level agreements with thresholds
├── specification/         # API specs and product documentation
└── sample-logs/           # Test incident logs
```

Drop your own `.md` or `.txt` files into any subfolder — the wiki auto-detects document type from filename and extracts technology tags (kubernetes, postgresql, redis, tmf620, etc.).

## Running Tests

```bash
cd ~/.openclaw/workspace/cortex-analyst
pytest tests/ -v   # 43 tests, 0 failures
```
