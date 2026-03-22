# PRD — Infra Alpha: Infrastructure Investment Intelligence
**Status:** GSD v1 — approved for build  
**Created:** 2026-03-22  
**Owner:** Jerry C. / Frank (end user)  
**Model budget:** Local-first. Gemini Flash for research. Sonnet only for arch decisions.

---

## Phase 1: Intake

**What we're building:**  
Infra Alpha is a personal investment intelligence platform for Frank — a data center Senior Chief Engineer who physically works on the hardware (UPS systems, breakers, PLCs, generators) that powers the world's AI infrastructure. His field observations (what equipment he's replacing, how often, how critical) are signals that public investors can't see. This tool turns those observations into investment intelligence on the companies that make that equipment.

**The core insight:**  
Frank replaces an Eaton UPS → Eaton (ETN) is getting paid. Frank sees a facility swap from Liebert (Vertiv) to APC (Schneider) → that's a brand-loyalty signal. He's an accidental expert witness to billions in infrastructure spending.

**End Users:** Frank (primary), Jerry (owner/admin)

**Success Criteria:**
- [ ] Deployed app accessible at a real URL (Vercel static or Railway)
- [ ] Real stock prices loading (not simulated) via our backend proxy
- [ ] AI Intelligence tab working via our backend proxy (no client-side API key needed)
- [ ] Field observations persist (initially localStorage, later Supabase)
- [ ] GitHub repo created under rekaldsi
- [ ] Logged to Convex
- [ ] Mobile-usable (Frank is in the field)

**Constraints:**
- Local models first (Ollama/LM Studio) for the AI chat — Frank doesn't need Claude-level reasoning for most queries
- Anthropic Sonnet only as fallback if local model fails or for complex analysis
- No new Supabase project for MVP — localStorage is fine for v1, Supabase in v2
- Railway backend preferred (we already have Railway) for the price proxy + AI proxy
- Budget: $0 incremental API cost target for MVP

---

## Phase 2: PRD

### Problem
The original HTML prototype is excellent conceptually but has 4 critical gaps:

1. **corsproxy.io dependency** — public free proxy for Yahoo Finance, unreliable, frequently rate-limited. Price data falls back to fake randomized numbers constantly.
2. **Client-side Anthropic API key** — stored in localStorage, Frank has to get his own key, calls go directly from browser. Fragile, exposes key, costs Frank money.
3. **No cross-device persistence** — localStorage only. Frank logs an observation on mobile, opens desktop, it's gone.
4. **ENS (EnerSys) missing** — referenced in BRAND_MAP but not in BASE_COMPANIES. Battery backup is a major infrastructure category.

### Goals
**In scope (MVP):**
- Backend proxy for Yahoo Finance prices (Railway Express server)
- Backend proxy for AI chat (routes to local Ollama/LM Studio first, Anthropic Sonnet as fallback)
- Add ENS + 2-3 missing companies to BASE_COMPANIES
- GitHub repo under rekaldsi
- Vercel deploy for frontend (static), Railway for backend API
- Convex logging of key events

**Out of scope (v2):**
- Supabase persistence (device sync)
- User accounts / multi-user
- Push alerts / price notifications
- Portfolio tracking / P&L

### Current State
```
/tmp/prd-frank/infra-alpha-deploy/infra-alpha/index.html
  — Single file React app, CDN-loaded
  — 4 tabs: Dashboard | Field Log | Watchlist | Intelligence
  — 8 companies: VRT, ETN, SBGSY, ABB, CMI, NVT, ROK, CAT
  — corsproxy.io → Yahoo Finance for prices (unreliable)
  — Direct browser → api.anthropic.com for AI (client key required)
  — localStorage for all persistence
```

### Proposed Solution

**Architecture:**
```
Frontend (Vercel static):
  index.html — modified to point API calls at our Railway backend

Backend (Railway Express):
  GET /api/prices?symbols=VRT,ETN,... → Yahoo Finance proxy (no CORS issues)
  POST /api/chat → Ollama (local) → fallback Anthropic Sonnet
  GET /health → health check

Local Model Strategy:
  Primary: ollama/qwen3:8b or llama3.2:3b (already running on mac mini)
  Fallback: anthropic/claude-sonnet-4-6 (pro plan)
  Finance-specific: qwen3:8b handles investment analysis well
```

