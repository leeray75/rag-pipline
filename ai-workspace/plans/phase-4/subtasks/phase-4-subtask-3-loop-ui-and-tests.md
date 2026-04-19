# Phase 4, Subtask 3 — Loop Monitoring UI, Tests & Validation

> **Phase**: Phase 4 — Correction Agent & Iterative Audit Loop (A2A Protocol v1.0)
> **Subtask**: 3 of 3
> **Prerequisites**: Phase 3 complete + Phase 4 Subtasks 1 and 2 complete (A2A agent cards, helpers, correction agent, A2A server wrappers, A2A client orchestrator, loop API endpoints, and agent discovery endpoints all functional).
> **Scope**: 2 new frontend files, 1 frontend modification, 1 new test file

---

## Objective

Build the Loop Monitoring UI page that displays the round timeline with A2A task states and loop status using RTK Query. Write unit tests for the A2A helper functions and agent card builders. Complete the Phase 4 Done-When checklist.

---

## Relevant Technology Stack

### Frontend

| Package | Version | Install |
|---|---|---|
| Next.js | 16.2.3 | `npx create-next-app@latest` |
| React | 19.2.5 | bundled with Next.js |
| Redux Toolkit | 2.11.2 | `npm install @reduxjs/toolkit react-redux` |
| TailwindCSS | 4.2.2 | `npm install tailwindcss` |
| shadcn/ui | latest | `npx shadcn@latest init` |

### Python (tests only)

| Package | Version | Install |
|---|---|---|
| Python | 3.13.x | Runtime |
| a2a-sdk | latest | `pip install a2a-sdk` |
| pytest | 8.x | `pip install pytest` |
| pytest-asyncio | 0.25.x | `pip install pytest-asyncio` |

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| **Create** | `rag-pipeline/apps/web/src/store/api/loop-api.ts` |
| **Create** | `rag-pipeline/apps/web/src/app/loop/[jobId]/page.tsx` |
| **Modify** | `rag-pipeline/apps/web/src/app/layout.tsx` (add nav link) |
| **Create** | `rag-pipeline/apps/api/tests/test_a2a_helpers.py` |

---

## Context: API Endpoints from Subtask 2

The frontend communicates with these endpoints created in Subtask 2:

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/jobs/{id}/start-loop` | Start the A2A audit-correct loop. Accepts `?max_rounds=N`. Returns `LoopResult`. |
| `POST` | `/api/v1/jobs/{id}/stop-loop` | Force-stop loop. Returns `{ status, message }`. |
| `GET` | `/api/v1/jobs/{id}/loop-status` | Get current loop state and round. Returns `LoopStatus`. |

The `LoopResult` response includes A2A task IDs and task states for each round, reflecting the official A2A Protocol v1.0 `Task` lifecycle.

---

## Step 1: Create RTK Query Endpoints

**Path**: `rag-pipeline/apps/web/src/store/api/loop-api.ts`

This file injects loop-related endpoints into the existing RTK Query `apiSlice`. The types reflect the A2A protocol — each round includes `audit_task_id`, `audit_task_state`, and optionally `correction_task_id`/`correction_task_state`.

```typescript
import { apiSlice } from "./api-slice";

export interface LoopRound {
  round: number;
  audit_task_id: string;
  audit_task_state: string;
  audit_issues: number;
  audit_status: string;
  report_id: string;
  correction_applied: boolean;
  correction_task_id?: string;
  correction_task_state?: string;
  docs_corrected: number;
  false_positives: number;
}

export interface LoopResult {
  status: string;
  final_round: number;
  total_rounds: number;
  rounds: LoopRound[];
  reason?: string;
}

export interface LoopStatus {
  job_id: string;
  status: string;
  current_round: number;
}

