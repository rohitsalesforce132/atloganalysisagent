# Deploying Cortex Analyst as a GitHub Copilot Extension

## Overview

This turns Cortex Analyst into a GitHub Copilot Extension that your team can use inside GitHub Copilot Chat by typing `@cortex-analyst`.

## Architecture

```
┌──────────────────────┐     ┌──────────────────────┐     ┌───────────────────┐
│  GitHub Copilot Chat │────▶│  Extension Server     │────▶│  Python Analysis  │
│  @cortex-analyst     │     │  (Node.js/Express)    │     │  Engine           │
│                      │◀────│  server.js            │◀────│  (src/tools/)     │
└──────────────────────┘     └──────────┬───────────┘     └───────────────────┘
                                      │
                                      ▼
                             ┌──────────────────────┐
                             │  Copilot LLM API     │
                             │  (formats response)  │
                             └──────────────────────┘
```

## Step-by-Step Deployment

### Step 1: Deploy the Extension Server

You need a publicly accessible HTTPS server. Options:

**Option A: Azure Container Apps (recommended for AT&T)**
```bash
# Build and deploy
cd copilot-extension
npm install
az containerapp create \
  --name cortex-analyst \
  --resource-group your-rg \
  --environment your-env \
  --source . \
  --target-port 3000 \
  --ingress external \
  --env-vars PYTHON_ENABLE=1
```

**Option B: Simple VPS/VM**
```bash
# On your server
cd cortex-analyst
npm install
PORT=3000 node server.js
# Use nginx as reverse proxy with SSL
```

### Step 2: Create a GitHub App

1. Go to **GitHub.com → Settings → Developer Settings → GitHub Apps → New GitHub App**
2. Fill in:
   - **GitHub App name:** `Cortex Analyst`
   - **Homepage URL:** `https://your-server.com`
   - **Webhook URL:** `https://your-server.com` (uncheck Active)
   - **Permissions:** 
     - ✅ Copilot Extensions (read/write)
   - **Where can it be installed:** Any account
3. Click **Create GitHub App**
4. Note the **App ID** and generate a **Private Key**

### Step 3: Register as Copilot Extension

1. Go to your GitHub App settings
2. Click **Copilot** in the left sidebar
3. Click **Enable Copilot Extension**
4. Set the extension URL to your server: `https://your-server.com`
5. Choose **Agent** mode (the server handles the LLM formatting)

### Step 4: Install on Your Organization

1. Go to your GitHub App's install page
2. Install it on your organization or repository
3. Every team member can now type `@cortex-analyst` in Copilot Chat

### Step 5: Verify

In any GitHub Copilot Chat:
```
@cortex-analyst analyze the incident log at references/sample-logs/tmf620-incident.log
```

## What Users Can Ask

```
@cortex-analyst analyze this log: <paste logs>
@cortex-analyst find runbook for database failover
@cortex-analyst what's the fix for ERR-4001?
@cortex-analyst check if latency 3200ms breaches SLA
@cortex-analyst search wiki for OOM kill
@cortex-analyst generate incident report
@cortex-analyst show me the timeline
@cortex-analyst what are the recommendations?
@cortex-analyst health check
```

## Adding Your Own Documents

Add your team's documentation to the `references/` folder:
```
references/
├── runbooks/              ← Your runbooks
├── troubleshooting/       ← Your error guides
├── sla/                   ← Your SLA documents
├── specification/         ← Your API specs
└── sample-logs/           ← Test incident logs
```

The wiki auto-ingests everything on startup.

## Security Notes

- The extension receives a GitHub token (`X-GitHub-Token`) for each request
- This token is used to identify the user and call Copilot's LLM API
- The Python analysis engine runs server-side — no data leaves your infrastructure
- Logs are analyzed in-memory, not stored
- For enterprise: deploy behind your corporate firewall
