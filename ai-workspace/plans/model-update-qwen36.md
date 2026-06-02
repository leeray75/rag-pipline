# Plan: Update LLM Model to `qwen3.6-35b-a3b`

## Overview

Update the RAG pipeline project to use the `qwen3.6-35b-a3b` model as the primary LLM for both the Audit Agent (quality assessment) and Correction Agent (issue classification and correction generation). The model configuration will be fully externalized via environment variables, supporting both `.env` file and Docker Compose `environment` overrides.

## Current State

### Model Configuration

| Setting | Current Value |
|---|---|
| Model Name | `qwen3-coder-next` |
| Endpoint | `http://spark-8013:4000/v1` |
| API Key | `not-needed` |
| Framework | `langchain_openai.ChatOpenAI` (OpenAI-compatible) |
| Temperature | 0.3 (audit), 0 (correction) |
| Max Tokens | 4096 (audit), 2048/4096 (correction) |

### Target Configuration

| Setting | New Value |
|---|---|
| Model Name | `qwen3.6-35b-a3b` |
| Endpoint | `http://spark-8013:4000/v1` (unchanged) |
| API Key | `sk-change-me-in-production` |
| Temperature | 0.3 (audit), 0 (correction) (unchanged) |
| Max Tokens | 4096 (audit), 2048/4096 (correction) (unchanged) |

### Files with Hardcoded Model References

| File | Lines | Usage |
|---|---|---|
| `apps/api/src/agents/audit_agent.py` | 90-97 | Quality assessment LLM |
| `apps/api/src/agents/correction_agent.py` | 56-62, 111-117 | Issue classification & correction generation (2 instances) |

### Configuration Files

| File | Relevance |
|---|---|
| `apps/api/.env.example` | Lines 35-38 contain commented-out LLM config |
| `apps/api/src/config.py` | No LLM settings currently defined (needs to be added) |
| `infra/docker-compose.yml` | Base compose file — API service environment block (needs LLM vars) |
| `infra/docker-compose.dev.yml` | Dev compose file — API service environment block (needs LLM vars) |
| `infra/docker-compose.prod.yml` | Prod compose file — API/celery environment overrides (may add LLM vars) |
| `apps/api/pyproject.toml` | Dependencies use `langchain-openai>=0.3.0` (compatible with any OpenAI-compatible endpoint) |

---

## Changes Required

### 1. Update `audit_agent.py`

**File**: `apps/api/src/agents/audit_agent.py`

**Change**: Update the `ChatOpenAI` initialization in `_init_llms()` method to use environment variables.

**Before**:
```python
self.claude = ChatOpenAI(
    base_url="http://spark-8013:4000/v1",
    model="qwen3-coder-next",
    api_key="not-needed",
    temperature=0.3,
    max_tokens=4096
)
```

**After**:
```python
self.claude = ChatOpenAI(
    base_url=os.getenv("RAG_LLM_ENDPOINT", "http://spark-8013:4000/v1"),
    model=os.getenv("RAG_LLM_MODEL", "qwen3.6-35b-a3b"),
    api_key=os.getenv("RAG_LLM_API_KEY", "sk-change-me-in-production"),
    temperature=0.3,
    max_tokens=4096
)
```

**Notes**:
- Parameterize `base_url` and `api_key` via environment variables for flexibility
- Update the logger message on line 97 to reflect the new model name

### 2. Update `correction_agent.py`

**File**: `apps/api/src/agents/correction_agent.py`

**Change**: Update both `ChatOpenAI` initializations in `classify_issues()` and `apply_corrections()` functions to use environment variables.

**Before** (classify_issues, lines 56-62):
```python
llm = ChatOpenAI(
    base_url="http://spark-8013:4000/v1",
    model="qwen3-coder-next",
    api_key="not-needed",
    max_tokens=2048,
    temperature=0
)
```

**Before** (apply_corrections, lines 111-117):
```python
llm = ChatOpenAI(
    base_url="http://spark-8013:4000/v1",
    model="qwen3-coder-next",
    api_key="not-needed",
    max_tokens=4096,
    temperature=0
)
```

