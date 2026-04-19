#!/usr/bin/env bash
set -euo pipefail

PHASE=5
ROOT="rag-pipeline"
ERRORS=0

echo "=== Phase $PHASE Validation ==="
echo "Validating: Human Review Interface & Approval Workflow"
echo ""

check_file() {
  if [ -f "$1" ]; then echo "  ✅ $1"; else echo "  ❌ MISSING: $1"; ERRORS=$((ERRORS + 1)); fi
}

echo "── 1. Source files ──"
check_file "$ROOT/apps/api/src/models/review.py"
check_file "$ROOT/apps/api/src/schemas/review.py"
check_file "$ROOT/apps/api/src/routers/review.py"
echo ""

echo "── 2. Test files ──"
check_file "$ROOT/apps/api/tests/test_review_api.py"
echo ""

echo "── 3. Frontend files ──"
check_file "$ROOT/apps/web/src/store/api/review-api.ts"
check_file "$ROOT/apps/web/src/app/review/[jobId]/page.tsx"
check_file "$ROOT/apps/web/src/app/review/[jobId]/[docId]/page.tsx"
echo ""

echo "── 4. Python import checks ──"
PYTHON=""
if command -v python3 &>/dev/null; then PYTHON=python3;
elif command -v python &>/dev/null; then PYTHON=python; fi

if [ -n "$PYTHON" ] && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null

  for module in \
    "src.models.review" \
    "src.schemas.review" \
    "src.routers.review"; do
    if $PYTHON -c "import $module" 2>/dev/null; then
      echo "  ✅ import $module"
    else
      echo "  ❌ FAILED: import $module"; ERRORS=$((ERRORS + 1))
    fi
  done

  echo ""
  echo "── 5. Export checks ──"
  if $PYTHON -c "from src.models.review import ReviewDecision, ReviewComment" 2>/dev/null; then
    echo "  ✅ review model exports"
  else
    echo "  ❌ FAILED: review model exports"; ERRORS=$((ERRORS + 1))
  fi

  if $PYTHON -c "from src.schemas.review import ReviewDecisionCreate, ReviewDecisionResponse, ReviewCommentCreate, ReviewCommentResponse, BatchApproveRequest, ReviewSummary" 2>/dev/null; then
    echo "  ✅ review schema exports"
  else
    echo "  ❌ FAILED: review schema exports"; ERRORS=$((ERRORS + 1))
  fi

  popd > /dev/null
fi
echo ""

echo "── 6. Type checking (mypy) ──"
if [ -n "$PYTHON" ] && command -v mypy &>/dev/null && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null
  if mypy src/models/review.py src/schemas/review.py src/routers/review.py --ignore-missing-imports --no-error-summary 2>/dev/null; then
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

echo "── 8. Run Phase 5 tests ──"
if [ -n "$PYTHON" ] && command -v pytest &>/dev/null && [ -d "$ROOT/apps/api" ]; then
  pushd "$ROOT/apps/api" > /dev/null
  if pytest tests/test_review_api.py -v --tb=short 2>/dev/null; then
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
  if grep -q "review.router" "$ROOT/apps/api/src/main.py"; then
    echo "  ✅ review router registered in main.py"
  else
    echo "  ❌ review router not registered in main.py"; ERRORS=$((ERRORS + 1))
  fi
fi
echo ""

echo "── 10. Database migration check ──"
if [ -d "$ROOT/apps/api/alembic/versions" ]; then
  if ls "$ROOT/apps/api/alembic/versions/"*review* &>/dev/null 2>&1; then
    echo "  ✅ Review migration file exists"
  else
    echo "  ⚠️  No migration file with 'review' in name found (may use different naming)"
  fi
fi
echo ""

echo "════════════════════════════════════════"
if [ $ERRORS -eq 0 ]; then echo "✅ Phase $PHASE validation PASSED"; exit 0
else echo "❌ Phase $PHASE validation FAILED — $ERRORS error(s)"; exit 1; fi
