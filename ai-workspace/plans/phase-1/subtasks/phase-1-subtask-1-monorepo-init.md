# Phase 1, Subtask 1 — Mono-Repo Initialization

> **Phase**: Phase 1 — Foundation
> **Subtask**: 1 of 5
> **Prerequisites**: None — this is the first subtask
> **Scope**: 4 files to create, 1 command to run

---

## Context

This subtask bootstraps the mono-repo root with Turborepo, pnpm workspaces, and a shared `.gitignore`. All subsequent subtasks depend on this structure being in place.

**Project Root**: `rag-pipeline/`

---

## Relevant Technology Stack

| Component | Version | Notes |
|---|---|---|
| pnpm | 9.15.0 | Package manager — set via `packageManager` field |
| Turborepo | 2.x | `npm install -D turbo` |
| Node.js | 22.x | Runtime for frontend tooling |

---

## Mono-Repo Target Structure

This is the full target structure for the entire project. Subsequent subtasks will reference this briefly but only this subtask includes the complete tree.

```
rag-pipeline/
├── apps/
│   ├── api/                    # FastAPI backend (Python)
│   │   ├── src/
│   │   │   ├── agents/         # LangGraph agent definitions
│   │   │   ├── auth/           # JWT authentication (Phase 7)
│   │   │   ├── crawlers/       # URL + doc discovery
│   │   │   ├── converters/     # markitdown HTML to MD
│   │   │   ├── embeddings/     # FastEmbed model wrappers (Phase 6)
│   │   │   ├── ingest/         # Chunking + Qdrant upsert (Phase 6)
│   │   │   ├── mcp/            # MCP server tools (Phase 7)
│   │   │   ├── routers/        # FastAPI route modules
│   │   │   ├── models/         # SQLAlchemy models
│   │   │   ├── schemas/        # Pydantic schemas
│   │   │   ├── security/       # SSRF prevention (Phase 7)
│   │   │   ├── workers/        # Celery task definitions
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── alembic/
│   │   ├── data/staging/       # Chunk JSON staging area
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── alembic.ini
│   └── web/                    # Next.js frontend
│       ├── src/
│       │   ├── app/            # App Router pages
│       │   ├── components/     # Shared UI components
│       │   ├── features/       # Feature modules
│       │   ├── store/          # Redux store + RTK Query
│       │   └── lib/            # Shared utilities
│       ├── Dockerfile
│       ├── package.json
│       └── tsconfig.json
├── packages/
│   ├── shared-types/           # Shared TS + Python schemas
│   └── config/                 # Shared ESLint/TS configs
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── docker-compose.prod.yml  # Production overrides (Phase 7)
│   ├── traefik/
│   ├── prometheus/              # prometheus.yml (Phase 7)
│   ├── tempo/                   # tempo.yaml (Phase 7)
│   └── grafana/                 # Provisioning + dashboards (Phase 7)
├── .github/
│   └── workflows/
│       └── ci.yml
├── turbo.json
├── package.json
├── pnpm-workspace.yaml
└── ai-workspace/
    └── plans/                  # Planning documents
```

---

## Step-by-Step Implementation

**Working directory**: `rag-pipeline/`

### Step 1: Create the root `package.json`

Create file `rag-pipeline/package.json`:

```json
{
  "name": "rag-pipeline",
  "private": true,
  "packageManager": "pnpm@9.15.0",
  "scripts": {
    "dev": "turbo dev",
    "build": "turbo build",
    "lint": "turbo lint",
    "test": "turbo test",
    "type-check": "turbo type-check"
  },
  "devDependencies": {
    "turbo": "^2.0.0"
  }
}
```

### Step 2: Create `pnpm-workspace.yaml`

Create file `rag-pipeline/pnpm-workspace.yaml`:

```yaml
packages:
  - "apps/*"
  - "packages/*"
```

### Step 3: Create `turbo.json`

Create file `rag-pipeline/turbo.json`:

```json
{
  "$schema": "https://turbo.build/schema.json",
  "globalDependencies": ["**/.env.*local"],
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": [".next/**", "!.next/cache/**", "dist/**"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "lint": {},
    "test": {},
    "type-check": {}
  }
}
```

### Step 4: Create `.gitignore`

Create file `rag-pipeline/.gitignore`:

```gitignore
node_modules/
.next/
dist/
.turbo/
__pycache__/
*.pyc
.venv/
*.egg-info/
.env
.env.local
.env.*.local
*.db
.DS_Store
```

### Step 5: Run initialization

```bash
cd rag-pipeline && pnpm install
```

---

## Files to Create/Modify

| # | File Path | Action |
|---|---|---|
| 1 | `rag-pipeline/package.json` | Create |
| 2 | `rag-pipeline/pnpm-workspace.yaml` | Create |
| 3 | `rag-pipeline/turbo.json` | Create |
| 4 | `rag-pipeline/.gitignore` | Create |

---

## Done-When Checklist

- [ ] `rag-pipeline/package.json` exists with `packageManager` set to `pnpm@9.15.0`
- [ ] `rag-pipeline/pnpm-workspace.yaml` exists with `apps/*` and `packages/*` entries
- [ ] `rag-pipeline/turbo.json` exists with build, dev, lint, test, type-check tasks
- [ ] `rag-pipeline/.gitignore` exists with node_modules, .next, __pycache__, .venv entries
- [ ] `pnpm install` completes successfully at repo root

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-1-subtask-1-monorepo-init-summary.md`

The summary report must include:
- **Subtask**: Phase 1, Subtask 1 — Mono-Repo Initialization
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
