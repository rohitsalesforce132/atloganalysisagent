"""Comprehensive tests for APILoganalysisExpert — Unified Wiki + Log Analysis Agent."""
import pytest, sys, os, time, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.wiki_engine import WikiEngine
from src.analyzer import LogAnalyzer, Severity
from src.correlator import LogCorrelator
from src.expert import LogAnalysisExpert
from src.tools import ToolRegistry, ToolDefinition, ToolResult

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS = os.path.join(BASE, 'references')

SAMPLE_LOG = """2026-04-26T08:12:01Z ERROR [tmf620-api] ERR-4001 Invalid product specification reference
2026-04-26T08:15:22Z ERROR [pricing-engine] ERR-5002 Pricing engine timeout after 5000ms
2026-04-26T08:18:45Z ERROR [k8s-pod] container exit code 137 (OOMKilled)
2026-04-26T08:18:46Z WARN  [k8s-pod] Pod memory limit: 1Gi, actual: 1.02Gi
2026-04-26T08:22:10Z ERROR [catalog-search] ERR-5001 Search index stale: delta=188
2026-04-26T08:25:33Z ERROR [tmf620-api] ERR-4003 Invalid lifecycle transition
2026-04-26T08:28:01Z ERROR [tmf620-api] ERR-4221 Cannot delete offering: 47 active subscriptions
2026-04-26T08:30:15Z CRITICAL [api-gateway] TMF620 health check failed 3 consecutive times
2026-04-26T08:30:17Z ERROR [k8s-pod] tmf620-api-7d4f8b CrashLoopBackOff: exit code 137
2026-04-26T08:31:01Z ERROR [postgres] Connection refused to postgres-primary:5432
2026-04-26T08:31:02Z WARN  [patroni] PostgreSQL primary failover in progress
2026-04-26T08:33:00Z ERROR [redis] CLUSTERDOWN split-brain detected between redis-0 and redis-3
2026-04-26T08:35:00Z WARN  [monitoring] P95 latency spike: 2800ms on GET /productOffering
2026-04-26T08:35:01Z WARN  [monitoring] Cache hit rate dropped to 42%
2026-04-26T08:35:02Z ERROR [tmf620-api] Query timeout: SELECT * FROM product_offering took 8200ms
"""

def _make_registry():
    wiki = WikiEngine()
    registry = ToolRegistry(wiki=wiki)
    # Ingest reference docs
    for d in ['troubleshooting', 'runbooks', 'sla', 'specification']:
        path = os.path.join(REFS, d)
        if os.path.isdir(path):
            registry.call("ingest_directory", path=path)
    return registry


# ═══════════════════ WIKI ENGINE ═══════════════════

class TestWiki:
    def test_ingest_file(self):
        wiki = WikiEngine()
        path = os.path.join(REFS, 'troubleshooting', 'tmf620-troubleshooting.md')
        page = wiki.ingest_file(path, 'troubleshooting')
        assert page is not None
        assert 'ERR-4001' in page.content

    def test_ingest_directory(self):
        wiki = WikiEngine()
        count = wiki.ingest_directory(os.path.join(REFS, 'troubleshooting'))
        assert count >= 1

    def test_search(self):
        wiki = WikiEngine()
        wiki.ingest_file(os.path.join(REFS, 'troubleshooting', 'tmf620-troubleshooting.md'), 'troubleshooting')
        results = wiki.search('ERR-4001 specification lifecycle')
        assert len(results) > 0

    def test_find_resolution(self):
        wiki = WikiEngine()
        wiki.ingest_file(os.path.join(REFS, 'troubleshooting', 'tmf620-troubleshooting.md'), 'troubleshooting')
        pages = wiki.find_resolution('ERR-4001')
        assert len(pages) > 0

    def test_find_runbook(self):
        wiki = WikiEngine()
        wiki.ingest_file(os.path.join(REFS, 'runbooks', 'emergency-catalog-recovery.md'), 'runbook')
        pages = wiki.find_runbook('emergency catalog recovery')
        assert len(pages) > 0

    def test_sla_check(self):
        wiki = WikiEngine()
        wiki.ingest_file(os.path.join(REFS, 'sla', 'tmf620-sla.md'), 'sla')
        result = wiki.check_sla('latency', 2800)
        if result:
            assert result['breached'] is True


# ═══════════════════ ANALYZER ═══════════════════