export const loopApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    startLoop: builder.mutation<
      LoopResult,
      { jobId: string; maxRounds?: number }
    >({
      query: ({ jobId, maxRounds }) => ({
        url: `/jobs/${jobId}/start-loop${maxRounds ? `?max_rounds=${maxRounds}` : ""}`,
        method: "POST",
      }),
    }),
    stopLoop: builder.mutation<{ status: string; message: string }, string>({
      query: (jobId) => ({
        url: `/jobs/${jobId}/stop-loop`,
        method: "POST",
      }),
    }),
    getLoopStatus: builder.query<LoopStatus, string>({
      query: (jobId) => `/jobs/${jobId}/loop-status`,
    }),
  }),
});

export const {
  useStartLoopMutation,
  useStopLoopMutation,
  useGetLoopStatusQuery,
} = loopApi;
```

---

## Step 2: Create Loop Monitor Page

**Path**: `rag-pipeline/apps/web/src/app/loop/[jobId]/page.tsx`

This page displays:
1. Controls to start/stop the loop with configurable max rounds
2. Current loop status with polling (5-second interval)
3. A round timeline showing A2A task states, issue counts, and correction stats per round

The page uses shadcn/ui components: `Card`, `CardContent`, `CardHeader`, `CardTitle`, `Badge`, and `Button`.

```tsx
"use client";

import { use, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  useStartLoopMutation,
  useStopLoopMutation,
  useGetLoopStatusQuery,
  type LoopRound,
} from "@/store/api/loop-api";

