#!/usr/bin/env bash
set -euo pipefail

PHASE=3
COMMIT_MSG="feat(phase-$PHASE):"
ROOT="rag-pipeline"

echo "=== Rolling back Phase $PHASE ==="
echo "Phase: Audit Agent — Schema Validation & Report Generation"
echo ""

if ! git rev-parse --is-inside-work-tree &>/dev/null; then
  echo "❌ Not inside a git repository."; exit 1
fi

PHASE_COMMITS=$(git log --oneline --grep="$COMMIT_MSG" --format="%H %s" 2>/dev/null || true)

if [ -z "$PHASE_COMMITS" ]; then
  echo "⚠️  No commits found matching '$COMMIT_MSG'. File-based rollback..."

  FILES_TO_REMOVE=(
    "$ROOT/apps/api/src/agents/schema_validator.py"
    "$ROOT/apps/api/src/agents/audit_state.py"
    "$ROOT/apps/api/src/agents/audit_agent.py"
    "$ROOT/apps/api/src/routers/audit.py"
    "$ROOT/apps/api/tests/test_schema_validator.py"
    "$ROOT/apps/web/src/store/api/audit-api.ts"
  )

  DIRS_TO_REMOVE=(
    "$ROOT/apps/web/src/app/audit"
  )

  for file in "${FILES_TO_REMOVE[@]}"; do
    if [ -f "$file" ]; then rm -f "$file"; echo "  🗑️  Removed $file"; fi
  done
  for dir in "${DIRS_TO_REMOVE[@]}"; do
    if [ -d "$dir" ]; then rm -rf "$dir"; echo "  🗑️  Removed $dir/"; fi
  done

  echo ""; echo "✅ File-based rollback complete."; exit 0
fi

echo "Found Phase $PHASE commits:"
echo "$PHASE_COMMITS" | head -5 | sed 's/^/  /'

FIRST_PHASE_COMMIT=$(echo "$PHASE_COMMITS" | tail -1 | awk '{print $1}')
PRE_PHASE_COMMIT=$(git rev-parse "${FIRST_PHASE_COMMIT}^" 2>/dev/null || true)

if [ -z "$PRE_PHASE_COMMIT" ]; then echo "❌ Cannot find parent commit."; exit 1; fi

echo "Rolling back to: $(git log --oneline -1 "$PRE_PHASE_COMMIT")"
read -p "⚠️  Continue? [y/N] " -n 1 -r; echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then echo "Cancelled."; exit 0; fi

SAFETY_BRANCH="backup/pre-rollback-phase-$PHASE-$(date +%Y%m%d-%H%M%S)"
git branch "$SAFETY_BRANCH"
git reset --hard "$PRE_PHASE_COMMIT"
echo "✅ Phase $PHASE rolled back. Safety branch: $SAFETY_BRANCH"
