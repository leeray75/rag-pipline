# Phase 1, Subtask 3 — Next.js Frontend Scaffold + Shared Pydantic Schemas

> **Subtask**: Phase 1, Subtask 3 — Next.js Frontend Scaffold + Shared Pydantic Schemas
> **Status**: Complete
> **Date**: 2026-04-15

---

## Summary

Successfully implemented Phase 1, Subtask 3, which involved scaffolding a Next.js frontend application at `apps/web/` with shadcn/ui, Redux Toolkit, and RTK Query, along with creating the shared Pydantic schemas in the API backend at `apps/api/src/schemas/`.

---

## Files Created/Modified

### Next.js Frontend (apps/web/)

| # | File Path | Action | Description |
|---|-----------|--------|-------------|
| 1 | `apps/web/` | Created | Next.js 16.2.3 app scaffold via `create-next-app@latest` |
| 2 | `apps/web/package.json` | Created/Modified | Next.js, Redux Toolkit, Vitest dependencies |
| 3 | `apps/web/src/store/store.ts` | Created | Redux store configuration with RTK Query |
| 4 | `apps/web/src/store/hooks.ts` | Created | TypeScript-typed Redux hooks (useAppDispatch, useAppSelector) |
| 5 | `apps/web/src/store/provider.tsx` | Created | StoreProvider component wrapping the app |
| 6 | `apps/web/src/store/api/api-slice.ts` | Created | RTK Query base API configuration |
| 7 | `apps/web/src/app/layout.tsx` | Modified | Added StoreProvider wrapper and metadata |
| 8 | `apps/web/src/app/page.tsx` | Modified | Placeholder home page with 3 dashboard cards |
| 9 | `apps/web/.env.local` | Created | Environment variable for API URL |
| 10 | `apps/web/src/components/ui/button.tsx` | Created | shadcn/ui button component |
| 11 | `apps/web/src/components/ui/card.tsx` | Created | shadcn/ui card component |
| 12 | `apps/web/src/components/ui/input.tsx` | Created | shadcn/ui input component |
| 13 | `apps/web/src/components/ui/badge.tsx` | Created | shadcn/ui badge component |
| 14 | `apps/web/src/components/ui/tabs.tsx` | Created | shadcn/ui tabs component |
| 15 | `apps/web/src/components/ui/separator.tsx` | Created | shadcn/ui separator component |
| 16 | `apps/web/src/components/ui/` | Modified | shadcn/ui configuration files |
| 17 | `apps/web/src/lib/utils.ts` | Created | shadcn/ui utility functions |

### Python API Schemas (apps/api/src/schemas/)

| # | File Path | Action | Description |
|---|-----------|--------|-------------|
| 18 | `apps/api/src/schemas/job.py` | Created | Pydantic schemas: JobCreate, JobResponse, JobStatusResponse |
| 19 | `apps/api/src/schemas/document.py` | Created | Pydantic schema: DocumentResponse |
| 20 | `apps/api/src/schemas/__init__.py` | Modified | Export all schema classes |

---

## Key Decisions

1. **shadcn/ui Initialization**: The new shadcn CLI (v4.x) uses presets instead of interactive prompts. Used the default `nova` preset which is compatible with the New York style aesthetic. Component library was set to Radix.

2. **shadcn Components**: Added components individually using `npx shadcn@latest add [component]` for button, card, input, badge, tabs, and separator as specified.

3. **RTK Query Tag Types**: Configured tag types as `["Jobs", "Documents", "AuditReports"]` to support future API caching strategies.

4. **Python Environment**: Created a Python virtual environment using `python3 -m venv .venv` to install pydantic for testing, since the system Python is externally managed (Homebrew).

---

## Issues Encountered

1. **Next.js Typegen Error**: During create-next-app initialization, encountered an `ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL` error related to `next typegen`. This was non-fatal and the app was created successfully.

2. **shadcn UI Preset**: The new shadcn CLI doesn't support the `--style` and `--base-color` flags that were documented in the subtask. The init command automatically uses `nova` preset which provides a clean, minimal aesthetic.

3. **Python Module Import Error**: The pydantic module was not installed in the system Python. Created a virtual environment to install pydantic for testing the schema imports.

---

## Dependencies for Next Subtask

The Next.js frontend and API backend are now properly scaffolded. The next subtask should be able to:

1. **Start the Next.js dev server** at `http://localhost:3000` using `pnpm dev` from `apps/web/`
2. **Start the FastAPI backend** using the configured dev server from `apps/api/`
3. **Connect the frontend to the backend** using the configured `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`

---

## Verification Results

### ✅ Done-When Checklist

| # | Checklist Item | Status |
|---|----------------|--------|
| 1 | `apps/web/package.json` exists with Next.js, Redux Toolkit, and Vitest dependencies | ✅ Complete |
| 2 | `pnpm dev` starts Next.js at `http://localhost:3000` (from `apps/web/`) | ✅ Running |
| 3 | Dashboard displays 3 placeholder cards (Ingestion Jobs, Documents, Vector Collections) | ✅ Complete |
| 4 | shadcn/ui components are installed (button, card, input, badge, tabs, separator) | ✅ Complete |
| 5 | Redux store is configured with RTK Query base API slice | ✅ Complete |
| 6 | `StoreProvider` wraps the app in `layout.tsx` | ✅ Complete |
| 7 | `.env.local` sets `NEXT_PUBLIC_API_URL` | ✅ Complete |
| 8 | `python -c "from src.schemas import JobCreate, JobResponse, JobStatusResponse, DocumentResponse"` succeeds (from `apps/api/`) | ✅ Complete |
| 9 | All schema exports are present in `src/schemas/__init__.py` | ✅ Complete |

---

## Notes

- The Next.js dev server is currently running and accessible at `http://localhost:3000`
- The Python schema imports have been verified to work correctly
- All 20 files have been created/modified as specified in the subtask
- The Next.js app uses:
  - TypeScript
  - TailwindCSS v4
  - ESLint
  - App Router
  - src-dir configuration
  - `@/*` import alias
