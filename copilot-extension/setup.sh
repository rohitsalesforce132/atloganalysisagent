#!/bin/bash
# Deploy Cortex Analyst as a GitHub Copilot Extension
# Run this script to set up everything needed

set -e

echo "🧠 Cortex Analyst — GitHub Copilot Extension Setup"
echo "=================================================="
echo ""

# Check prerequisites
echo "🔍 Checking prerequisites..."

if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Install from https://nodejs.org"
    exit 1
fi
echo "  ✅ Node.js $(node --version)"

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    exit 1
fi
echo "  ✅ Python $(python3 --version)"

# Install dependencies
echo ""
echo "📦 Installing Node.js dependencies..."
cd "$(dirname "$0")"
npm install

# Verify Python engine
echo ""
echo "🐍 Verifying Python analysis engine..."
cd ..
if python3 -c "from src.tools import ToolRegistry; print('OK')" 2>/dev/null; then
    echo "  ✅ Python engine working"
else
    echo "  ❌ Python engine failed. Check src/tools/"
    exit 1
fi

# Verify reference docs
echo ""
echo "📚 Checking reference documents..."
DOCS=0
for d in references/troubleshooting references/runbooks references/sla references/specification; do
    if [ -d "$d" ]; then
        COUNT=$(ls -1 "$d"/*.md 2>/dev/null | wc -l)
        echo "  • $d: $COUNT documents"
        DOCS=$((DOCS + COUNT))
    fi
done
echo "  Total: $DOCS documents loaded"

echo ""
echo "=================================================="
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo ""
echo "1. Start the server locally:"
echo "   cd copilot-extension && npm start"
echo ""
echo "2. Create a GitHub App:"
echo "   → Go to https://github.com/settings/developers"
echo "   → Click 'New GitHub App'"
echo "   → Name: Cortex Analyst"
echo "   → Webhook URL: https://YOUR-SERVER.COM"
echo "   → Permissions: Copilot (read/write)"
echo ""
echo "3. Enable Copilot Extension:"
echo "   → In your GitHub App settings → Copilot → Enable"
echo ""
echo "4. Install on your org:"
echo "   → Install the GitHub App on your organization"
echo ""
echo "5. Use it:"
echo "   → @cortex-analyst analyze this log: <paste logs>"
echo "   → @cortex-analyst what's the fix for ERR-4001?"
echo "   → @cortex-analyst check SLA for latency 3200ms"
echo ""
echo "Deploy options:"
echo "  • Heroku: git subtree push --prefix copilot-extension heroku main"
echo "  • Azure:  az containerapp create --source copilot-extension/"
echo "  • Railway: railway up from copilot-extension/"
echo "  • VPS:    scp -r copilot-extension/ server:/opt/cortex-analyst/"
