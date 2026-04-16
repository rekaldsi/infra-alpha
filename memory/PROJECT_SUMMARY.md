# INFRA_ALPHA — Project Summary

**Created:** 2026-04-16  
**Status:** 🟢 ACTIVE  
**Owner:** Jerry C. (7638568632)  
**Group Chat:** Telegram — Infra_Alpha (`-1003951840341`)  
**Bot:** MrMagoochi (@MrMagoochiBot)  

---

## What Is This

Infra_Alpha is the Telegram group where Jerry runs MrMagoochi alongside Frank. The bot serves two distinct roles:

1. **For Jerry** — Full orchestration: infra, deploys, agents, memory, all of it
2. **For Frank** — Investment partner: market research, portfolio tracking, trade insights, sector recon, watchlist alerts. **No infra access.**

---

## Frank's Role (set by Jerry 2026-04-16)

- **Location:** Remote — different location from Jerry. No access to Mac mini, local network, or localhost services
- **Access:** NONE — no Railway, Vercel, Mac mini, localhost:8082, or any local infra
- **Delivery:** Telegram only — all research, alerts, and insights go directly in chat
- **Scope:** Researcher · Advisor · Investing Partner
- **What Gooch does for Frank:**
  - Portfolio tracking + P&L (delivered in chat)
  - Watchlist monitoring + price alerts (IONQ, AMD, UEC, BNS + more)
  - Market research + sector recon
  - Trade insights + gap analysis
  - News + catalyst monitoring
  - Investment thesis validation
- **What Gooch does NOT do for Frank:** share localhost links, deploy apps, manage infrastructure, or touch Jerry's systems

---

## Stack Integrations

| Integration | Purpose | Status |
|---|---|---|
| **Convex** | Log all group events, Frank interactions, decisions | ✅ Live |
| **Grafana** | Visualize group activity, query volume, uptime | ✅ Live |
| **Serena MCP** | Code intel (Jerry use only) | ✅ Live |
| **Memory MCP (vectorDB)** | Frank's portfolio, preferences, investment context | ✅ Live |
| **GitHub (rekaldsi/infra-alpha)** | Backup memory + dashboard source | ✅ Live |
| **Dashboard (port 8082)** | Infra_Alpha page — watchlist + portfolio live | ✅ Live |

---

## Frank's Investment Data

- **Master Watchlist (29 tickers):** VRT, ABB, ETN, SBGSF, TT, SNDK, JLL, CBRE, CWK, DLR, MOD, CARR, SIE, FIX, FTV, APG, JCI, HON, MSA, CMI, GNRC, CAT, ATLKY, GEV, IONQ, AMD, UEC, BNS
- **Thesis:** Picks-and-shovels data center infrastructure + Frank's 4 additions (IONQ, AMD, UEC, BNS)
- **Advisor mode:** PROACTIVE — daily 9 AM CST intel brief, unprompted alerts on ±5% moves, earnings, upgrades, catalysts
- **Portfolio:** Pending — Frank to provide positions
- **Memory keys:** `agent-state:infra_alpha_watchlist`, `agent-state:frank_role`, `agent-state:frank_advisor_mode`

---

## Key Decisions & Events

| Date | Event |
|---|---|
| 2026-04-16 | Project initialized — Jerry requested full backup + orchestration stack |
| 2026-04-16 | Frank's role clarified by Jerry — investment partner only, no infra access |
| 2026-04-16 | Frank added watchlist: IONQ, AMD, UEC, BNS |
| 2026-04-16 | Frank requested portfolio tracker — awaiting positions |

---

## Data Backup Strategy

1. **Convex** — every significant event logged
2. **Memory MCP** — Frank's context at `agent-state:frank_*` and `agent-state:infra_alpha_*`
3. **GitHub** — `rekaldsi/infra-alpha`, nightly cron at 2 AM CST
4. **Dashboard** — `http://localhost:8082/infra-alpha`

---

## Resume Trigger

Mention "Infra_Alpha", "Frank", or "watchlist" → read this file first.