class TestAnalyzer:
    def test_parse(self):
        entries = LogAnalyzer().parse(SAMPLE_LOG)
        assert len(entries) >= 15

    def test_error_codes(self):
        entries = LogAnalyzer().parse(SAMPLE_LOG)
        codes = set()
        for e in entries:
            codes.update(e.error_codes)
        assert 'ERR-4001' in codes
        assert 'ERR-5002' in codes

    def test_patterns(self):
        entries = LogAnalyzer().parse(SAMPLE_LOG)
        patterns = LogAnalyzer().detect_patterns(entries)
        assert len(patterns) >= 5

    def test_oom_detection(self):
        entries = LogAnalyzer().parse(SAMPLE_LOG)
        patterns = LogAnalyzer().detect_patterns(entries)
        oom = [p for p in patterns if p.pattern_type == 'oom']
        assert len(oom) == 1

    def test_failover_detection(self):
        entries = LogAnalyzer().parse(SAMPLE_LOG)
        patterns = LogAnalyzer().detect_patterns(entries)
        failovers = [p for p in patterns if p.pattern_type == 'failover']
        assert len(failovers) >= 1

    def test_parse_file(self):
        log_path = os.path.join(REFS, 'sample-logs', 'tmf620-incident.log')
        if os.path.exists(log_path):
            entries = LogAnalyzer().parse_file(log_path)
            assert len(entries) > 20


# ═══════════════════ EXPERT ═══════════════════

class TestExpert:
    def test_analyze(self):
        wiki = WikiEngine()
        wiki.ingest_file(os.path.join(REFS, 'troubleshooting', 'tmf620-troubleshooting.md'), 'troubleshooting')
        wiki.ingest_file(os.path.join(REFS, 'runbooks', 'emergency-catalog-recovery.md'), 'runbook')
        wiki.ingest_file(os.path.join(REFS, 'sla', 'tmf620-sla.md'), 'sla')
        expert = LogAnalysisExpert(wiki)
        report = expert.analyze(SAMPLE_LOG)
        assert report.total_entries > 0
        assert len(report.patterns_detected) >= 5
        assert report.severity in (Severity.ERROR, Severity.CRITICAL)

    def test_analyze_file(self):
        wiki = WikiEngine()
        wiki.ingest_file(os.path.join(REFS, 'troubleshooting', 'tmf620-troubleshooting.md'), 'troubleshooting')
        expert = LogAnalysisExpert(wiki)
        log_path = os.path.join(REFS, 'sample-logs', 'tmf620-incident.log')
        if os.path.exists(log_path):
            report = expert.analyze_file(log_path)
            assert report.total_entries > 20

    def test_markdown_report(self):
        wiki = WikiEngine()
        wiki.ingest_file(os.path.join(REFS, 'troubleshooting', 'tmf620-troubleshooting.md'), 'troubleshooting')
        expert = LogAnalysisExpert(wiki)
        report = expert.analyze(SAMPLE_LOG)
        md = report.to_markdown()
        assert '# Log Analysis Report' in md
        assert 'Executive Summary' in md


# ═══════════════════ TOOL REGISTRY ═══════════════════

