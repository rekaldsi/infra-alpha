# INFRA_ALPHA — Project Summary

**Created:** 2026-04-16  
**Status:** 🟢 ACTIVE  
**Owner:** Jerry C. (7638568632)  
**Group Chat:** Telegram — Infra_Alpha (`-1003951840341`)  
**Bot:** MrMagoochi (@MrMagoochiBot)  

---

## What Is This

Infra_Alpha is the Telegram group where Jerry runs MrMagoochi alongside Frank and potentially other team members. The goal is to have the bot:

1. **Back up all group data** — conversations, decisions, tasks, files
2. **Orchestrate with full stack** — Convex (event log), Grafana (visibility), Serena (code intel), vectorDB (knowledge recall), Notion (tasks/docs), Google Drive (file storage), GitHub (code/backups)
3. **Serve Frank** — Frank can use the bot directly in this group; the bot tracks everything Frank does/asks

---

## Stack Integrations

| Integration | Purpose | Status |
|---|---|---|
| **Convex** | Log all group events, Frank interactions, decisions | ✅ Wired |
| **Grafana** | Visualize group activity, query volume, uptime | ✅ Wired |
| **Serena MCP** | Code intel for any dev tasks raised in group | ✅ Wired |
| **Memory MCP (vectorDB)** | Store Frank's preferences, recurring requests, context | ✅ Wired |
| **GitHub** | Backup configs, decisions, group docs | 🔲 To set up |
| **Notion** | Project tracking, decisions log, knowledge base | 🔲 To wire |
| **Google Drive** | File backups, shared docs from group | 🔲 To wire |
| **Dashboard** | Infra_Alpha page on mrmagoochi-dashboard (port 8082) | 🔲 Building |

---

## Frank Context

- **Name:** Frank
- **Role:** Team member using MrMagoochi in Infra_Alpha group
- **Access level:** Authorized group participant (same group as Jerry)
- **Bot behavior for Frank:** Answer questions, execute tasks, log all interactions to Convex
- **Frank preferences:** To be filled in as interactions accumulate

---

## Key Decisions & Events

| Date | Event |
|---|---|
| 2026-04-16 | Project initialized — Jerry requested full backup + orchestration stack for Infra_Alpha |

---

## Data Backup Strategy

1. **Convex** — every significant message/event/decision logged via convex-bridge.mjs
2. **Memory MCP** — Frank's context stored at `agent-state:frank_*` and `agent-state:infra_alpha_*`
3. **GitHub** — `memory/INFRA_ALPHA/` directory committed to openclaw-core repo
4. **Dashboard** — Live InfraAlpha page at `http://localhost:8082` showing group health

---

## Resume Trigger

Say "Infra_Alpha" or "Frank" in context → read this file first.