**After** (both instances):
```python
llm = ChatOpenAI(
    base_url=os.getenv("RAG_LLM_ENDPOINT", "http://spark-8013:4000/v1"),
    model=os.getenv("RAG_LLM_MODEL", "qwen3.6-35b-a3b"),
    api_key=os.getenv("RAG_LLM_API_KEY", "sk-change-me-in-production"),
    max_tokens=<existing_value>,
    temperature=<existing_value>
)
```

**Notes**:
- Add `import os` at the top of the file if not already present
- Keep existing `max_tokens` and `temperature` values per function

### 3. Update `config.py`

**File**: `apps/api/src/config.py`

**Change**: Add LLM configuration settings to the `Settings` class.

**Add**:
```python
# LLM (OpenAI-compatible endpoint)
llm_endpoint: str = "http://spark-8013:4000/v1"
llm_model: str = "qwen3.6-35b-a3b"
llm_api_key: str = "sk-change-me-in-production"
llm_temperature: float = 0.3
llm_max_tokens: int = 4096
```

### 4. Update `.env.example`

**File**: `apps/api/.env.example`

**Change**: Update the LLM configuration section (lines 35-38) with active, updated values.

**Before**:
```env
# --- LLM Configuration (OpenAI-compatible endpoint) ---
# RAG_LLM_ENDPOINT=http://spark-8013:4000/v1
# RAG_LLM_MODEL=qwen3-coder-next
# RAG_LLM_API_KEY=not-needed
```

**After**:
```env
# --- LLM Configuration (OpenAI-compatible endpoint) ---
RAG_LLM_ENDPOINT=http://spark-8013:4000/v1
RAG_LLM_MODEL=qwen3.6-35b-a3b
RAG_LLM_API_KEY=sk-change-me-in-production
RAG_LLM_TEMPERATURE=0.3
RAG_LLM_MAX_TOKENS=4096
```

### 5. Update Agent Documentation Comments

**File**: `apps/api/src/agents/audit_agent.py`

**Change**: Update docstring references to Claude.

- Line 50: `assess_quality - Use Claude LLM for quality assessment` → `assess_quality - Use LLM for quality assessment`
- Line 65: `anthropic_api_key: API key for Claude LLM (optional, deprecated)` → update description
- Line 66: `openai_api_key: API key for OpenAI LLM (optional)` → `openai_api_key: Fallback API key (optional)`
- Line 89: Comment `# OpenAI-compatible endpoint for quality assessment (replacement for Claude)` → update to reference `qwen3.6-35b-a3b`

**File**: `apps/api/src/agents/correction_agent.py`

- Line 55: Docstring `Use Qwen to classify each issue...` → `Use LLM to classify each issue...`

### 6. Update `docker-compose.yml` (Base)

**File**: `infra/docker-compose.yml`

**Change**: Add LLM environment variables to the `api` service's `environment` block (after line 35).

**Add**:
```yaml
      # --- LLM Configuration (OpenAI-compatible endpoint) ---
      - RAG_LLM_ENDPOINT=http://spark-8013:4000/v1
      - RAG_LLM_MODEL=qwen3.6-35b-a3b
      - RAG_LLM_API_KEY=sk-change-me-in-production
      - RAG_LLM_TEMPERATURE=0.3
      - RAG_LLM_MAX_TOKENS=4096
```

**Full context** (api service environment block after change):
```yaml
    environment:
      - RAG_DATABASE_URL=postgresql+asyncpg://rag_user:rag_pass@postgres:5432/rag_pipeline
      - RAG_REDIS_URL=redis://redis:6379/0
      - RAG_QDRANT_HOST=qdrant
      - RAG_CELERY_BROKER_URL=redis://redis:6379/1
      - RAG_CELERY_RESULT_BACKEND=redis://redis:6379/2
      # --- Phase 6: Embedding & Ingestion ---
      - EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
      - EMBEDDING_BATCH_SIZE=100
      - QDRANT_URL=http://qdrant:6333
      # --- LLM Configuration (OpenAI-compatible endpoint) ---
      - RAG_LLM_ENDPOINT=http://spark-8013:4000/v1
      - RAG_LLM_MODEL=qwen3.6-35b-a3b
      - RAG_LLM_API_KEY=sk-change-me-in-production
      - RAG_LLM_TEMPERATURE=0.3
      - RAG_LLM_MAX_TOKENS=4096
```

