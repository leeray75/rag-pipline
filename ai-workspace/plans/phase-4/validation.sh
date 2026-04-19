#!/usr/bin/env bash
set -euo pipefail

PHASE=4
ROOT="rag-pipeline"
ERRORS=0

echo "=== Phase $PHASE Validation ==="
echo "Validating: Correction Agent & Iterative Audit Loop (A2A)"
echo ""

check_file() {
  if [ -f "$1" ]; then echo "  ✅ $1"; else echo "  ❌ MISSING: $1"; ERRORS=$((ERRORS + 1)); fi
}

echo "── 1. Source files ──"
check_file "$ROOT/apps/api/src/agents/a2a_messages.py"
check_file "$ROOT/apps/api/src/agents/correction_state.py"
check_file "$ROOT/apps/api/src/agents/correction_agent.py"
check_file "$ROOT/apps/api/src/agents/loop_orchestrator.py"
check_file "$ROOT/apps/api/src/routers/loop.py"
echo ""

echo "── 2. Test files ──"
check_file "$ROOT/apps/api/tests/test_a2a_messages.py"
echo ""

echo "── 3. Frontend files ──"
check_file "$ROOT/apps/web/src/store/api/loop-api.ts"
check_file "$ROOT/apps/web/src/app/loop/[jobId]/page.tsx"
echo ""

echo "── 4. Python import checks ──"
PYTHON=""
if command -v python3 &>/dev/null; then PYTHON=python3;
elif command -v python &>/dev/null; then PYTHON=python; fi

if [ -n "$PYTHON" ] && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null

  for module in \
    "src.agents.a2a_messages" \
    "src.agents.correction_state" \
    "src.agents.correction_agent" \
    "src.agents.loop_orchestrator" \
    "src.routers.loop"; do
    if $PYTHON -c "import $module" 2>/dev/null; then
      echo "  ✅ import $module"
    else
      echo "  ❌ FAILED: import $module"
      ERRORS=$((ERRORS + 1))
    fi
  done

  echo ""
  echo "── 5. Export checks ──"
  if $PYTHON -c "from src.agents.a2a_messages import A2AAction, A2AMessage, A2AMessageBus, message_bus" 2>/dev/null; then
    echo "  ✅ a2a_messages exports"
  else
    echo "  ❌ FAILED: a2a_messages exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.agents.correction_state import CorrectionIssue, CorrectionDocInfo, CorrectionState" 2>/dev/null; then
    echo "  ✅ correction_state exports"
  else
    echo "  ❌ FAILED: correction_state exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.agents.correction_agent import build_correction_graph, run_correction" 2>/dev/null; then
    echo "  ✅ correction_agent exports"
  else
    echo "  ❌ FAILED: correction_agent exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.agents.loop_orchestrator import run_audit_correct_loop, DEFAULT_MAX_ROUNDS" 2>/dev/null; then
    echo "  ✅ loop_orchestrator exports"
  else
    echo "  ❌ FAILED: loop_orchestrator exports"; ERRORS=$((ERRORS + 1))
  fi

  popd > /dev/null
fi
echo ""

echo "── 6. Type checking (mypy) ──"
if [ -n "$PYTHON" ] && command -v mypy &>/dev/null && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null
  if mypy src/agents/a2a_messages.py src/agents/correction_state.py src/agents/correction_agent.py src/agents/loop_orchestrator.py src/routers/loop.py --ignore-missing-imports --no-error-summary 2>/dev/null; then
    echo "  ✅ mypy passed"
  else
    echo "  ❌ mypy found type errors"; ERRORS=$((ERRORS + 1))
  fi
  popd > /dev/null
else
  echo "  ⚠️  mypy not available — skipping"
fi
echo ""

echo "── 7. TypeScript compilation ──"
if command -v npx &>/dev/null && [ -d "$ROOT/apps/web" ]; then
  pushd "$ROOT/apps/web" > /dev/null
  if npx tsc --noEmit 2>/dev/null; then
    echo "  ✅ TypeScript compilation passed"
  else
    echo "  ❌ TypeScript compilation failed"; ERRORS=$((ERRORS + 1))
  fi
  popd > /dev/null
else
  echo "  ⚠️  npx not available — skipping"
fi
echo ""

echo "── 8. Run Phase 4 tests ──"
if [ -n "$PYTHON" ] && command -v pytest &>/dev/null && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null
  if pytest tests/test_a2a_messages.py -v --tb=short 2>/dev/null; then
    echo "  ✅ Tests passed"
  else
    echo "  ❌ Tests failed"; ERRORS=$((ERRORS + 1))
  fi
  popd > /dev/null
else
  echo "  ⚠️  pytest not available — skipping"
fi
echo ""

echo "── 9. Router registration ──"
if [ -f "$ROOT/apps/api/src/main.py" ]; then
  if grep -q "loop.router" "$ROOT/apps/api/src/main.py"; then
    echo "  ✅ loop router registered in main.py"
  else
    echo "  ❌ loop router not registered in main.py"; ERRORS=$((ERRORS + 1))
  fi
fi
echo ""

echo "════════════════════════════════════════"
if [ $ERRORS -eq 0 ]; then echo "✅ Phase $PHASE validation PASSED"; exit 0
else echo "❌ Phase $PHASE validation FAILED — $ERRORS error(s)"; exit 1; fi
