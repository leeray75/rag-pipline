# LLM Alignment Plan for RAG Pipeline API

**Generated:** 2026-04-22
**Project:** RAG Pipeline
**Scope:** Identify and align all LLM usage across the API to use a consistent OpenAI-compatible endpoint

---

## Executive Summary

**Issue**: The crawler in `rag-pipline/apps/api/src/crawlers/link_discovery.py` uses a different LLM (Anthropic Claude) than the agents in `rag-pipline/apps/api/src/agents` (OpenAI-compatible endpoint with `qwen3-coder-next` model).

**Impact**: Inconsistent LLM usage across the pipeline creates:
- Increased operational complexity
- Potential cost inefficiencies
- Reduced maintainability
- Possible quality inconsistencies

**Solution**: Update the crawler to use the same OpenAI-compatible endpoint as the agents.

---

## Summary Report Findings

The [`consolidated-rag-pipeline-summary-report-2026-04-17.md`](../summary-reports/consolidated-rag-pipeline-summary-report-2026-04-17.md) confirms the LLM configuration strategy:

> **Line 118**: "All LLM operations use an OpenAI-compatible endpoint, eliminating provider-specific dependencies and simplifying configuration."

However, the code in `link_discovery.py` still uses `ChatAnthropic` directly, which is inconsistent with this stated strategy.

---

## Current State Analysis

### Complete LLM Inventory in API

**Search Scope**: `rag-pipline/apps/api/src/` (all `.py` files)

| File | LLM Type | Model | Endpoint | Status |
|------|----------|-------|----------|--------|
| [`agents/audit_agent.py`](../apps/api/src/agents/audit_agent.py:90) | OpenAI-compatible | `qwen3-coder-next` | `http://spark-8013:4000/v1` | ✅ Aligned |
| [`agents/correction_agent.py`](../apps/api/src/agents/correction_agent.py:56) | OpenAI-compatible | `qwen3-coder-next` | `http://spark-8013:4000/v1` | ✅ Aligned |
| [`agents/correction_agent.py`](../apps/api/src/agents/correction_agent.py:111) | OpenAI-compatible | `qwen3-coder-next` | `http://spark-8013:4000/v1` | ✅ Aligned |
| [`crawlers/link_discovery.py`](../apps/api/src/crawlers/link_discovery.py:90) | **Anthropic** | `claude-sonnet-4-20250514` | Default Anthropic | ❌ **Needs Update** |

### Agent LLM Configuration (Aligned)

**Location**: [`rag-pipline/apps/api/src/agents/`](../apps/api/src/agents)

**Code Pattern**:
```python
llm = ChatOpenAI(
    base_url="http://spark-8013:4000/v1",
    model="qwen3-coder-next",
    api_key="not-needed",
    temperature=0.3,
    max_tokens=4096
)
```

### Crawler LLM Configuration (Needs Update)

**Location**: [`rag-pipline/apps/api/src/crawlers/link_discovery.py`](../apps/api/src/crawlers/link_discovery.py:90)

**Current Code**:
```python
llm = ChatAnthropic(model="claude-sonnet-4-20250514", max_tokens=4096, temperature=0)
```

**Required Change**:
```python
llm = ChatOpenAI(
    base_url="http://spark-8013:4000/v1",
    model="qwen3-coder-next",
    api_key="not-needed",
    max_tokens=4096,
    temperature=0
)
```

---

## Migration Plan

### Step 1: Update `link_discovery.py`

**File**: [`rag-pipline/apps/api/src/crawlers/link_discovery.py`](../apps/api/src/crawlers/link_discovery.py:90)

**Current Import**:
```python
from langchain_anthropic import ChatAnthropic
```

**Required Change**:
```python
from langchain_openai import ChatOpenAI
```

**Current Usage**:
```python
llm = ChatAnthropic(model="claude-sonnet-4-20250514", max_tokens=4096, temperature=0)
```

**Required Change**:
```python
llm = ChatOpenAI(
    base_url="http://spark-8013:4000/v1",
    model="qwen3-coder-next",
    api_key="not-needed",
    max_tokens=4096,
    temperature=0
)
```

### Step 2: Update Dependencies

**File**: [`rag-pipline/apps/api/pyproject.toml`](../apps/api/pyproject.toml)

**Current Dependency**:
```toml
langchain-anthropic = "..."
```

**Required Change**: Remove or keep as optional (if other parts use it)

**Add/Verify**:
```toml
langchain-openai = "..."
```

### Step 3: Update Environment Configuration

**File**: [`rag-pipline/apps/api/src/config.py`](../apps/api/src/config.py)

**Current Settings**:
```python
class Settings(BaseSettings):
    # No LLM-specific settings
```

