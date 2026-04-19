#!/usr/bin/env bash
set -euo pipefail

PHASE=1
COMMIT_MSG="feat(phase-$PHASE):"
ROOT="rag-pipeline"

echo "=== Rolling back Phase $PHASE ==="
echo "Phase: Foundation — Mono-Repo, Infrastructure & Core APIs"
echo ""

# ─── Safety check ─────────────────────────────────────────────────
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
  echo "❌ Not inside a git repository. Cannot rollback."
  exit 1
fi

# ─── Find the commit before this phase ────────────────────────────
echo "── Searching for Phase $PHASE commits ──"
PHASE_COMMITS=$(git log --oneline --grep="$COMMIT_MSG" --format="%H %s" 2>/dev/null || true)

if [ -z "$PHASE_COMMITS" ]; then
  echo "⚠️  No commits found matching '$COMMIT_MSG'"
  echo ""
  echo "Attempting file-based rollback instead..."
  echo ""

  # ─── File-based rollback: remove Phase 1 files ──────────────────
  echo "── Removing Phase 1 files ──"

  FILES_TO_REMOVE=(
    "$ROOT/package.json"
    "$ROOT/pnpm-workspace.yaml"
    "$ROOT/turbo.json"
    "$ROOT/.gitignore"
    "$ROOT/apps/api/pyproject.toml"
    "$ROOT/apps/api/Dockerfile"
    "$ROOT/apps/api/alembic.ini"
    "$ROOT/apps/web/Dockerfile"
    "$ROOT/apps/web/next.config.js"
    "$ROOT/apps/web/.env.local"
    "$ROOT/infra/docker-compose.yml"
    "$ROOT/infra/docker-compose.dev.yml"
    "$ROOT/.github/workflows/ci.yml"
  )

  DIRS_TO_REMOVE=(
    "$ROOT/apps/api/src"
    "$ROOT/apps/api/tests"
    "$ROOT/apps/api/alembic"
    "$ROOT/apps/web/src"
    "$ROOT/node_modules"
    "$ROOT/apps/web/node_modules"
    "$ROOT/.turbo"
  )

  for file in "${FILES_TO_REMOVE[@]}"; do
    if [ -f "$file" ]; then
      rm -f "$file"
      echo "  🗑️  Removed $file"
    fi
  done

  for dir in "${DIRS_TO_REMOVE[@]}"; do
    if [ -d "$dir" ]; then
      rm -rf "$dir"
      echo "  🗑️  Removed $dir/"
    fi
  done

  # Clean up empty directories
  for dir in "$ROOT/apps/api" "$ROOT/apps/web" "$ROOT/apps" "$ROOT/infra" "$ROOT/.github/workflows" "$ROOT/.github"; do
    if [ -d "$dir" ] && [ -z "$(ls -A "$dir" 2>/dev/null)" ]; then
      rmdir "$dir" 2>/dev/null || true
      echo "  🗑️  Removed empty $dir/"
    fi
  done

  echo ""
  echo "✅ File-based rollback complete."
  echo "   Run 'git status' to review changes, then commit if satisfied."
  exit 0
fi

echo "Found Phase $PHASE commits:"
echo "$PHASE_COMMITS" | head -5 | sed 's/^/  /'
echo ""

# ─── Get the earliest phase commit ───────────────────────────────
FIRST_PHASE_COMMIT=$(echo "$PHASE_COMMITS" | tail -1 | awk '{print $1}')
PRE_PHASE_COMMIT=$(git rev-parse "${FIRST_PHASE_COMMIT}^" 2>/dev/null || true)

if [ -z "$PRE_PHASE_COMMIT" ]; then
  echo "❌ Cannot find parent commit before Phase $PHASE."
  echo "   The phase commit may be the initial commit."
  exit 1
fi

echo "── Rollback target ──"
echo "  First Phase $PHASE commit: $(echo "$PHASE_COMMITS" | tail -1)"
echo "  Rolling back to:           $(git log --oneline -1 "$PRE_PHASE_COMMIT")"
echo ""

# ─── Confirm rollback ─────────────────────────────────────────────
read -p "⚠️  This will reset to before Phase $PHASE. Continue? [y/N] " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Rollback cancelled."
  exit 0
fi

# ─── Create safety branch ────────────────────────────────────────
SAFETY_BRANCH="backup/pre-rollback-phase-$PHASE-$(date +%Y%m%d-%H%M%S)"
git branch "$SAFETY_BRANCH"
echo "  📌 Safety branch created: $SAFETY_BRANCH"

# ─── Perform rollback ────────────────────────────────────────────
git reset --hard "$PRE_PHASE_COMMIT"
echo ""
echo "✅ Phase $PHASE rolled back successfully."
echo "   Current HEAD: $(git log --oneline -1)"
echo "   Safety branch: $SAFETY_BRANCH (contains pre-rollback state)"
echo ""
echo "   To undo this rollback: git reset --hard $SAFETY_BRANCH"
