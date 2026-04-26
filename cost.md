# Cost Optimization — How Knowledge Graphs Reduce Token Usage

## The Problem Without Graphs

```
User asks: "Why did the pods crash?"

Without graph — you send EVERYTHING to the LLM:
┌─────────────────────────────────────────────────────┐
│ System prompt                                    2K  │
│ Full troubleshooting doc (50 pages)             25K  │
│ Full runbook (30 pages)                         15K  │
│ Full SLA doc (10 pages)                          5K  │
│ Full API specification (40 pages)              20K  │
│ Chat history                                     2K  │
│                                                  ──  │
│ Total:                                         69K  │  ← Most is irrelevant
└─────────────────────────────────────────────────────┘
```

**69K tokens burned. 90% of it irrelevant to "why did pods crash."**

---

## With Knowledge Graph — Token-Optimized Retrieval

```
User asks: "Why did pods crash?"

Step 1: TOKENIZED SEARCH (cheap, no LLM)
  "pods crash" → match against wiki page word sets
  Returns seed pages: ["kubernetes-pod", "oom-kill"]
  Cost: 0 LLM tokens (pure Python computation)

Step 2: GRAPH EXPANSION (4-Signal model)
  kubernetes-pod → neighbors: [oom-kill, crash-recovery, resource-limits]
                  → 2 hops: [postgresql-failover, latency-spike]
  Cost: 0 LLM tokens (graph traversal in memory)

Step 3: BUDGET-CONTROLLED ASSEMBLY
  Context window: 128K tokens, allocated:
  ┌─────────────────────────────────────────────────────┐
  │ System prompt (15%)                   19.2K tokens  │
  │ Wiki pages (60%)                      76.8K tokens  │
  │   - oom-kill.md          (3K tokens)                │
  │   - crash-recovery.md    (5K tokens)                │
  │   - resource-limits.md   (2K tokens)                │
  │   - runbook-emergency.md (4K tokens)                │
  │   Total: 14K tokens (not 69K!)                      │
  │ Chat history (20%)                    25.6K tokens  │
  │ Index (5%)                             6.4K tokens  │
  │                                                  ──  │
  │ Total used: ~52K (saved 17K tokens)                 │
  └─────────────────────────────────────────────────────┘
```

**Key savings: Only 14K tokens of wiki content instead of 65K.**

---

## The 4 Signals That Replace Semantic Search

Most systems use vector embeddings for retrieval (expensive — needs an embedding model call for every query). The graph uses **4 deterministic signals** that cost **zero tokens**:

### Signal 1: Direct Link (×3.0 weight)
- Page A has `[[Page B]]` wikilink → they're related
- **Cost:** 0 tokens (just checking a list)

### Signal 2: Source Overlap (×4.0 weight — strongest)
- Page A and Page B both reference `runbook-rb001.md`
- They share provenance, likely related
- **Cost:** 0 tokens (set intersection on source lists)

### Signal 3: Adamic-Adar (×1.5 weight)
- Page A and Page B share neighbors, but neighbors with FEW connections count MORE
- This is a niche expertise signal
- `neighbor_degree = 3 → 1/log(3) = 0.91` (high signal)
- `neighbor_degree = 100 → 1/log(100) = 0.22` (low signal)
- **Cost:** 0 tokens (math on pre-built adjacency list)

### Signal 4: Type Affinity (×1.0 weight)
- Both pages are "troubleshooting" type → bonus
- **Cost:** 0 tokens (string comparison)

**Total token cost for relevance scoring: ZERO.** All done in Python with sets and dicts.

---

## Visual: Graph vs No-Graph Token Usage

```
TOKEN CONSUMPTION COMPARISON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

No Graph (brute force):
██████████████████████████████████████████ 69K tokens
↑ 90% irrelevant content sent to LLM

Vector Search (embedding-based):
████████████████████ 22K tokens
↑ Still needs embedding API calls ($0.02/query)

Knowledge Graph (4-Signal):
████████████ 14K tokens  ← 80% fewer tokens
↑ Zero API calls, pure computation

Token savings: 69K → 14K = 80% reduction
Cost savings: ~$0.15/query → ~$0.03/query (at GPT-4 pricing)
```

---

## Budget-Controlled Assembly (Proportional Allocation)

The query engine allocates the context window proportionally:

```
128K context window
├── 60% → Wiki pages (76.8K cap)
│   Sorted by graph score, packed until budget full
│   Pages that don't fit are dropped (lower score)
│
├── 20% → Chat history (25.6K cap)
│   Recent conversation turns
│
├── 15% → System prompt (19.2K cap)
│   Agent personality + rules
│
└── 5% → Index/citations (6.4K cap)
    Citation numbers for LLM to reference
```

### Auto-Concise When Budget Is Tight (>70% used)

- Wiki page budget drops from 76.8K → 38.4K
- Only top-scoring pages survive
- Old conversation turns get summarized
- Net effect: 40-60% token reduction

---

## Real-World Cost Impact

### Scenario: 1000 queries/day against 100-document knowledge base

| Method | Tokens/Query | Daily Tokens | Daily Cost (GPT-4) | Monthly Cost |
|--------|-------------|-------------|-------------------|-------------|
| Brute force (all docs) | 69K | 69M | $207 | **$6,210** |
| Vector search | 22K | 22M | $66 | **$1,980** |
| **Knowledge graph (4-Signal)** | **14K** | **14M** | **$42** | **$1,260** |
| Graph + auto-concise | 8K | 8M | $24 | **$720** |

**Savings: $6,210 → $720/month = $5,490/month saved (88% reduction)**

---

## Interview Answer

> **Q: "How do you optimize token usage in RAG systems?"**
>
> I use a knowledge graph with 4 deterministic signals — direct links (×3.0), source overlap (×4.0), Adamic-Adar shared neighbors (×1.5), and type affinity (×1.0). Each signal is computed in-memory with zero LLM token cost. The graph pre-filters the document set from potentially thousands of pages down to the 5-10 most relevant, then a budget controller allocates the context window proportionally — 60% wiki, 20% history, 15% system prompt, 5% index. This cuts token consumption by 80% compared to brute-force document injection and avoids the per-query cost of embedding-based retrieval. At scale, this saves ~$5,500/month on a 1000 queries/day workload.

---

## Why Source Overlap Is the Strongest Signal (×4.0)

Two pages derived from the same raw document share implicit relationships that even wikilinks miss. If Page A and Page B both list `tmf620-troubleshooting.md` in their sources field, they're talking about the same domain — even if they don't explicitly link to each other. This catches relationships that human editors forget to wikilink.

## Why Adamic-Adar Beats Jaccard

Jaccard similarity treats all shared neighbors equally. Adamic-Adar weights by inverse log-degree — a shared neighbor that connects to only 3 pages is a **stronger specificity signal** than one connecting to 100 pages. In knowledge graphs, hub nodes (like "Python") connect to everything and tell you nothing specific. Niche nodes (like "OOM kill in Kubernetes 1.28") are high-value signals.
