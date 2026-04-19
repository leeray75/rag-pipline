#!/usr/bin/env bash
set -euo pipefail

PHASE=3
ROOT="rag-pipeline"
ERRORS=0

echo "=== Phase $PHASE Validation ==="
echo "Validating: Audit Agent — Schema Validation & Report Generation"
echo ""

check_file() {
  if [ -f "$1" ]; then echo "  ✅ $1"; else echo "  ❌ MISSING: $1"; ERRORS=$((ERRORS + 1)); fi
}

# ─── 1. Check files exist ─────────────────────────────────────────
echo "── 1. Source files ──"
check_file "$ROOT/apps/api/src/agents/schema_validator.py"
check_file "$ROOT/apps/api/src/agents/audit_state.py"
check_file "$ROOT/apps/api/src/agents/audit_agent.py"
check_file "$ROOT/apps/api/src/routers/audit.py"
echo ""

echo "── 2. Test files ──"
check_file "$ROOT/apps/api/tests/test_schema_validator.py"
echo ""

echo "── 3. Frontend files ──"
check_file "$ROOT/apps/web/src/store/api/audit-api.ts"
check_file "$ROOT/apps/web/src/app/audit/[jobId]/page.tsx"
echo ""

# ─── 2. Python imports ────────────────────────────────────────────
echo "── 4. Python import checks ──"
PYTHON=""
if command -v python3 &>/dev/null; then PYTHON=python3;
elif command -v python &>/dev/null; then PYTHON=python; fi

if [ -n "$PYTHON" ] && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null

  for module in \
    "src.agents.schema_validator" \
    "src.agents.audit_state" \
    "src.agents.audit_agent" \
    "src.routers.audit"; do
    if $PYTHON -c "import $module" 2>/dev/null; then
      echo "  ✅ import $module"
    else
      echo "  ❌ FAILED: import $module"
      ERRORS=$((ERRORS + 1))
    fi
  done

  echo ""
  echo "── 5. Export checks ──"
  if $PYTHON -c "from src.agents.schema_validator import SchemaIssue, SchemaValidationResult, validate_document" 2>/dev/null; then
    echo "  ✅ schema_validator exports"
  else
    echo "  ❌ FAILED: schema_validator exports"
    ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.agents.audit_state import AuditDocInfo, AuditState" 2>/dev/null; then
    echo "  ✅ audit_state exports"
  else
    echo "  ❌ FAILED: audit_state exports"
    ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.agents.audit_agent import build_audit_graph, run_audit" 2>/dev/null; then
    echo "  ✅ audit_agent exports"
  else
    echo "  ❌ FAILED: audit_agent exports"
    ERRORS=$((ERRORS + 1))
  fi

  popd > /dev/null
fi
echo ""

# ─── 3. Type checking ─────────────────────────────────────────────
echo "── 6. Type checking (mypy) ──"
if [ -n "$PYTHON" ] && command -v mypy &>/dev/null && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null
  if mypy src/agents/ src/routers/audit.py --ignore-missing-imports --no-error-summary 2>/dev/null; then
    echo "  ✅ mypy passed"
  else
    echo "  ❌ mypy found type errors"
    ERRORS=$((ERRORS + 1))
  fi
  popd > /dev/null
else
  echo "  ⚠️  mypy not available — skipping"
fi
echo ""

# ─── 4. TypeScript compilation ────────────────────────────────────
echo "── 7. TypeScript compilation ──"
if command -v npx &>/dev/null && [ -d "$ROOT/apps/web" ]; then
  pushd "$ROOT/apps/web" > /dev/null
  if npx tsc --noEmit 2>/dev/null; then
    echo "  ✅ TypeScript compilation passed"
  else
    echo "  ❌ TypeScript compilation failed"
    ERRORS=$((ERRORS + 1))
  fi
  popd > /dev/null
else
  echo "  ⚠️  npx not available — skipping"
fi
echo ""

# ─── 5. Run tests ─────────────────────────────────────────────────
echo "── 8. Run Phase 3 tests ──"
if [ -n "$PYTHON" ] && command -v pytest &>/dev/null && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null
  if pytest tests/test_schema_validator.py -v --tb=short 2>/dev/null; then
    echo "  ✅ Tests passed"
  else
    echo "  ❌ Tests failed"
    ERRORS=$((ERRORS + 1))
  fi
  popd > /dev/null
else
  echo "  ⚠️  pytest not available — skipping"
fi
echo ""

# ─── 6. Router registration ──────────────────────────────────────
echo "── 9. Router registration ──"
if [ -f "$ROOT/apps/api/src/main.py" ]; then
  if grep -q "audit.router" "$ROOT/apps/api/src/main.py"; then
    echo "  ✅ audit router registered in main.py"
  else
    echo "  ❌ audit router not registered in main.py"
    ERRORS=$((ERRORS + 1))
  fi
fi
echo ""

# ─── Summary ──────────────────────────────────────────────────────
echo "════════════════════════════════════════"
if [ $ERRORS -eq 0 ]; then
  echo "✅ Phase $PHASE validation PASSED"
  exit 0
else
  echo "❌ Phase $PHASE validation FAILED — $ERRORS error(s)"
  exit 1
fi
