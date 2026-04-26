/**
 * Cortex Analyst — GitHub Copilot Extension
 *
 * This is the server that GitHub Copilot calls when a user types @cortex-analyst.
 * It receives the user's message, runs the Python analysis engine, then
 * streams the result back through Copilot's LLM for formatting.
 *
 * Based on the official GitHub Copilot Extension pattern:
 * https://github.com/copilot-extensions/blackbeard-extension
 *
 * Flow:
 *   1. GitHub Copilot Chat sends POST to this server
 *   2. Server extracts user message and calls Python scan.py
 *   3. Python engine analyzes logs/errors against wiki docs
 *   4. Analysis result injected as system message
 *   5. Copilot LLM formats the response naturally
 *   6. Streamed back to user in Copilot Chat
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
app.use(express.json());

// Health check
app.get("/", (req, res) => {
  res.json({
    name: "Cortex Analyst",
    description: "Wiki-aware log analysis agent for GitHub Copilot",
    tools: 21,
    status: "running",
    engine: PROJECT_ROOT,
  });
});

// Copilot extension endpoint
app.post("/", async (req, res) => {
  try {
    // 1. Get user identity
    const tokenForUser = req.get("X-GitHub-Token");
    const octokit = new Octokit({ auth: tokenForUser });
    const user = await octokit.request("GET /user");
    const username = user.data.login;

    // 2. Extract user message
    const payload = req.body;
    const messages = payload.messages;
    const userMessage = messages[messages.length - 1]?.content || "";

    console.log(`[${new Date().toISOString()}] @${username}: ${userMessage.substring(0, 200)}`);

    // 3. Run Python analysis engine
    const analysisResult = runAnalysis(userMessage);

    // 4. Build enriched messages for Copilot LLM
    messages.unshift({
      role: "system",
      content: buildSystemPrompt(username, analysisResult),
    });

    // 5. Call Copilot LLM to format the response
    const copilotResponse = await fetch(
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

    // 6. Stream response back to user
    Readable.from(copilotResponse.body).pipe(res);
  } catch (err) {
    console.error("Error:", err.message);
    res.type("text/plain").status(500).send(
      `🧠 Cortex Analyst encountered an error: ${err.message}\n\n` +
      `Make sure Python 3 is installed and the analysis engine is accessible.`
    );
  }
});

/**
 * Run the Python analysis engine on the user's message.
 */
function runAnalysis(userMessage) {
  const escapedMessage = userMessage.replace(/'/g, "'\\''").replace(/\n/g, "\\n");
  const pythonScript = `
import sys, os, json
sys.path.insert(0, "${PROJECT_ROOT}")
os.chdir("${PROJECT_ROOT}")
from scan import scan
result = scan("${escapedMessage}")
print(json.dumps(result))
`;

  try {
    const output = execSync(`python3 -c '${pythonScript}'`, {
      timeout: 30000,
      maxBuffer: 5 * 1024 * 1024,
      cwd: PROJECT_ROOT,
    }).toString().trim();

    return JSON.parse(output);
  } catch (err) {
    return {
      mode: "error",
      error: err.message,
      wiki_matches: [],
      resolutions: [],
    };
  }
}

/**
 * Build system prompt with analysis context.
 */
function buildSystemPrompt(username, result) {
  if (result.error) {
    return `You are Cortex Analyst, a log analysis agent. Tell @${username} that an error occurred: ${result.error}. Suggest they check that Python 3 and the cortex-analyst repo are properly set up.`;
  }

  let context = `You are Cortex Analyst, a wiki-aware production log analysis agent. You help @${username} analyze errors, find root causes, check SLAs, and get resolution steps.

## Analysis Result
**Mode:** ${result.mode}
**Input:** ${result.input || "N/A"}
`;

  if (result.mode === "log_analysis" && result.analysis) {
    const a = result.analysis;
    context += `
**Severity:** ${a.severity || "UNKNOWN"}
**Total entries:** ${a.total_entries || 0}
**Errors:** ${a.errors || 0}
**Patterns detected:** ${a.patterns || 0}
**Incident chains:** ${a.incidents || 0}
**Confidence:** ${Math.round((a.confidence || 0) * 100)}%
`;

    if (result.patterns?.length > 0) {
      context += `\n**Patterns:**\n`;
      for (const p of result.patterns.slice(0, 10)) {
        context += `- ${p.name} [${p.type}] in ${p.service} (${p.entries} hits)\n`;
      }
    }

    if (result.incidents?.length > 0) {
      for (const inc of result.incidents) {
        context += `\n**Incident ${inc.chain_id} [${inc.severity}]**\n`;
        context += `Blast radius: ${inc.blast_radius?.join(", ")}\n`;
        for (const c of inc.correlations?.slice(0, 5) || []) {
          context += `- ${c.pattern_name} (${c.pattern_type}) confidence=${Math.round(c.confidence * 100)}%\n`;
          if (c.root_cause && !c.root_cause.includes("not explicitly")) {
            context += `  Root cause: ${c.root_cause.substring(0, 150)}\n`;
          }
          if (c.resolution_steps?.length > 0) {
            context += `  Resolution: ${c.resolution_steps.length} steps available\n`;
          }
          if (c.sla_breach) {
            context += `  ⚠️ SLA BREACH: ${c.sla_breach.metric}=${c.sla_breach.value} > ${c.sla_breach.threshold}\n`;
          }
        }
      }
    }

    if (result.recommendations?.length > 0) {
      context += `\n**Recommendations:**\n`;
      for (const r of result.recommendations.slice(0, 5)) {
        context += `- [${r.priority}] ${r.title}\n`;
        if (r.action) context += `  → ${r.action.substring(0, 120)}\n`;
      }
    }
  } else {
    // Error lookup mode
    if (result.error_codes?.length > 0) {
      context += `\n**Error codes found:** ${result.error_codes.join(", ")}\n`;
    }
    if (result.resolutions?.length > 0) {
      context += `\n**Resolution docs:**\n`;
      for (const r of result.resolutions) {
        context += `- ${r.title} [${r.type}]\n`;
      }
    }
    if (result.wiki_matches?.length > 0) {
      context += `\n**Wiki matches:**\n`;
      for (const w of result.wiki_matches) {
        context += `- ${w.title} [${w.type}] (relevance: ${w.score})\n`;
      }
    }
    if (result.runbooks?.length > 0) {
      context += `\n**Runbooks:**\n`;
      for (const rb of result.runbooks) {
        context += `- ${rb.title}\n`;
      }
    }
    if (result.sla_check) {
      const s = result.sla_check;
      context += `\n**SLA Check:** ${s.metric}=${s.value} (threshold: ${s.threshold}) ${s.breached ? "⚠️ BREACHED" : "✅ OK"}\n`;
    }
  }

  context += `
## Instructions
Based on the analysis above, provide a clear, concise response to @${username}:
- Explain what happened in plain language
- List root causes with specific resolution steps
- Highlight any SLA breaches
- Prioritize recommendations
- Cite wiki sources where applicable
- Keep it action-oriented and brief`;

  return context;
}

const port = Number(process.env.PORT || "3000");
app.listen(port, () => {
  console.log(`🧠 Cortex Analyst Copilot Extension running on port ${port}`);
  console.log(`   Repo: ${PROJECT_ROOT}`);
  console.log(`   Endpoint: http://localhost:${port}`);
});