export default function LoopPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = use(params);
  const [startLoop, { data: loopResult, isLoading: isRunning }] =
    useStartLoopMutation();
  const [stopLoop] = useStopLoopMutation();
  const { data: loopStatus } = useGetLoopStatusQuery(jobId, {
    pollingInterval: 5000,
  });
  const [maxRounds, setMaxRounds] = useState(10);

  return (
    <main className="container mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">
          Audit-Correct Loop — A2A Protocol
        </h1>
        <div className="flex items-center gap-4">
          <label className="text-sm">
            Max Rounds:
            <input
              type="number"
              value={maxRounds}
              onChange={(e) => setMaxRounds(Number(e.target.value))}
              min={1}
              max={50}
              className="ml-2 w-16 border rounded px-2 py-1"
            />
          </label>
          <Button
            onClick={() => startLoop({ jobId, maxRounds })}
            disabled={isRunning}
          >
            {isRunning ? "Running..." : "Start Loop"}
          </Button>
          <Button variant="destructive" onClick={() => stopLoop(jobId)}>
            Force Stop
          </Button>
        </div>
      </div>

      {/* Current Status */}
      {loopStatus && (
        <Card className="mb-4">
          <CardContent className="pt-4">
            <p className="text-sm">
              Status: <Badge>{loopStatus.status}</Badge> — Round:{" "}
              {loopStatus.current_round}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Round Timeline */}
      {loopResult && (
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Loop Result
              <Badge
                variant={
                  loopResult.status === "approved" ? "default" : "destructive"
                }
              >
                {loopResult.status}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 overflow-x-auto pb-4">
              {loopResult.rounds.map((round: LoopRound) => (
                <div
                  key={round.round}
                  className="flex flex-col items-center min-w-[180px] p-4 border rounded-lg"
                >
                  <span className="text-xs font-semibold mb-1">
                    Round {round.round}
                  </span>
                  <Badge
                    variant={
                      round.audit_issues === 0 ? "default" : "destructive"
                    }
                    className="mb-2"
                  >
                    {round.audit_issues} issues
                  </Badge>
                  <span className="text-xs text-muted-foreground mb-1">
                    Audit: {round.audit_task_state}
                  </span>
                  {round.correction_applied && (
                    <div className="text-xs text-center">
                      <p>{round.docs_corrected} docs fixed</p>
                      <p>{round.false_positives} false positives</p>
                      {round.correction_task_state && (
                        <p className="text-muted-foreground">
                          Correction: {round.correction_task_state}
                        </p>
                      )}
                    </div>
                  )}
                  {round.audit_status === "approved" && (
                    <span className="text-green-600 text-lg mt-1">✓</span>
                  )}
                </div>
              ))}
            </div>
            {loopResult.reason && (
              <p className="text-sm text-muted-foreground mt-2">
                ⚠️ {loopResult.reason}
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
```

---

## Step 3: Add Navigation Link

**Path**: `rag-pipeline/apps/web/src/app/layout.tsx`

In the layout navigation bar, add a link to the Loop Monitor page:

```tsx
<a href="/loop" className="text-sm hover:underline">Loop Monitor</a>
```

Add this alongside the existing navigation links (Jobs, Audit). The exact placement depends on the existing nav structure from Phase 1/2/3.

---

## Step 4: Create A2A Helper & Agent Card Tests

**Path**: `rag-pipeline/apps/api/tests/test_a2a_helpers.py`

These 8 tests validate the A2A helper functions and agent card builders using official `a2a.types`.

```python
"""Tests for A2A helper functions and agent card builders."""

from a2a.types import Task, TaskState, Role

from src.agents.a2a_helpers import (
    make_user_message,
    make_agent_message,
    make_task_status,
    make_artifact,
    extract_artifact_data,
)
from src.agents.a2a_agent_cards import (
    build_audit_agent_card,
    build_correction_agent_card,
)


def test_make_user_message_has_data_part():
    """User message should contain a DataPart with the provided data."""
    msg = make_user_message(
        context_id="ctx-1", data={"job_id": "j1"}, text="Hello",
    )
    assert msg.role == Role.ROLE_USER
    assert msg.contextId == "ctx-1"
    assert len(msg.parts) == 2  # TextPart + DataPart
    assert hasattr(msg.parts[1], "data")
    assert msg.parts[1].data["job_id"] == "j1"


def test_make_user_message_without_text():
    """User message without text should have only a DataPart."""
    msg = make_user_message(context_id="ctx-2", data={"round": 1})
    assert len(msg.parts) == 1  # DataPart only
    assert hasattr(msg.parts[0], "data")


def test_make_agent_message_has_text():
    """Agent message should contain a TextPart."""
    msg = make_agent_message(
        context_id="ctx-1", task_id="t-1", text="Done",
    )
    assert msg.role == Role.ROLE_AGENT
    assert msg.taskId == "t-1"
    assert hasattr(msg.parts[0], "text")
    assert msg.parts[0].text == "Done"


def test_make_task_status_working():
    """TaskStatus should have the correct state and timestamp."""
    status = make_task_status(TaskState.TASK_STATE_WORKING)
    assert status.state == TaskState.TASK_STATE_WORKING
    assert status.timestamp is not None


def test_make_artifact_contains_data():
    """Artifact should contain a DataPart with the provided data."""
    artifact = make_artifact(
        name="test", description="desc", data={"key": "val"},
    )
    assert artifact.name == "test"
    assert hasattr(artifact.parts[0], "data")
    assert artifact.parts[0].data["key"] == "val"


def test_extract_artifact_data_from_task():
    """extract_artifact_data should pull data from the first artifact."""
    artifact = make_artifact(
        name="r", description="d", data={"total_issues": 5},
    )
    task = Task(
        id="t-1",
        contextId="ctx-1",
        status=make_task_status(TaskState.TASK_STATE_COMPLETED),
        artifacts=[artifact],
    )
    data = extract_artifact_data(task)
    assert data["total_issues"] == 5


def test_extract_artifact_data_empty_task():
    """extract_artifact_data should return empty dict for no artifacts."""
    task = Task(
        id="t-1",
        contextId="ctx-1",
        status=make_task_status(TaskState.TASK_STATE_COMPLETED),
        artifacts=[],
    )
    assert extract_artifact_data(task) == {}


def test_audit_agent_card_structure():
    """Audit AgentCard should have correct name, skills, and capabilities."""
    card = build_audit_agent_card("http://localhost:8000")
    assert card.name == "RAG Pipeline Audit Agent"
    assert len(card.skills) == 1
    assert card.skills[0].id == "audit-documents"
    assert card.capabilities.streaming is True
    assert card.url == "http://localhost:8000/a2a/audit"


def test_correction_agent_card_structure():
    """Correction AgentCard should have correct name and skills."""
    card = build_correction_agent_card("http://localhost:8000")
    assert card.name == "RAG Pipeline Correction Agent"
    assert len(card.skills) == 1
    assert card.skills[0].id == "correct-documents"
    assert card.url == "http://localhost:8000/a2a/correction"
```

**Run tests with:**

```bash
cd rag-pipeline/apps/api && pytest tests/test_a2a_helpers.py -v
```

---

## Done-When Checklist

- [ ] RTK Query `loop-api.ts` exports `useStartLoopMutation`, `useStopLoopMutation`, `useGetLoopStatusQuery`
- [ ] `LoopRound` interface includes `audit_task_id`, `audit_task_state`, `correction_task_id`, `correction_task_state`
- [ ] `/loop/{jobId}` page renders the round timeline with A2A task states
- [ ] `/loop/{jobId}` page shows current loop status with 5-second polling
- [ ] Navigation link to Loop Monitor is added to the layout
- [ ] `pytest tests/test_a2a_helpers.py -v` passes all 9 tests:
  - `test_make_user_message_has_data_part`
  - `test_make_user_message_without_text`
  - `test_make_agent_message_has_text`
  - `test_make_task_status_working`
  - `test_make_artifact_contains_data`
  - `test_extract_artifact_data_from_task`
  - `test_extract_artifact_data_empty_task`
  - `test_audit_agent_card_structure`
  - `test_correction_agent_card_structure`

---

## Full Phase 4 Done-When Checklist

After all 3 subtasks are complete, verify the entire Phase 4:

- [ ] `a2a-sdk` installed and importable (`from a2a.types import Task, Message, AgentCard`)
- [ ] Audit Agent `AgentCard` served at `/a2a/audit/.well-known/agent-card.json`
- [ ] Correction Agent `AgentCard` served at `/a2a/correction/.well-known/agent-card.json`
- [ ] `AuditTaskHandler.on_message()` returns `Task` with `TASK_STATE_COMPLETED` and audit `Artifact`
- [ ] `CorrectionTaskHandler.on_message()` returns `Task` with `TASK_STATE_COMPLETED` and correction `Artifact`
- [ ] Correction Agent graph compiles: receive → classify → plan → apply → save → emit
- [ ] `await run_correction(job_id, round, report_id)` processes issues from audit report
- [ ] Issue classification correctly labels LEGITIMATE vs FALSE_POSITIVE with reasoning
- [ ] Corrected Markdown files are saved; originals backed up with `.roundN.bak.md` suffix
- [ ] `await run_audit_correct_loop(audit_client, correction_client, job_id)` iterates using A2A protocol
- [ ] Loop terminates on convergence (zero issues → approved) or max_rounds (→ escalated)
- [ ] `POST /api/v1/jobs/{id}/start-loop` triggers the A2A loop and returns round summaries
- [ ] `POST /api/v1/jobs/{id}/stop-loop` force-stops and sends to human review
- [ ] `GET /api/v1/jobs/{id}/loop-status` returns current loop state
- [ ] Loop monitor UI shows round timeline with A2A task states
- [ ] `pytest tests/test_a2a_helpers.py -v` passes all tests

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-4-subtask-3-loop-ui-and-tests-summary.md`

The summary report must include:
- **Subtask**: Phase 4, Subtask 3 — Loop Monitoring UI, Tests & Validation
- **Status**: Complete / Partial / Blocked
- **Date**: ISO 8601 date
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next phase (Phase 5) needs to know
- **Verification Results**: Output of Done-When checklist items
