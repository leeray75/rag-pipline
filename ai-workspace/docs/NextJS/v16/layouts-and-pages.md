# Next.js App Router — Layouts & Pages
**Agent Knowledge Reference · Next.js v16+ · Last reviewed: 2026-04-17**

> **Purpose:** Optimized for AI coding agents. Corrects common misconceptions and fills knowledge gaps around file-system routing, layouts, pages, dynamic segments, and navigation in the Next.js App Router. Read before generating any route or layout code.

---

## CRITICAL DEFAULTS — Read First

| Assumption (WRONG) | Correct Behavior |
|---|---|
| Route files can be named anything | Only `page.tsx` and `layout.tsx` are special file conventions that create UI |
| Layouts re-render on navigation | Layouts **preserve state, stay interactive, and do NOT re-render** between navigations |
| Root layout is optional | `app/layout.tsx` is **required** and must include `<html>` and `<body>` tags |
| `params` is a plain object | In v15+, `params` and `searchParams` are **Promises** — must be `await`ed |
| `useSearchParams` works in Server Components | `searchParams` prop is for Server Components; `useSearchParams()` hook is for Client Components only |
| `PageProps` / `LayoutProps` must be imported | These are **globally available** generated types — no import needed |

---

## File-System Routing — Core Rules

Next.js App Router maps the **folder structure** inside `app/` to URL routes.

```
app/
├── page.tsx              →  /
├── layout.tsx            →  root layout (wraps everything)
├── blog/
│   ├── page.tsx          →  /blog
│   ├── layout.tsx        →  layout for /blog and all children
│   └── [slug]/
│       └── page.tsx      →  /blog/:slug  (dynamic)
```

**Two rules:**
1. **Folders** define route segments (URL path parts).
2. **`page.tsx`** makes a segment publicly accessible. A folder without a `page.tsx` is not a route — it can still hold a `layout.tsx`, components, utilities, etc.

---

## Pages

A page is a React component default-exported from `page.tsx` (or `.js`/`.jsx`).

```tsx
// app/page.tsx  →  renders at /
export default function Page() {
  return <h1>Hello Next.js!</h1>
}
```

Pages are **Server Components by default** and can be `async`.

### Props available on a Page

| Prop | Type | Notes |
|---|---|---|
| `params` | `Promise<{ [key: string]: string }>` | Dynamic segment values. Must be awaited. |
| `searchParams` | `Promise<{ [key: string]: string \| string[] \| undefined }>` | URL query params. Must be awaited. Forces dynamic rendering. |

```tsx
// app/blog/[slug]/page.tsx
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>
  searchParams: Promise<{ page?: string }>
}) {
  const { slug } = await params
  const { page } = await searchParams

  const post = await getPost(slug)
  return <article>{post.content}</article>
}
```

> **v15+ Breaking Change:** `params` is now a `Promise`. Do NOT do `{ params: { slug } }` — destructure only after awaiting.

### `PageProps` Helper (TypeScript)

Generated automatically by `next dev` / `next build` / `next typegen`. Globally available — no import.

```tsx
// app/blog/[slug]/page.tsx
export default async function Page(props: PageProps<'/blog/[slug]'>) {
  const { slug } = await props.params
  return <h1>{slug}</h1>
}
```

---

## Layouts

A layout wraps one or more pages (or nested layouts) and **persists across navigations** — it does not unmount or re-render when the user navigates between child routes.

```tsx
// app/layout.tsx  — Root Layout (REQUIRED)
export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <main>{children}</main>
      </body>
    </html>
  )
}
```

### Root Layout Rules
- Must live at `app/layout.tsx`.
- Must return `<html>` and `<body>` tags — no other file should include these.
- Is required — Next.js will error without it.
- Wraps every route in the entire application.

### Nested Layouts

Add a `layout.tsx` inside any route folder to scope a layout to that segment and all its children.

```tsx
// app/blog/layout.tsx  — applies to /blog and /blog/[slug]
export default function BlogLayout({ children }: { children: React.ReactNode }) {
  return (
    <section className="blog-container">
      <BlogSidebar />
      <div>{children}</div>
    </section>
  )
}
```

**Nesting order for `/blog/post-1`:**
```
RootLayout (app/layout.tsx)
  └── BlogLayout (app/blog/layout.tsx)
        └── Page (app/blog/[slug]/page.tsx)
```

### Props available on a Layout

| Prop | Type | Notes |
|---|---|---|
| `children` | `React.ReactNode` | Required. The nested page or layout. |
| `params` | `Promise<{ [key: string]: string }>` | Only present in dynamic route layouts. Must be awaited. |
| Named slots | `React.ReactNode` | Parallel routes (e.g. `@analytics` folder → `analytics` prop) |

```tsx
// app/dashboard/layout.tsx
export default async function Layout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ teamId: string }>
}) {
  const { teamId } = await params
  return <div data-team={teamId}>{children}</div>
}
```

### `LayoutProps` Helper (TypeScript)

```tsx
// app/dashboard/layout.tsx
export default function Layout(props: LayoutProps<'/dashboard'>) {
  return (
    <section>
      {props.children}
      {/* If app/dashboard/@analytics exists: */}
      {/* {props.analytics} */}
    </section>
  )
}
```