**Recommended Addition**:
```python
class Settings(BaseSettings):
    # LLM Configuration
    llm_endpoint: str = "http://spark-8013:4000/v1"
    llm_model: str = "qwen3-coder-next"
    llm_api_key: str = "not-needed"
    
    model_config = {"env_prefix": "RAG_", "env_file": ".env"}
```

**Benefits**:
- Centralized LLM configuration
- Easier environment switching
- Consistent settings across agents and crawlers

---

## Pros/Cons Analysis

### Using Anthropic Claude (Current Crawler State)

| Pros | Cons |
|------|------|
| ✅ High-quality reasoning for link extraction | ❌ Requires separate API key management |
| ✅ Proven performance on structured tasks | ❌ Different cost structure than agents |
| | ❌ Inconsistent with agent LLM choice |
| | ❌ Hardcoded model name in crawler |

### Using OpenAI-Compatible Endpoint (Proposed)

| Pros | Cons |
|------|------|
| ✅ Consistent with agents (qwen3-coder-next) | ❌ May have different quality characteristics |
| ✅ Single API key management | ⚠️ Requires testing for link extraction quality |
| ✅ Centralized endpoint configuration | |
| ✅ Easier to swap models globally | |

---

## Testing Strategy

### Unit Tests
1. Verify `extract_links_with_llm()` returns valid links
2. Test with sample HTML containing various link patterns
3. Compare results between Claude and Qwen models

### Integration Tests
1. Run full crawl pipeline on test documentation site
2. Verify link discovery quality is maintained
3. Monitor for any failures or degraded performance

### Quality Metrics
- **Precision**: % of discovered links that are valid documentation pages
- **Recall**: % of documentation pages that are discovered
- **Latency**: Time to extract links from HTML

---

## Implementation Checklist

- [ ] Update import in `link_discovery.py` from `ChatAnthropic` to `ChatOpenAI`
- [ ] Update LLM initialization with correct endpoint, model, and API key
- [ ] Update `pyproject.toml` dependencies
- [ ] Add LLM configuration to `config.py`
- [ ] Update `.env.example` with new LLM settings
- [ ] Run unit tests for link discovery
- [ ] Run integration tests on test site
- [ ] Compare quality metrics between old and new LLM
- [ ] Update documentation in `AGENTS.md` if applicable

---

## Rollback Plan

If issues are detected after migration:

1. Revert `link_discovery.py` to use `ChatAnthropic`
2. Restore original import and LLM initialization
3. Revert `pyproject.toml` changes
4. Revert `config.py` changes

---

## Additional Findings from Summary Report

### LLM Configuration Strategy

The [`consolidated-rag-pipeline-summary-report-2026-04-17.md`](../summary-reports/consolidated-rag-pipeline-summary-report-2026-04-17.md) confirms the following:

| Finding | Location | Details |
|---------|----------|---------|
| OpenAI-compatible endpoint | Line 118 | "All LLM operations use an OpenAI-compatible endpoint" |
| Claude LLM usage | Phase 3 | Quality assessment uses Claude LLM (now migrated to OpenAI-compatible) |
| A2A Protocol | Phase 4 | Agent Actions Alliance protocol for agent communication |

### Audit Agent Migration Note

The audit agent's [`audit_agent.py:16`](../apps/api/src/agents/audit_agent.py:16) contains a comment indicating the migration from Anthropic:

```python
# from langchain_anthropic import ChatAnthropic  # Using OpenAI-compatible endpoint instead
```

This confirms the project's direction toward a unified OpenAI-compatible endpoint.

---

## Timeline Estimate

| Task | Estimated Time |
|------|----------------|
| Code changes | 15 minutes |
| Testing | 30 minutes |
| Documentation update | 15 minutes |
| **Total** | **1 hour** |

---

## References

### Code Files
- Agent LLM Configuration: [`audit_agent.py:90`](../apps/api/src/agents/audit_agent.py:90)
- Crawler LLM Configuration: [`link_discovery.py:90`](../apps/api/src/crawlers/link_discovery.py:90)
- Correction Agent LLM: [`correction_agent.py:56`](../apps/api/src/agents/correction_agent.py:56)

### Documentation
- [`consolidated-rag-pipeline-summary-report-2026-04-17.md`](../summary-reports/consolidated-rag-pipeline-summary-report-2026-04-17.md)
- [`phase-3-audit-agent.md`](../plans/phase-3-audit-agent.md)
- [`phase-4-correction-agent.md`](../plans/phase-4-correction-agent.md)

### Libraries
- LangChain OpenAI Integration: https://python.langchain.com/docs/integrations/chat/openai/
- LangChain Anthropic Integration: https://python.langchain.com/docs/integrations/chat/anthropic/
- A2A Protocol: https://github.com/agent-actions-alliance/a2a
