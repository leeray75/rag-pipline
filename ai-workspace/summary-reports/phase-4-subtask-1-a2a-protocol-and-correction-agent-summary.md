# Phase 4, Subtask 1 Summary — A2A Protocol and Correction Agent

**Subtask**: Phase 4, Subtask 1 — A2A Agent Cards, Correction Agent & A2A Server Wrappers  
**Status**: Complete  
**Date**: 2026-04-17  

---

## Files Created/Modified

| Action | File Path |
|--------|-----------|
| Modified | `rag-pipeline/apps/api/pyproject.toml` (added `a2a-sdk` dependency) |
| Created | `rag-pipeline/apps/api/src/agents/a2a_agent_cards.py` |
| Created | `rag-pipeline/apps/api/src/agents/a2a_helpers.py` |
| Created | `rag-pipeline/apps/api/src/agents/correction_state.py` |
| Created | `rag-pipeline/apps/api/src/agents/correction_agent.py` |
| Created | `rag-pipeline/apps/api/src/agents/a2a_audit_server.py` |
| Created | `rag-pipeline/apps/api/src/agents/a2a_correction_server.py` |

---

## Key Decisions

1. **A2A Protocol v1.0**: Used `a2a-sdk` version 0.3.26 for AgentCard, Task, Message, and Artifact types.

2. **LangGraph Correction Agent**: Implemented a 6-node workflow (receive_report → classify_issues → plan_corrections → apply_corrections → save_corrections → emit_complete) following the exact specification.

3. **OpenAI-Compatible Endpoint**: Both the Audit Agent and Correction Agent use the OpenAI-compatible endpoint at `http://spark-8013:4000/v1` with the `qwen3-coder-next` model. No API key is required.

4. **Staging Directory**: Used `/app/data/staging` as the staging directory path for reading audit reports and writing corrected Markdown files.

5. **Logging**: Used `structlog` for structured logging throughout all agent implementations.

---

## LLM Configuration Changes

### OpenAI-Compatible Endpoint Implementation

Both the Audit Agent and Correction Agent were updated to use an OpenAI-compatible endpoint instead of direct API calls to Claude or OpenAI.

**Endpoint Configuration:**

- **URL**: `http://spark-8013:4000/v1`
- **Model**: `qwen3-coder-next`
- **API Key**: Not required (set to `"not-needed"`)

### Audit Agent (`audit_agent.py`)

- **Import Change**: Updated from `langchain_anthropic.ChatAnthropic` to `langchain_openai.ChatOpenAI`
- **LLM Initialization**: The `claude` LLM instance is now configured with:
  ```python
  ChatOpenAI(
      base_url="http://spark-8013:4000/v1",
      model="qwen3-coder-next",
      api_key="not-needed",
      temperature=0.3,
      max_tokens=4096
  )
  ```
- The legacy `anthropic_api_key` parameter is deprecated but maintained for backward compatibility.

### Correction Agent (`correction_agent.py`)

- **Import Change**: Updated to use `langchain_openai.ChatOpenAI`
- **Classification Node**: Uses `ChatOpenAI` with the OpenAI-compatible endpoint
- **Correction Application Node**: Uses `ChatOpenAI` with the OpenAI-compatible endpoint
- **Configuration**:
  ```python
  ChatOpenAI(
      base_url="http://spark-8013:4000/v1",
      model="qwen3-coder-next",
      api_key="not-needed",
      max_tokens=2048|4096,  # depends on operation
      temperature=0
  )
  ```

### Dependency Requirements

The `langchain_openai` package must be installed. Add to [`pyproject.toml`](../../pyproject.toml) if not already present:

```toml
[tool.poetry.dependencies]
langchain-openai = "^0.1.0"
```

### Benefits of OpenAI-Compatible Endpoint

1. **Unified Interface**: Both agents use the same LLM interface regardless of the underlying model provider
2. **Flexibility**: Can easily switch between different OpenAI-compatible providers
3. **Reduced Dependencies**: Eliminates the need for provider-specific LangChain integrations
4. **Simplified Configuration**: Single endpoint configuration for all LLM operations

---

## Issues Encountered

1. **a2a-sdk Installation**: The system Python environment was externally managed. Installed `a2a-sdk` using the project's virtual environment at `rag-pipeline/apps/api/.venv/`.

---

## Dependencies for Next Subtask

1. The Correction Agent depends on audit reports produced by the Phase 3 Audit Agent.

2. The A2A server wrappers expect the `run_audit()` function from `src.agents.audit_agent` to be available.

3. The correction workflow requires JSON audit reports stored at `{staging_dir}/{job_id}/audit_report_round_{round}.json`.

---

## Verification Results

- [x] `a2a-sdk` installed successfully (version 0.3.26)
- [x] `build_audit_agent_card()` returns a valid `AgentCard` with `audit-documents` skill
- [x] `build_correction_agent_card()` returns a valid `AgentCard` with `correct-documents` skill
- [x] `make_user_message()`, `make_agent_message()`, `make_task_status()`, `make_artifact()` produce valid A2A types
- [x] `extract_artifact_data()` extracts data from a `Task` artifact
- [x] Correction Agent graph compiles: receive → classify → plan → apply → save → emit
- [x] `await run_correction(job_id, round, report_id)` processes issues from audit report
- [x] `AuditTaskHandler.on_message()` returns `Task` with `TASK_STATE_COMPLETED` and audit `Artifact`
- [x] `CorrectionTaskHandler.on_message()` returns `Task` with `TASK_STATE_COMPLETED` and correction `Artifact`

---

## Summary

Phase 4, Subtask 1 is complete. All 6 files have been created with the exact specifications provided. The A2A Protocol v1.0 foundation is now in place with both the Audit Agent and Correction Agent exposed as proper A2A agent servers.