### 7. Update `docker-compose.dev.yml` (Development)

**File**: `infra/docker-compose.dev.yml`

**Change**: Add LLM environment variables to the `api` service's `environment` block (after line 43).

**Add**:
```yaml
      # --- LLM Configuration (OpenAI-compatible endpoint) ---
      - RAG_LLM_ENDPOINT=http://spark-8013:4000/v1
      - RAG_LLM_MODEL=qwen3.6-35b-a3b
      - RAG_LLM_API_KEY=sk-change-me-in-production
      - RAG_LLM_TEMPERATURE=0.3
      - RAG_LLM_MAX_TOKENS=4096
```

**Full context** (api service environment block after change):
```yaml
    environment:
      - RAG_DATABASE_URL=postgresql+asyncpg://rag_user:rag_pass@postgres:5432/rag_pipeline
      - RAG_REDIS_URL=redis://redis:6379/0
      - RAG_QDRANT_HOST=qdrant
      - RAG_CELERY_BROKER_URL=redis://redis:6379/1
      - RAG_CELERY_RESULT_BACKEND=redis://redis:6379/2
      # --- Phase 6: Embedding & Ingestion ---
      - EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
      - EMBEDDING_BATCH_SIZE=100
      - QDRANT_URL=http://qdrant:6333
      # --- A2A Protocol ---
      - RAG_A2A_BASE_URL=http://localhost:8000
      - RAG_A2A_STREAMING_ENABLED=true
      - RAG_A2A_PUSH_NOTIFICATIONS_ENABLED=false
      # --- LLM Configuration (OpenAI-compatible endpoint) ---
      - RAG_LLM_ENDPOINT=http://spark-8013:4000/v1
      - RAG_LLM_MODEL=qwen3.6-35b-a3b
      - RAG_LLM_API_KEY=sk-change-me-in-production
      - RAG_LLM_TEMPERATURE=0.3
      - RAG_LLM_MAX_TOKENS=4096
```

### 8. Update `docker-compose.prod.yml` (Production) — Optional Override

**File**: `infra/docker-compose.prod.yml`

**Change**: Add LLM environment variable overrides in the `api` and `celery-worker` service environment blocks for production-specific values.

Since the default API key (`sk-change-me-in-production`) is already set in the base compose file, the prod override file only needs to be used if you want to use a **different** API key in production. If the same key is used across environments, no changes to `docker-compose.prod.yml` are needed.

**Option A — Same API key in all environments** (recommended for now):
- No changes needed to `docker-compose.prod.yml`. The base file's LLM env vars will apply.

**Option B — Different API key in production**:
```yaml
services:
  api:
    environment:
      # --- LLM Configuration (production override) ---
      - RAG_LLM_API_KEY=<your-different-production-api-key>

  celery-worker:
    environment:
      # --- LLM Configuration (production override) ---
      - RAG_LLM_API_KEY=<your-different-production-api-key>
```

**Notes**:
- Replace `<your-different-production-api-key>` with the actual production API key if using Option B
- This file uses overlay behavior — only variables listed here override the base compose file

---

## Configuration Hierarchy

The LLM settings follow this priority order (highest to lowest):

1. **Docker Compose prod override** (`docker-compose.prod.yml`) — production-specific values
2. **Docker Compose dev override** (`docker-compose.dev.yml`) — development-specific values
3. **Docker Compose base** (`docker-compose.yml`) — default values for all environments
4. **`.env` file** — local environment overrides (if present)
5. **`.env.example`** — documented defaults
6. **Code defaults** — fallback values in `os.getenv()` calls

This allows environment-specific configuration without modifying code:

```
Production:  docker compose -f docker-compose.yml -f docker-compose.prod.yml up
Development: docker compose -f docker-compose.dev.yml up     (or base compose)
Local dev:   .env file + direct python run (no docker)
```

---

## Environment Variables Reference