**Companies to Add:**
```javascript
{ ticker:'ENS', name:'EnerSys', cat:'Battery / Energy Storage', tier:2, score:71,
  dcPct:45, cycle:8, crit:5, lock:3, sup:3,
  desc:'Industrial battery systems for DC UPS backup. Mission-critical runtime for Tier 3/4 facilities. Dominant in VRLA and lithium DC backup.',
  tags:['Mission Critical','Recurring'], base:88 },
{ ticker:'HUBB', name:'Hubbell Inc', cat:'Wiring / Electrical Distribution', tier:2, score:64,
  dcPct:20, cycle:15, crit:3, lock:2, sup:3,
  desc:'Electrical wiring devices, distribution products. In every data center build-out. Steady compounder, less sexy but reliable.',
  tags:['Build-Out Play'], base:390 },
{ ticker:'AMETEK', name:'AMETEK Inc', cat:'Power / Electronic Instruments', tier:2, score:69,
  dcPct:25, cycle:10, crit:4, lock:3, sup:3,
  desc:'Electronic instruments, electromechanical devices. Power quality monitoring and precision power equipment for DC environments.',
  tags:['Instruments','Recurring'], base:185 },
```

### Architecture / Touchpoints
```
NEW:
  /Users/jerrycieslik/projects/infra-alpha/
  ├── server/
  │   ├── index.js          — Express server
  │   ├── routes/prices.js  — Yahoo Finance proxy
  │   └── routes/chat.js    — Ollama → Anthropic fallback
  ├── client/
  │   └── index.html        — Modified version of prototype
  ├── package.json
  ├── railway.toml
  └── PRD.md

GitHub: rekaldsi/infra-alpha
Railway: infra-alpha service
Vercel: infra-alpha-client (or serve static from Railway)
Convex: log spawns, deploys, errors
```

### Risk + Blast Radius
- **Low:** Self-contained new project, no existing systems touched
- **Medium:** Ollama model quality for investment analysis — qwen3:8b may need prompt tuning
- **Low:** Railway new service is cheap (hobby plan covers it)

### Rollback Plan
- The original `index.html` is preserved — can revert to it instantly
- Railway service deletion if needed

### Test Plan
- [ ] `GET /api/prices?symbols=VRT,ETN` returns real JSON with price data
- [ ] `POST /api/chat` with a message returns a coherent response
- [ ] Frontend loads and shows real prices (not "fallback" label)
- [ ] Field observation submits and persists in localStorage
- [ ] Intelligence tab chat works without any user-facing API key setup
- [ ] Build deploys clean to Railway

---

## Execution Plan

### M001 — Backend (45 min)
1. `package.json` with Express, axios, node-fetch
2. `server/routes/prices.js` — Yahoo Finance proxy
3. `server/routes/chat.js` — Ollama first, Anthropic fallback
4. `server/index.js` — Express app wiring + health check + static serve of client/
5. `railway.toml` — deployment config
6. `.env.example` — document ANTHROPIC_API_KEY, OLLAMA_URL

### M002 — Frontend Adaptation (30 min)
7. Copy `index.html` → `client/index.html`
8. Patch `fetchPrices()` → hit `/api/prices` instead of corsproxy.io
9. Patch `sendChat()` → hit `/api/chat` instead of api.anthropic.com directly (remove API key requirement from UI)
10. Add ENS + HUBB + AMETEK to BASE_COMPANIES
11. Fix ENS in BRAND_MAP (already there but no company card)
12. Add "Powered by Infra Alpha" footer with version

### M003 — GitHub + Deploy (20 min)
13. `git init` + `gh repo create rekaldsi/infra-alpha --public`
14. Initial commit + push
15. Railway deploy: `railway up`
16. Verify live URL responds
17. Log to Convex

### M004 — Verify + Handoff (10 min)
18. Smoke test all 4 tabs
19. Verify prices are real (not "fallback")
20. Verify AI chat works (local model)
21. Write summary to `/tmp/subagent-result-infra-alpha.md`
22. Update `memory/PROVISION/PROJECT_SUMMARY.md` → add infra-alpha to projects list
23. Write `memory/INFRA-ALPHA/PROJECT_SUMMARY.md`
