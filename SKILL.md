---
name: APILoganalysisExpert
description: Analyze production errors and logs instantly. Paste any error, log snippet, or error code — get root cause analysis, resolution steps, SLA breach detection, and runbook references. Hybrid engine combining deterministic pattern detection (21 tools) with LLM reasoning for deep contextual analysis. Supports TMF620 API errors, Kubernetes pod crashes, database failovers, OOM kills, latency spikes, and cache degradation.
version: 2.0.0
homepage: https://github.com/rohitsalesforce132/logagent
---

# 🧠 APILoganalysisExpert — Production Error & Log Analysis Skill

When the user pastes an error, log snippet, error code, or describes a production issue, analyze it using this two-layer approach.

## Architecture: Hybrid Analysis (Deterministic + LLM)

```
User Input (error/logs)
        │
        ▼
┌─────────────────────┐
│  Layer 1: Engine     │  ← scan.py (deterministic, ~100ms, 0 tokens)
│  - Parse logs        │
│  - Detect patterns   │
│  - Search wiki       │
│  - Check SLAs        │
│  - Find runbooks     │
└────────┬────────────┘
         │ JSON output
         ▼
┌─────────────────────┐
│  Layer 2: LLM        │  ← You (Opus/Claude), contextual reasoning
│  - Interpret results  │
│  - Explain root cause │
│  - Suggest fixes      │
│  - Correlate across   │
│    systems            │
│  - Risk assessment    │
└─────────────────────┘
         │
         ▼
   Rich Analysis Report
```

## How to Use This Skill

### Step 1: Run the deterministic engine

The repo is at: `/home/rohit/.gemini/antigravity/scratch/log-analysis-agent`

**For short errors** (no timestamps):
```bash
cd /home/rohit/.gemini/antigravity/scratch/log-analysis-agent && python3 scan.py "USER_ERROR_TEXT_HERE" --json
```

**For multi-line logs** (with timestamps), write to temp file first:
```bash
cat > /tmp/apilog_input.log << 'LOGEOF'
USER_LOG_TEXT_HERE
LOGEOF
cd /home/rohit/.gemini/antigravity/scratch/log-analysis-agent && python3 scan.py < /tmp/apilog_input.log --json
```

### Step 2: Read relevant reference docs

Based on the scan output, read the most relevant wiki docs to build deeper context:

- **Error codes found?** → Read `references/specification/tmf620-troubleshooting.md`
- **SLA concern?** → Read `references/specification/tmf620-sla.md`
- **Need runbook?** → Read `references/runbooks/emergency-catalog-recovery.md`
- **API question?** → Read `references/specification/tmf620-specification.md`
- **Operational issue?** → Read `references/specification/tmf620-runbook.md`

### Step 3: LLM Analysis Layer

Using the scan.py JSON output AND the reference docs, provide a comprehensive analysis:

#### Analysis Report Format

```
## 🧠 APILoganalysisExpert — [Error Type] Analysis

### Severity: [CRITICAL/ERROR/WARN] [emoji]

### What Happened
[Plain language explanation of the error, what it means in context]

### Root Cause
[Deep analysis combining scan results + wiki docs + LLM reasoning]
[Explain WHY this happened, not just WHAT happened]

### Impact Assessment
- **Blast Radius:** [Which services/users are affected]
- **SLA Impact:** [Any threshold breaches]
- **Data Risk:** [Any data integrity concerns]

### Resolution Steps
[Numbered, actionable steps with actual commands]

### Recommendations
[Prioritized table of actions: P1/P2/P3]

### Related Patterns
[If the error could be part of a larger incident chain, explain]
```

#### LLM Analysis Guidelines

1. **Go beyond the raw output** — Don't just repeat what scan.py returns. Add reasoning about WHY the error occurred, what the downstream effects could be, and what the user should worry about.

2. **Cross-reference systems** — If a TMF620 error could be caused by a Kubernetes issue, PostgreSQL failure, or Redis split-brain, explain the connection.

3. **Estimate urgency** — Based on the error pattern, tell the user if this is "fix now" or "monitor and investigate".

4. **Suggest preventive measures** — After the fix, recommend what to put in place so it doesn't happen again (alerts, pre-validation hooks, circuit breakers).

5. **Ask clarifying questions** — If the error is ambiguous, ask the user for more context (which endpoint, when it started, is it intermittent or constant).

## Supported Error Types

| Type | Examples |
|------|----------|
| TMF620 API errors | ERR-4001, ERR-4003, ERR-5001, ERR-4221, HTTP 403/400/500 |
| Kubernetes | OOMKilled, CrashLoopBackOff, exit code 137, pod eviction |
| Database | Connection refused, failover, split-brain, slow queries |
| Cache | Redis CLUSTERDOWN, cache hit rate drops |
| Performance | P95 latency spikes, query timeouts |
| Auth/Security | HTTP 403 Forbidden, token expired, credentials rejected |

## 21 Tools Available

### ANALYZE (5)
| Tool | Description | Params |
|------|-------------|--------|
| `analyze_logs` | Full deep-dive with pattern detection + correlation | `log_text` |
| `analyze_file` | Analyze log file by path | `path` |
| `parse_logs` | Quick parse without deep analysis | `log_text` |
| `extract_errors` | Extract ERROR/CRITICAL entries only | `log_text` |
| `filter_by_service` | Filter by service name | `log_text`, `service` |

### KNOWLEDGE (7)
| Tool | Description | Params |
|------|-------------|--------|
| `wiki_search` | Search wiki documentation | `query` |
| `ingest_document` | Add one doc to wiki | `path` |
| `ingest_directory` | Bulk-load docs from folder | `path` |
| `find_runbook` | Find runbooks for scenario | `scenario` |
| `find_resolution` | Resolution for error code | `error_code` |
| `check_sla` | Check metric against SLA | `metric`, `value` |

### REPORT (7)
| Tool | Description | Params |
|------|-------------|--------|
| `get_summary` | Quick analysis summary | — |
| `get_patterns` | All detected patterns | — |
| `get_incidents` | Incident chains | — |
| `get_recommendations` | Prioritized actions | — |
| `get_timeline` | Chronological timeline | — |
| `get_report` | Full markdown report | — |
| `ask_question` | Q&A over analysis + wiki | `question` |

### UTILITY (3)
| Tool | Description | Params |
|------|-------------|--------|
| `health_check` | System health | — |
| `get_stats` | Wiki + analysis stats | — |
| `list_tools` | List all tools | — |

## Pattern Detection (7 types)

| Pattern | Detects | Example |
|---------|---------|---------|
| `error_code` | ERR-NNNN codes | ERR-4001, ERR-5002 |
| `oom` | OOM kills, exit code 137 | OOMKilled, memory kill |
| `failover` | DB/cache failovers | split-brain, promoting replica |
| `timeout` | Service timeouts | timeout after 5000ms |
| `latency_spike` | P95/P99 spikes | P95 latency: 2800ms |
| `cache_issue` | Cache degradation | cache hit rate dropped 42% |
| `db_connection` | Connection pool issues | connection refused |

## Knowledge Base

```
references/
├── troubleshooting/       # Error resolution guides
├── runbooks/              # Step-by-step incident procedures
├── sla/                   # SLA thresholds
├── specification/         # TMF620 API specs, extended troubleshooting, runbooks
└── sample-logs/           # Test incident logs
```

Add `.md` files to extend — the wiki auto-detects doc type and extracts technology tags.

## Running Tests

```bash
cd /home/rohit/.gemini/antigravity/scratch/log-analysis-agent
pytest tests/ -v
```