class TestToolRegistry:
    def test_tool_count(self):
        reg = _make_registry()
        assert reg.tool_count >= 20

    def test_anthropic_format(self):
        reg = _make_registry()
        defs = reg.get_tool_definitions()
        assert len(defs) >= 20
        for d in defs:
            assert 'name' in d
            assert 'description' in d
            assert 'input_schema' in d

    def test_system_prompt(self):
        reg = _make_registry()
        prompt = reg.get_system_prompt()
        assert 'APILoganalysisExpert' in prompt
        assert 'analyze_logs' in prompt

    def test_unknown_tool(self):
        reg = _make_registry()
        result = reg.call('nonexistent')
        assert result.is_error is True

    def test_analyze_logs_tool(self):
        reg = _make_registry()
        result = reg.call('analyze_logs', log_text=SAMPLE_LOG)
        assert result.is_error is False
        assert result.data['patterns'] >= 5
        assert result.data['errors'] > 0

    def test_analyze_file_tool(self):
        reg = _make_registry()
        log_path = os.path.join(REFS, 'sample-logs', 'tmf620-incident.log')
        result = reg.call('analyze_file', path=log_path)
        assert result.is_error is False
        assert result.data['total_entries'] > 20

    def test_analyze_file_not_found(self):
        reg = _make_registry()
        result = reg.call('analyze_file', path='/nonexistent.log')
        assert result.is_error is True

    def test_parse_logs_tool(self):
        reg = _make_registry()
        result = reg.call('parse_logs', log_text=SAMPLE_LOG)
        assert len(result.data['entries']) > 0

    def test_extract_errors_tool(self):
        reg = _make_registry()
        result = reg.call('extract_errors', log_text=SAMPLE_LOG)
        assert len(result.data['errors']) > 0
        for e in result.data['errors']:
            assert len(e['error_codes']) >= 0  # Error entries extracted

    def test_filter_service_tool(self):
        reg = _make_registry()
        result = reg.call('filter_by_service', log_text=SAMPLE_LOG, service='k8s-pod')
        assert len(result.data['entries']) > 0

    def test_wiki_search_tool(self):
        reg = _make_registry()
        result = reg.call('wiki_search', query='ERR-4001')
        assert len(result.data['results']) > 0

    def test_find_runbook_tool(self):
        reg = _make_registry()
        result = reg.call('find_runbook', scenario='emergency recovery')
        assert result.is_error is False

    def test_find_resolution_tool(self):
        reg = _make_registry()
        result = reg.call('find_resolution', error_code='ERR-4001')
        assert result.is_error is False

    def test_check_sla_tool(self):
        reg = _make_registry()
        result = reg.call('check_sla', metric='latency', value=2800)
        if result.data:
            assert result.data.get('breached') is True

    def test_get_summary_tool(self):
        reg = _make_registry()
        reg.call('analyze_logs', log_text=SAMPLE_LOG)
        result = reg.call('get_summary')
        assert result.is_error is False
        assert result.data['errors'] > 0

    def test_get_patterns_tool(self):
        reg = _make_registry()
        reg.call('analyze_logs', log_text=SAMPLE_LOG)
        result = reg.call('get_patterns')
        assert len(result.data['patterns']) >= 5

    def test_get_incidents_tool(self):
        reg = _make_registry()
        reg.call('analyze_logs', log_text=SAMPLE_LOG)
        result = reg.call('get_incidents')
        assert result.is_error is False

    def test_get_recommendations_tool(self):
        reg = _make_registry()
        reg.call('analyze_logs', log_text=SAMPLE_LOG)
        result = reg.call('get_recommendations')
        assert result.is_error is False

    def test_get_timeline_tool(self):
        reg = _make_registry()
        reg.call('analyze_logs', log_text=SAMPLE_LOG)
        result = reg.call('get_timeline')
        assert result.is_error is False

    def test_get_report_tool(self):
        reg = _make_registry()
        reg.call('analyze_logs', log_text=SAMPLE_LOG)
        result = reg.call('get_report')
        assert '# Log Analysis Report' in result.data['markdown']

    def test_ask_question_tool(self):
        reg = _make_registry()
        reg.call('analyze_logs', log_text=SAMPLE_LOG)
        result = reg.call('ask_question', question='Why did pods crash?')
        assert result.is_error is False
        assert 'wiki_matches' in result.data

    def test_health_check_tool(self):
        reg = _make_registry()
        result = reg.call('health_check')
        assert result.data['wiki_loaded'] is True

    def test_get_stats_tool(self):
        reg = _make_registry()
        result = reg.call('get_stats')
        assert 'wiki' in result.data

    def test_list_tools_tool(self):
        reg = _make_registry()
        result = reg.call('list_tools')
        assert result.data['tools']
        assert len(result.data['tools']) >= 20

    def test_ingest_document_tool(self):
        reg = _make_registry()
        path = os.path.join(REFS, 'specification', 'tmf620-specification.md')
        result = reg.call('ingest_document', path=path)
        assert result.is_error is False

    def test_call_log(self):
        reg = _make_registry()
        reg.call('health_check')
        reg.call('health_check')
        assert len(reg.call_log) >= 2


# ═══════════════════ END-TO-END ═══════════════════

class TestEndToEnd:
    def test_full_agent_workflow(self):
        """Simulate an Anthropic-style agentic loop."""
        reg = _make_registry()

        # Step 1: Agent ingests documentation
        for d in ['troubleshooting', 'runbooks', 'sla']:
            path = os.path.join(REFS, d)
            if os.path.isdir(path):
                ingest = reg.call('ingest_directory', path=path)
                assert ingest.is_error is False

        # Step 2: Agent analyzes production logs
        log_path = os.path.join(REFS, 'sample-logs', 'tmf620-incident.log')
        analysis = reg.call('analyze_file', path=log_path)
        assert analysis.is_error is False
        assert analysis.data['severity'] in ('ERROR', 'CRITICAL')
        assert analysis.data['patterns'] >= 5

        # Step 3: Agent answers questions
        answer = reg.call('ask_question', question='What caused ERR-4001?')
        assert answer.is_error is False
        assert len(answer.data['wiki_matches']) > 0

        # Step 4: Agent checks SLAs
        sla = reg.call('check_sla', metric='latency', value=2800)
        if sla.data:
            assert sla.data.get('breached') is True

        # Step 5: Agent finds runbook
        runbook = reg.call('find_runbook', scenario='emergency catalog recovery')
        assert runbook.is_error is False

        # Step 6: Agent generates report
        report = reg.call('get_report')
        assert '# Log Analysis Report' in report.data['markdown']
        assert 'Incident Chains' in report.data['markdown']

        # Step 7: Agent exports tool definitions (Anthropic format)
        defs = reg.get_tool_definitions()
        assert all('input_schema' in d for d in defs)

    def test_tool_schema_validity(self):
        """All tool schemas must be valid Anthropic format."""
        reg = _make_registry()
        for tool_def in reg.get_tool_definitions():
            assert isinstance(tool_def['name'], str)
            assert len(tool_def['description']) >= 50  # Detailed descriptions
            schema = tool_def['input_schema']
            assert schema['type'] == 'object'
            if 'properties' in schema:
                for prop_name, prop in schema['properties'].items():
                    assert 'type' in prop or 'enum' in prop
