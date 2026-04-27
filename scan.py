#!/usr/bin/env python3
"""
APILoganalysisExpert — Instant Error Scanner
Paste any error/log text, get instant analysis with wiki-backed resolution.

Usage:
    python3 scan.py "ERR-4001 Invalid product specification"
    python3 scan.py < incident.log
    echo "OOMKilled container exit code 137" | python3 scan.py
"""
import sys, os, json

# Setup paths
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from src.tools import ToolRegistry
from src.wiki_engine import WikiEngine


def scan(text):
    """Scan error/log text and return instant analysis."""
    wiki = WikiEngine()
    agent = ToolRegistry(wiki=wiki)

    # Load all reference docs
    for d in ['troubleshooting', 'runbooks', 'sla', 'specification']:
        path = os.path.join(HERE, 'references', d)
        if os.path.isdir(path):
            agent.call('ingest_directory', path=path)

    # Detect if it's a full log or a short error
    lines = [l for l in text.strip().split('\n') if l.strip()]
    has_timestamps = any(l.startswith('20') for l in lines[:3])

    results = {
        'input': text[:200],
        'input_lines': len(lines),
        'mode': 'log_analysis' if has_timestamps else 'error_lookup',
    }

    if has_timestamps and len(lines) >= 3:
        # Full log analysis
        analysis = agent.call('analyze_logs', log_text=text)
        results['analysis'] = {
            'severity': analysis.data.get('severity'),
            'total_entries': analysis.data.get('total_entries'),
            'errors': analysis.data.get('errors'),
            'patterns': analysis.data.get('patterns'),
            'incidents': analysis.data.get('incidents'),
            'confidence': analysis.data.get('confidence'),
        }
        # Get details
        patterns = agent.call('get_patterns')
        incidents = agent.call('get_incidents')
        recs = agent.call('get_recommendations')
        results['patterns'] = patterns.data.get('patterns', [])
        results['incidents'] = incidents.data.get('incidents', [])
        results['recommendations'] = recs.data.get('recommendations', [])
    else:
        # Quick error lookup — search wiki
        error_codes = []
        import re
        for code in re.findall(r'ERR-\d{4}', text, re.I):
            error_codes.append(code.upper())

        results['error_codes'] = error_codes

        # Search wiki
        search = agent.call('wiki_search', query=text)
        results['wiki_matches'] = search.data.get('results', [])

        # Find resolution for each error code
        results['resolutions'] = []
        for code in error_codes:
            res = agent.call('find_resolution', error_code=code)
            results['resolutions'].extend(res.data.get('pages', []))

        # Find runbooks
        runbook = agent.call('find_runbook', scenario=text)
        results['runbooks'] = runbook.data.get('runbooks', [])

        # Check SLA if metric mentioned
        latency_match = re.search(r'(\d+)\s*ms', text)
        if latency_match:
            sla = agent.call('check_sla', metric='latency', value=int(latency_match.group(1)))
            if sla.data:
                results['sla_check'] = sla.data

    return results


def format_output(results):
    """Format results as readable output."""
    lines = []
    mode = results.get('mode', 'error_lookup')

    if mode == 'log_analysis':
        a = results.get('analysis', {})
        lines.append(f"🧠 APILOGANALYSISEXPERT — Log Analysis")
        lines.append(f"{'='*50}")
        lines.append(f"Severity: {a.get('severity', 'UNKNOWN')}")
        lines.append(f"Entries: {a.get('total_entries', 0)} | Errors: {a.get('errors', 0)}")
        lines.append(f"Patterns: {a.get('patterns', 0)} | Incidents: {a.get('incidents', 0)}")
        lines.append(f"Confidence: {a.get('confidence', 0):.0%}")
        lines.append("")

        patterns = results.get('patterns', [])
        if patterns:
            lines.append(f"🔎 PATTERNS ({len(patterns)}):")
            for p in patterns:
                lines.append(f"  • {p['name']} [{p['type']}] in {p['service']}")
            lines.append("")

        recs = results.get('recommendations', [])
        if recs:
            lines.append(f"💡 RECOMMENDATIONS ({len(recs)}):")
            for r in recs[:5]:
                lines.append(f"  [{r['priority']}] {r['title']}")
                if r.get('action'):
                    lines.append(f"     → {r['action'][:120]}")
            lines.append("")

        incidents = results.get('incidents', [])
        for inc in incidents:
            lines.append(f"🔗 {inc['chain_id']} [{inc['severity']}]")
            lines.append(f"  Blast: {', '.join(inc['blast_radius'])}")
            for c in inc.get('correlations', []):
                lines.append(f"  ├─ {c['pattern_name']} ({c['pattern_type']}) [{c['confidence']:.0%}]")
                if c.get('root_cause') and 'not explicitly' not in c.get('root_cause', ''):
                    lines.append(f"  │  Root: {c['root_cause'][:120]}")
                if c.get('resolution_steps'):
                    lines.append(f"  │  Steps: {len(c['resolution_steps'])} found")
                if c.get('sla_breach'):
                    sb = c['sla_breach']
                    lines.append(f"  │  ⚠️ SLA: {sb['metric']}={sb['value']} > {sb['threshold']}")
    else:
        lines.append(f"🧠 APILOGANALYSISEXPERT — Error Lookup")
        lines.append(f"{'='*50}")

        if results.get('error_codes'):
            lines.append(f"Error codes: {', '.join(results['error_codes'])}")
        lines.append("")

        resolutions = results.get('resolutions', [])
        if resolutions:
            lines.append(f"📋 RESOLUTION DOCS ({len(resolutions)}):")
            for r in resolutions:
                lines.append(f"  • {r['title']} [{r['type']}] → {r['source']}")
            lines.append("")

        wiki = results.get('wiki_matches', [])
        if wiki:
            lines.append(f"📚 WIKI MATCHES ({len(wiki)}):")
            for w in wiki:
                lines.append(f"  • {w['title']} [{w['type']}] (score: {w['score']})")
            lines.append("")

        runbooks = results.get('runbooks', [])
        if runbooks:
            lines.append(f"📖 RUNBOOKS ({len(runbooks)}):")
            for rb in runbooks:
                lines.append(f"  • {rb['title']} → {rb['source']}")
            lines.append("")

        sla = results.get('sla_check')
        if sla:
            status = '⚠️ BREACHED' if sla.get('breached') else '✅ OK'
            lines.append(f"📏 SLA: {sla['metric']}={sla['value']} (threshold: {sla['threshold']}) {status}")

        if not wiki and not resolutions and not runbooks:
            lines.append("No matching documentation found. Add more docs to references/")

    return '\n'.join(lines)


if __name__ == '__main__':
    # Get input from argument or stdin
    if len(sys.argv) > 1:
        text = ' '.join(sys.argv[1:])
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("Usage: python3 scan.py \"ERR-4001 Invalid specification\"")
        print("       cat incident.log | python3 scan.py")
        print("       python3 scan.py < incident.log")
        sys.exit(1)

    results = scan(text)

    # Output as JSON if --json flag
    if '--json' in sys.argv:
        print(json.dumps(results, indent=2))
    else:
        print(format_output(results))
