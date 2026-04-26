/**
 * Cortex Analyst — GitHub Copilot Extension
 *
 * A wiki-aware log analysis agent that runs as a GitHub Copilot Extension.
 * Users ask @cortex-analyst to analyze logs, check SLAs, find runbooks,
 * and get incident reports — all within GitHub Copilot Chat.
 *
 * Architecture:
 *   GitHub Copilot Chat → this server → Python analysis engine → Copilot LLM → response
 *
 * Setup:
 *   1. npm install
 *   2. python3 -c "from src.tools import ToolRegistry; print('OK')"  # verify Python engine
 *   3. npm start
 *   4. Register as GitHub App with Copilot extension (see DEPLOY.md)
 */

import { Octokit } from "@octokit/core";
import express from "express";
import { Readable } from "node:stream";
import { execSync } from "child_process";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, "..");

const app = express();

// ─── Python Engine Bridge ───────────────────────────────────

/**
 * Call a Cortex Analyst tool via Python.
 * Returns parsed JSON result.
 */
function callTool(toolName, params = {}) {
  const paramsJson = JSON.stringify(params).replace(/'/g, "'\\''");
  const pythonCode = `
import sys, os, json
sys.path.insert(0, os.path.expanduser("${PROJECT_ROOT}"))
os.chdir(os.path.expanduser("${PROJECT_ROOT}"))
from src.tools import ToolRegistry
from src.wiki_engine import WikiEngine

wiki = WikiEngine()
agent = ToolRegistry(wiki=wiki)

# Load reference docs
for d in ["troubleshooting", "runbooks", "sla", "specification"]:
    p = os.path.join("references", d)
    if os.path.isdir(p):
        agent.call("ingest_directory", path=p)

result = agent.call("${toolName}", **json.loads('${paramsJson}'))
print(json.dumps({"output": result.output, "is_error": result.is_error, "data": result.data}))
`;
  try {
    const output = execSync(`python3 -c '${pythonCode}'`, {
      timeout: 30000,
      maxBuffer: 5 * 1024 * 1024,
      cwd: PROJECT_ROOT,
    }).toString().trim();
    return JSON.parse(output);
  } catch (err) {
    return { output: `Error: ${err.message}`, is_error: true, data: {} };
  }
}

/**
 * Determine which tool to call based on user message.
 * This is a simple intent classifier — in production, the LLM handles this.
 */
function classifyIntent(message) {
  const lower = message.toLowerCase();

  // Analysis requests
  if (lower.includes("analyze") && (lower.includes("file") || lower.includes("log"))) {
    const pathMatch = lower.match(/(?:file|log|path)[:\s]+([^\s,.]+)/);
    return { tool: "analyze_file", params: { path: pathMatch ? pathMatch[1] : "" } };
  }
  if (lower.includes("analyze") || lower.includes("deep dive") || lower.includes("incident")) {
    return { tool: "analyze_pending", hint: "needs_log_text" };
  }

  // Extract errors
  if (lower.includes("error") && (lower.includes("extract") || lower.includes("show") || lower.includes("what"))) {
    return { tool: "extract_errors", hint: "needs_log_text" };
  }

  // Knowledge queries
  if (lower.includes("runbook")) {
    const scenario = message.replace(/.*runbook[s]?\s*(?:for|about|on)?\s*/i, "").trim();
    return { tool: "find_runbook", params: { scenario: scenario || "emergency recovery" } };
  }
  if (lower.includes("resolution") || lower.includes("fix") || lower.includes("how to fix")) {
    const codeMatch = message.match(/ERR-\d{4}/i);
    if (codeMatch) return { tool: "find_resolution", params: { error_code: codeMatch[0].toUpperCase() } };
    return { tool: "find_resolution", params: { error_code: "" } };
  }
  if (lower.includes("sla") || lower.includes("threshold") || lower.includes("breach")) {
    const numMatch = message.match(/(\d+)\s*ms/);
    return { tool: "check_sla", params: { metric: "latency", value: numMatch ? parseInt(numMatch[1]) : 0 } };
  }
  if (lower.includes("search") || lower.includes("wiki") || lower.includes("document")) {
    const query = message.replace(/.*(?:search|wiki|document|find)\s*(?:for|about|on)?\s*/i, "").trim();
    return { tool: "wiki_search", params: { query: query || "troubleshooting" } };
  }

  // Report requests
  if (lower.includes("report") || lower.includes("summary")) return { tool: "get_report", params: {} };
  if (lower.includes("pattern")) return { tool: "get_patterns", params: {} };
  if (lower.includes("incident") || lower.includes("chain")) return { tool: "get_incidents", params: {} };
  if (lower.includes("recommend")) return { tool: "get_recommendations", params: {} };
  if (lower.includes("timeline")) return { tool: "get_timeline", params: {} };

  // Utils
  if (lower.includes("health") || lower.includes("status")) return { tool: "health_check", params: {} };
  if (lower.includes("stat")) return { tool: "get_stats", params: {} };
  if (lower.includes("tool") || lower.includes("help")) return { tool: "list_tools", params: {} };

  return { tool: "get_report", params: {} };
}

// ─── Routes ─────────────────────────────────────────────────

app.get("/", (req, res) => {
  res.json({
    name: "Cortex Analyst",
    description: "Wiki-aware log analysis agent for GitHub Copilot",
    tools: 21,
    status: "running",
  });
});

app.post("/", express.json(), async (req, res) => {
  const tokenForUser = req.get("X-GitHub-Token");
  const octokit = new Octokit({ auth: tokenForUser });
  const user = await octokit.request("GET /user");

  const payload = req.body;
  const userMessage = payload.messages[payload.messages.length - 1]?.content || "";

  console.log(`[${new Date().toISOString()}] @${user.data.login}: ${userMessage}`);

  // Call Python analysis engine
  const intent = classifyIntent(userMessage);
  let toolResult;

  if (intent.hint === "needs_log_text") {
    // Extract any log text from the message
    const logLines = userMessage.split("\n").filter(l =>
      /^\d{4}-\d{2}-\d{2}T/.test(l.trim()) ||
      /ERROR|WARN|INFO|CRITICAL/.test(l)
    );
    if (logLines.length > 0) {
      toolResult = callTool("analyze_logs", { log_text: logLines.join("\n") });
    } else {
      toolResult = callTool(intent.tool, intent.params);
    }
  } else {
    toolResult = callTool(intent.tool, intent.params);
  }

  // Build enriched messages for Copilot LLM
  const messages = payload.messages;
  messages.unshift({
    role: "system",
    content: `You are Cortex Analyst, a wiki-aware log analysis agent. You help engineers analyze production logs, find root causes, check SLAs, and generate incident reports.

You have access to a Python analysis engine that has already processed the user's request. Here is the tool result:

**Tool Called:** ${intent.tool}
**Result:** ${toolResult.is_error ? "ERROR" : "SUCCESS"}
**Output:** ${toolResult.output}
**Data:** ${JSON.stringify(toolResult.data, null, 2).substring(0, 3000)}

Based on this tool result, provide a clear, actionable response to @${user.data.login}.
- If patterns were detected, explain them in plain language
- If root causes were found, list them with resolution steps
- If SLA breaches detected, highlight them
- If recommendations exist, prioritize them
- Always cite the wiki sources used

Keep the response concise and action-oriented. Use bullet points and tables when appropriate.`
  });

  // Call Copilot's LLM to format the response
  try {
    const copilotLLMResponse = await fetch(
      "https://api.githubcopilot.com/chat/completions",
      {
        method: "POST",
        headers: {
          authorization: `Bearer ${tokenForUser}`,
          "content-type": "application/json",
        },
        body: JSON.stringify({ messages, stream: true }),
      }
    );
    Readable.from(copilotLLMResponse.body).pipe(res);
  } catch (err) {
    // Fallback: return raw tool result if Copilot LLM fails
    res.type("text/plain");
    res.send(`🧠 **Cortex Analyst** (${intent.tool})\n\n${toolResult.output}\n\n${JSON.stringify(toolResult.data, null, 2)}`);
  }
});

const port = Number(process.env.PORT || "3000");
app.listen(port, () => {
  console.log(`🧠 Cortex Analyst Copilot Extension running on port ${port}`);
  console.log(`   Python engine: ${PROJECT_ROOT}`);
  console.log(`   Available at: http://localhost:${port}`);
});