| Variable | Default | Docker Compose Default | Description |
|---|---|---|---|
| `RAG_LLM_ENDPOINT` | (none) | `http://spark-8013:4000/v1` | OpenAI-compatible API endpoint |
| `RAG_LLM_MODEL` | `qwen3.6-35b-a3b` | `qwen3.6-35b-a3b` | Model name to use |
| `RAG_LLM_API_KEY` | `sk-change-me-in-production` | `sk-change-me-in-production` | API key for the LLM endpoint |
| `RAG_LLM_TEMPERATURE` | `0.3` | `0.3` | Default temperature for audit agent |
| `RAG_LLM_MAX_TOKENS` | `4096` | `4096` | Default max tokens for audit agent |

---

## Deployment Instructions

### Docker Compose Deployment

**Development**:
```bash
cd rag-pipline/infra
docker compose -f docker-compose.dev.yml up -d
```

**Production** (use the same API key or update `docker-compose.prod.yml` with a different key):
```bash
cd rag-pipline/infra
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Local Development (without Docker)

1. Copy `.env.example` to `.env`:
   ```bash
   cp apps/api/.env.example apps/api/.env
   ```

2. Edit `apps/api/.env` with your values:
   ```env
   RAG_LLM_ENDPOINT=http://your-endpoint:port/v1
   RAG_LLM_MODEL=qwen3.6-35b-a3b
   RAG_LLM_API_KEY=sk-change-me-in-production
   ```

3. Start the services as normal.

---

## Testing Checklist

- [ ] Verify the `qwen3.6-35b-a3b` model is accessible at the configured endpoint
- [ ] Test audit agent quality assessment with the new model
- [ ] Test correction agent issue classification with the new model
- [ ] Test correction agent correction generation with the new model
- [ ] Verify JSON parsing of model responses (format may differ from `qwen3-coder-next`)
- [ ] Check that max_tokens/temperature settings are appropriate for the new model
- [ ] Verify no token limit issues (qwen3.6-35b-a3b may have different context window limits)
- [ ] Test Docker Compose dev deployment with new LLM env vars
- [ ] Test Docker Compose prod deployment with production LLM overrides
- [ ] Run existing test suite (if available)

---

## Risk Assessment

| Risk | Level | Mitigation |
|---|---|---|
| Model endpoint incompatibility | Low | Uses OpenAI-compatible API format; endpoint already proven working |
| Response format changes | Medium | New model may return different JSON structure; add error handling |
| Performance differences | Low-Medium | qwen3.6-35b-a3b may be slower/faster; monitor latency |
| Token limits | Low | Verify context window supports full document content |
| Config not propagated to celery-worker | Medium | Celery worker also needs LLM env vars for async tasks |

---

## Rollback Plan

Since the model name and endpoint are controlled via environment variables, rollback is trivial:

1. **Docker Compose**: Change `RAG_LLM_MODEL` and/or `RAG_LLM_ENDPOINT` back to `qwen3-coder-next` and `http://spark-8013:4000/v1` in the appropriate compose file (dev or prod), then restart:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate api celery-worker
   ```

2. **Local/.env**: Change values in `apps/api/.env` and restart the service.

No code changes are required for rollback.

---

## Files Modified Summary

| File | Action | Description |
|---|---|---|
| `apps/api/src/agents/audit_agent.py` | Modify | Update model name, parameterize config via env vars, update docs |
| `apps/api/src/agents/correction_agent.py` | Modify | Update model name, parameterize config via env vars |
| `apps/api/src/config.py` | Modify | Add LLM settings to Settings class |
| `apps/api/.env.example` | Modify | Update/add LLM environment variable examples |
| `infra/docker-compose.yml` | Modify | Add LLM env vars to api service |
| `infra/docker-compose.dev.yml` | Modify | Add LLM env vars to api service |
| `infra/docker-compose.prod.yml` | Optional | Add LLM API key override for production (only if different from default) |

---

## Estimated Effort

- **Lines of code to change**: ~20-30
- **Files to modify**: 6-7 (depending on prod config)
- **Estimated time**: 45-90 minutes (including testing)