---

## Dynamic Route Segments

Wrap a folder name in square brackets to create a dynamic segment.

| Pattern | Example folder | Matches |
|---|---|---|
| Single param | `[slug]` | `/blog/hello-world` |
| Catch-all | `[...slug]` | `/blog/a/b/c` → `{ slug: ['a','b','c'] }` |
| Optional catch-all | `[[...slug]]` | `/blog` and `/blog/a/b` |

```tsx
// app/blog/[slug]/page.tsx
export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params      // ← always await
  const post = await getPost(slug)

  return (
    <div>
      <h1>{post.title}</h1>
      <p>{post.content}</p>
    </div>
  )
}
```

---

## Search Params

### In Server Component Pages — use `searchParams` prop

```tsx
// app/shop/page.tsx
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ category?: string; page?: string }>
}) {
  const { category, page } = await searchParams   // ← always await
  const items = await getItems({ category, page: Number(page ?? 1) })
  return <ItemList items={items} />
}
```

> **Side effect:** Using `searchParams` opts the page into **dynamic rendering** — it cannot be statically generated because query params are only known at request time.

### In Client Components — use `useSearchParams()` hook

```tsx
'use client'
import { useSearchParams } from 'next/navigation'

export default function Filters() {
  const searchParams = useSearchParams()
  const category = searchParams.get('category')
  return <div>Filtering by: {category}</div>
}
```

### Decision Guide

| Scenario | Use |
|---|---|
| Need search params to **fetch data** (pagination, DB filters) | `searchParams` prop on Server Component page |
| Client-only filtering of already-loaded data | `useSearchParams()` hook in Client Component |
| Read params in a callback/event handler without re-render | `new URLSearchParams(window.location.search)` |

---

## Linking Between Pages

Use `<Link>` from `next/link` — **not** `<a>` tags. `<Link>` provides:
- Client-side navigation (no full page reload)
- Automatic prefetching of linked routes on hover/visibility

```tsx
import Link from 'next/link'

// Static link
<Link href="/about">About</Link>

// Dynamic link
<Link href={`/blog/${post.slug}`}>{post.title}</Link>

// With query params
<Link href={{ pathname: '/shop', query: { category: 'shoes' } }}>Shoes</Link>
```

> For programmatic navigation in Client Components, use the `useRouter` hook from `next/navigation` (not `next/router` — that's the Pages Router).

```tsx
'use client'
import { useRouter } from 'next/navigation'

export default function BackButton() {
  const router = useRouter()
  return <button onClick={() => router.push('/dashboard')}>Go to Dashboard</button>
}
```

---

## File Conventions Summary

| File | Purpose | Required? |
|---|---|---|
| `app/layout.tsx` | Root layout — wraps entire app, must have `<html>` + `<body>` | ✅ Yes |
| `app/page.tsx` | Index route `/` | No (but needed to render `/`) |
| `app/[folder]/page.tsx` | Makes a route publicly accessible | No (folder exists but no UI without it) |
| `app/[folder]/layout.tsx` | Scoped layout for a route segment | No |
| `app/[folder]/loading.tsx` | Suspense loading UI for a segment | No |
| `app/[folder]/error.tsx` | Error boundary for a segment | No |
| `app/[folder]/not-found.tsx` | 404 UI for a segment | No |

---

## Folder Structure Example (Blog App)

```
app/
├── layout.tsx              ← Root layout (required)
├── page.tsx                ← Homepage /
├── blog/
│   ├── layout.tsx          ← Blog layout (wraps /blog and /blog/[slug])
│   ├── page.tsx            ← Blog index /blog
│   └── [slug]/
│       └── page.tsx        ← Individual post /blog/:slug
└── about/
    └── page.tsx            ← About page /about
```

---

## Common Mistakes Agent Should Avoid

1. **Forgetting `await` on `params` or `searchParams`** — they are Promises in v15+. Synchronous access returns a Promise object, not the value.
2. **Putting `<html>` or `<body>` in nested layouts** — only the root `app/layout.tsx` should contain these tags.
3. **Using `<a>` instead of `<Link>`** — `<a>` causes a full page reload, losing client-side navigation and prefetching.
4. **Importing `useRouter` from `next/router`** — App Router uses `next/navigation`, not `next/router` (that's Pages Router).
5. **Using `useSearchParams` in a Server Component** — Server Components use the `searchParams` prop; the hook is Client Component only.
6. **Expecting layouts to re-render on navigation** — they don't. State inside a layout persists across child route changes.
7. **Creating a folder without `page.tsx` and expecting a route** — the folder must contain `page.tsx` to be publicly accessible as a URL.
8. **Adding `<html>` / `<body>` to a non-root layout** — nested layouts should only return fragment-level wrappers (e.g. `<section>`, `<div>`).
9. **Importing `PageProps` or `LayoutProps`** — these are globally generated types, no import statement needed.
10. **Using `process.env` secrets inside page props** — pages are Server Components by default, which is fine, but be careful not to pass secret values as props down to Client Components.

---

*Source: https://nextjs.org/docs/app/getting-started/layouts-and-pages (v16.2.2, retrieved 2026-04-17)*