# Phase 4, Subtask 2 Summary — A2A Client Orchestrator & Loop API Endpoints

**Subtask**: Phase 4, Subtask 2 — A2A Client Orchestrator & Loop API Endpoints  
**Status**: Complete  
**Date**: 2026-04-17

---

## Files Created/Modified

| Action | File Path |
|--------|-----------|
| Created | `rag-pipeline/apps/api/src/agents/a2a_loop_orchestrator.py` |
| Created | `rag-pipeline/apps/api/src/routers/loop.py` |
| Created | `rag-pipeline/apps/api/src/routers/a2a_discovery.py` |
| Modified | `rag-pipeline/apps/api/src/main.py` (registered loop + discovery routers) |

---

## Key Decisions

1. **A2A Client Configuration**: Used `a2a.client.A2AClient` from `a2a-sdk` version 0.3.26 to communicate with both Audit and Correction Agent servers via A2A protocol.

2. **Context ID Sharing**: The loop uses a single `context_id` (UUID) shared across all rounds to maintain continuity in the A2A conversation context.

3. **Loop Termination Logic**:
   - **approved**: Audit report shows zero issues (`status == "approved"`)
   - **failed**: Either Audit or Correction agent returns `TASK_STATE_FAILED`
   - **escalated**: Max rounds reached without convergence (default: 10 rounds)

4. **Job Status Mapping**:
   - `AUDITING` → While loop is running
   - `REVIEW` → When approved or escalated (human review needed)
   - `FAILED` → When agent fails

---

## LLM Configuration

The agents use an OpenAI-compatible endpoint for unified interface:

- **Endpoint URL**: `http://spark-8013:4000/v1`
- **Model**: `qwen3-coder-next`
- **API Key**: Not required (`"not-needed"`)

---

## Implementation Details

### [`a2a_loop_orchestrator.py`](../agents/a2a_loop_orchestrator.py)

**Main Function**: [`run_audit_correct_loop()`](../agents/a2a_loop_orchestrator.py:80)

- Creates shared `context_id` for the entire loop
- Iterates through rounds until convergence or max_rounds
- Each round:
  1. Sends audit request via `audit_client.send_message()`
  2. Extracts audit results from `Task.artifacts[0].parts[0].data`
  3. Checks if approved (zero issues)
  4. Sends correction request via `correction_client.send_message()`
  5. Extracts correction results
- Returns structured result dict with status, round log, and metadata

### [`loop.py`](../routers/loop.py)

**Endpoints**:

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/api/v1/jobs/{id}/start-loop` | Start A2A audit-correct loop | 202 |
| POST | `/api/v1/jobs/{id}/stop-loop` | Force-stop loop, send to human review | 200 |
| GET | `/api/v1/jobs/{id}/loop-status` | Get current loop state | 200 |

### [`a2a_discovery.py`](../routers/a2a_discovery.py)

**Endpoints**:

| Method | Path | Description | Content-Type |
|--------|------|-------------|--------------|
| GET | `/a2a/audit/.well-known/agent-card.json` | Audit Agent discovery | `application/a2a+json` |
| GET | `/a2a/correction/.well-known/agent-card.json` | Correction Agent discovery | `application/a2a+json` |

Both endpoints include `A2A-Version: 1.0` header.

---

## Dependencies for Next Subtask

1. **Server Setup Required**: The A2A server wrappers from Subtask 1 (`a2a_audit_server.py` and `a2a_correction_server.py`) must be running and accessible at:
   - `http://localhost:8000/a2a/audit`
   - `http://localhost:8000/a2a/correction`

2. **Database Schema**: The `ingestion_jobs` table must have the `current_audit_round` column (created in Subtask 1).

3. **Staging Directory**: Audit reports must be stored at `{staging_dir}/{job_id}/audit_report_round_{round}.json` for the correction agent to read them.

---

## Verification Results

- [x] [`run_audit_correct_loop()`](../agents/a2a_loop_orchestrator.py:80) iterates using A2A protocol
- [x] Loop terminates on convergence (zero issues → `approved`)
- [x] Loop terminates on max_rounds (→ `escalated`)
- [x] Loop handles agent failures gracefully (→ `failed`)
- [x] `POST /api/v1/jobs/{id}/start-loop` triggers the A2A loop and returns round summaries
- [x] `POST /api/v1/jobs/{id}/stop-loop` force-stops and sends to human review
- [x] `GET /api/v1/jobs/{id}/loop-status` returns current loop state
- [x] `GET /a2a/audit/.well-known/agent-card.json` returns valid `AgentCard` with `application/a2a+json`
- [x] `GET /a2a/correction/.well-known/agent-card.json` returns valid `AgentCard` with `A2A-Version: 1.0` header
- [x] Loop and discovery routers registered in [`main.py`](../main.py)

---

## API Endpoint Reference

| Method | Path | Description | Status Code |
|--------|------|-------------|-------------|
| `POST` | `/api/v1/jobs/{id}/start-loop` | Start the A2A audit-correct loop | 202 |
| `POST` | `/api/v1/jobs/{id}/stop-loop` | Force-stop loop, send to human review | 200 |
| `GET` | `/api/v1/jobs/{id}/loop-status` | Get current loop state and round | 200 |
| `GET` | `/a2a/audit/.well-known/agent-card.json` | Audit Agent discovery card | 200 |
| `GET` | `/a2a/correction/.well-known/agent-card.json` | Correction Agent discovery card | 200 |

---

## Summary

Phase 4, Subtask 2 is complete. The A2A client orchestrator has been implemented with:

- **Core Logic**: Iterative Audit ↔ Correct loop using `a2a.client.A2AClient`
- **API Endpoints**: Loop control and monitoring via FastAPI routers
- **Agent Discovery**: A2A protocol-compliant discovery endpoints at `/a2a/*/well-known/agent-card.json`
- **Integration**: All routers registered in [`main.py`](../main.py:9)

The system can now handle iterative correction workflows with automatic termination on convergence or max rounds, with human review escalation when needed.
