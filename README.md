# Cortex Analyst — Wiki-Aware Log Analysis Agent

An AI agent that combines a knowledge engine (runbooks, SLAs, troubleshooting) with a log analysis expert, exposed through Anthropic-style tool definitions.

## Quick Start

```bash
pytest tests/ -v   # 43 tests, 0 failures
```

## Agent Tools (21 — Anthropic-compatible)

```python
from src.tools import ToolRegistry
from src.wiki_engine import WikiEngine

wiki = WikiEngine()
agent = ToolRegistry(wiki=wiki)

# Load your documentation
agent.call("ingest_directory", path="references/runbooks/")
agent.call("ingest_directory", path="references/troubleshooting/")
agent.call("ingest_directory", path="references/sla/")

# Analyze production logs
agent.call("analyze_file", path="references/sample-logs/tmf620-incident.log")

# Ask questions
agent.call("ask_question", question="Why did pods crash?")
agent.call("find_runbook", scenario="emergency catalog recovery")
agent.call("check_sla", metric="latency", value=2800)

# Get results
agent.call("get_report")           # Full markdown report
agent.call("get_incidents")        # Incident chains
agent.call("get_recommendations")  # Prioritized actions
agent.call("get_timeline")         # Event timeline

# Export for Anthropic API
tools = agent.get_tool_definitions()  # JSON Schema format
prompt = agent.get_system_prompt()    # System prompt with tool descriptions
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Cortex Analyst Agent                   │
│                                                         │
│  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │  references/         │  │  Tool Registry (21)      │  │
│  │  ├── runbooks/       │  │  ├── analyze_logs        │  │
│  │  ├── troubleshooting/│──│  ├── analyze_file         │  │
│  │  ├── sla/            │  │  ├── wiki_search          │  │
│  │  ├── specification/  │  │  ├── find_runbook         │  │
│  │  └── sample-logs/    │  │  ├── check_sla            │  │
│  └─────────────────────┘  │  ├── get_report            │  │
│                           │  ├── ask_question           │  │
│  ┌─────────────────────┐  │  └── list_tools             │  │
│  │  Wiki Knowledge      │  └───────────┬─────────────┘  │
│  │  Engine              │              │                 │
│  │  (Search + Tags)     │              ▼                 │
│  └──────────┬──────────┘  ┌─────────────────────────┐   │
│             │              │  Expert Agent            │   │
│             ▼              │  Parse → Detect →        │   │
│  ┌─────────────────────┐  │  Correlate → Chain →     │   │
│  │  Log Correlator      │  │  Recommend → Report     │   │
│  │  (Root Cause +       │  └─────────────────────────┘   │
│  │   Confidence Score)  │                                │
│  └─────────────────────┘                                 │
└─────────────────────────────────────────────────────────┘
```

## Folder Structure

```
cortex-analyst/
├── references/                    # Production knowledge base
│   ├── runbooks/                  # Step-by-step incident procedures
│   ├── troubleshooting/           # Error code resolution guides
│   ├── sla/                       # Service level agreements
│   ├── specification/             # API specs and product docs
│   └── sample-logs/               # Test incident logs
├── src/
│   ├── wiki_engine/               # Knowledge ingestion + search
│   ├── analyzer/                  # Log parsing + pattern detection
│   ├── correlator/                # Wiki cross-reference engine
│   ├── expert/                    # Orchestrator + report generator
│   └── tools/                     # 21 Anthropic-style agent tools
├── tests/
│   └── test_all.py                # 43 tests, 0 failures
├── STAR.md                        # Interview-ready summary
└── README.md
```

## See Also
- [STAR.md](STAR.md) — Interview-ready project summary
- [references/](references/) — Production documentation library
