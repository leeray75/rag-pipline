# Next.js App Router — Server & Client Components
**Agent Knowledge Reference · Next.js v16+ · Last reviewed: 2026-04-17**

> **Purpose:** This document is optimized for AI coding agents. It corrects common LLM misconceptions and fills knowledge gaps introduced in Next.js App Router (v13+), with behavior current as of v16. Read this before generating any Next.js App Router component code.

---

## CRITICAL DEFAULTS — Read First

| Assumption (WRONG) | Correct Behavior |
|---|---|
| Components are Client Components by default | **All** layouts and pages are **Server Components by default** |
| `useState`/`useEffect` work in any component | Only work in Client Components (marked `'use client'`) |
| `'use client'` must be added to every interactive child | Adding it to a parent makes **all its imports and children** client-side automatically |
| Context providers can live in Server Components | React context is **not supported** in Server Components |
| `process.env.MY_SECRET` is safe anywhere | Only `NEXT_PUBLIC_` prefixed env vars go to the client; unprefixed vars become **empty string** on client |

---

## Decision Tree: Server vs Client Component

```
Does the component need any of these?
  - onClick, onChange, or other event handlers
  - useState, useReducer, useEffect, useLayoutEffect
  - Browser APIs (localStorage, window, navigator, etc.)
  - Custom hooks that use any of the above
  → YES → Client Component ('use client')

Does the component need any of these?
  - Fetch data from a database or private API
  - Use secrets / API keys
  - Minimize JS sent to browser
  - Improve FCP / streaming
  → YES → Server Component (default, no directive needed)
```

**Rule of thumb:** Keep as much as possible as Server Components. Push `'use client'` as far down the component tree as possible to the smallest interactive leaf nodes.

---

## Directives

### `'use client'`
- Place at the **very top of the file**, above all imports.
- Declares a **boundary** between the server and client module graphs.
- Everything imported by that file is automatically included in the client bundle — you do not need to repeat the directive in child files.
- Does **not** mean the component only runs on the client — it still prerenders on the server for the initial HTML load. It means the component is hydrated and can run interactively on the client.

```tsx
// app/ui/like-button.tsx
'use client'                    // ← top of file, above imports

import { useState } from 'react'

export default function LikeButton({ likes }: { likes: number }) {
  const [count, setCount] = useState(likes)
  return <button onClick={() => setCount(c => c + 1)}>{count} likes</button>
}
```

### `'use server'`
- Used inside **Server Actions** (async functions called from the client), not for marking Server Components (they need no directive).
- Out of scope for this doc — see the Server Actions reference.

---

## Rendering Pipeline (What Actually Happens)

### Initial Request (SSR)
1. Server renders all Server Components → produces **RSC Payload** (compact binary format).
2. RSC Payload + Client Component shells → rendered to **HTML**.
3. Browser receives HTML → instantly shows non-interactive page.
4. Browser downloads JS → **hydrates** Client Components (attaches event handlers).

### Subsequent Navigations (SPA-style)
- RSC Payload is **prefetched and cached**; no full page reload.
- Client Components render **entirely on the client** — no server HTML for subsequent nav.
- Server Components still execute on the server and their output is streamed as RSC Payload.

### RSC Payload Contains
- Rendered output of Server Components
- Placeholders + JS file references for Client Components
- Props passed from Server → Client Components

---

## Composing Server and Client Components

### ✅ Correct: Pass Server Components as `children` or props to Client Components

This is the primary pattern for interleaving. The Server Component renders on the server; the Client Component receives it as an already-resolved prop.

```tsx
// app/ui/modal.tsx — Client Component
'use client'
export default function Modal({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button onClick={() => setOpen(true)}>Open</button>
      {open && <div>{children}</div>}
    </>
  )
}
```

```tsx
// app/page.tsx — Server Component (no directive)
import Modal from './ui/modal'
import Cart from './ui/cart'   // Cart is also a Server Component

export default function Page() {
  return (
    <Modal>
      <Cart />     {/* Server Component passed as children prop — valid! */}
    </Modal>
  )
}
```

### ❌ Wrong: Importing a Server Component directly inside a Client Component file

```tsx
'use client'
import Cart from './cart'     // ❌ If Cart is a Server Component, this breaks the boundary
                              // Cart gets pulled into the client bundle
```

**Fix:** Pass it in via props/children from a Server Component parent (see above).

---

## Props From Server → Client: Serialization Requirement

Props passed across the Server→Client boundary **must be serializable** by React. This means:

- ✅ Strings, numbers, booleans, `null`, `undefined`
- ✅ Plain objects and arrays of serializable values
- ✅ `Date` objects, `URL`, `TypedArray`, `ArrayBuffer`
- ✅ `BigInt`
- ❌ Functions / closures (unless wrapped as a Server Action)
- ❌ Class instances
- ❌ DOM nodes, React elements that contain non-serializable values

---

## Reducing Client Bundle Size

**Anti-pattern:** Marking large layout/wrapper components as `'use client'` because one child needs it.

**Pattern:** Extract only the interactive part into its own `'use client'` file.

```tsx
// app/layout.tsx — stays a Server Component
import Search from './search'  // Client Component (small, interactive)
import Logo from './logo'      // Server Component (static)

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <nav>
        <Logo />
        <Search />   {/* Only Search is client-side */}
      </nav>
      <main>{children}</main>
    </>
  )
}
```

---

## Context Providers

React context (`createContext`, `useContext`) is **not available** in Server Components.

**Pattern:** Wrap context providers in a `'use client'` component, then import it into a Server Component layout.

```tsx
// app/providers/theme-provider.tsx
'use client'
import { createContext } from 'react'
export const ThemeContext = createContext({})

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  return <ThemeContext.Provider value="dark">{children}</ThemeContext.Provider>
}
```

```tsx
// app/layout.tsx — Server Component
import ThemeProvider from './providers/theme-provider'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>
        <ThemeProvider>  {/* Wrap only what needs it, not the whole document */}
          {children}
        </ThemeProvider>
      </body>
    </html>
  )
}
```

> **Optimization note:** Place providers as **deep** in the tree as possible. Wrapping the entire `<html>` tag prevents Next.js from statically optimizing outer server-rendered content.

---

## Third-Party Components Without `'use client'`

Many npm packages use client-only APIs but haven't added `'use client'` to their source. Importing them into a Server Component will throw an error.

**Fix:** Create a thin wrapper file:

```tsx
// app/ui/carousel-wrapper.tsx
'use client'
export { Carousel } from 'acme-carousel'   // re-export with client boundary
```

```tsx
// app/page.tsx — Server Component
import Carousel from './ui/carousel-wrapper'  // ✅ safe to use now

export default function Page() {
  return <Carousel />
}
```

---

## Preventing Secret Leakage (Environment Poisoning)

### How Next.js handles env vars on the client
- `NEXT_PUBLIC_*` → included in client bundle ✅
- All other `process.env.*` → **replaced with empty string `""`** at build time on the client (no error thrown, silent failure)

### Use `server-only` package to enforce server boundary at build time

```bash
npm install server-only
```

```ts
// lib/data.ts
import 'server-only'    // ← build-time error if imported in a Client Component

export async function getData() {
  const res = await fetch('https://api.example.com/data', {
    headers: { authorization: process.env.API_KEY }  // safe — server-only enforced
  })
  return res.json()
}
```

Counterpart: `client-only` package marks modules that should never run on the server (e.g., code accessing `window`).

> Next.js handles these imports internally for better error messages. The NPM package contents themselves are not used at runtime by Next.js — the import is purely a signal.

---

## Async Server Components

Server Components can be `async` functions. This is **not** available in Client Components.

```tsx
// app/page.tsx
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params               // params is now a Promise in v15+
  const post = await getPost(id)            // direct async/await, no useEffect
  return <h1>{post.title}</h1>
}
```

> **v15+ Change:** `params` and `searchParams` in pages/layouts are now **Promises** and must be awaited. Do not destructure them synchronously.

---

## Streaming with `use` API (Server → Client Data Streaming)

Instead of awaiting data in a Server Component and passing it as props, you can stream a Promise directly to a Client Component:

```tsx
// app/page.tsx — Server Component
import { use } from 'react'
import Posts from './posts'

export default function Page() {
  const postsPromise = getPosts()       // do NOT await
  return <Posts posts={postsPromise} />  // pass the Promise as a prop
}
```

```tsx
// app/posts.tsx — Client Component
'use client'
import { use } from 'react'

export default function Posts({ posts }: { posts: Promise<Post[]> }) {
  const resolvedPosts = use(posts)      // React suspends until resolved
  return resolvedPosts.map(p => <div key={p.id}>{p.title}</div>)
}
```

Pair with `<Suspense>` for loading states.

---

## Quick Reference Cheat Sheet

```
Server Component (default)          Client Component ('use client')
─────────────────────────────────   ──────────────────────────────────
✅ async/await at component level   ✅ useState, useReducer
✅ Direct DB / API access           ✅ useEffect, useLayoutEffect
✅ Server-only env vars             ✅ onClick, onChange, event handlers
✅ Reduce JS bundle                 ✅ Browser APIs (window, localStorage)
✅ Import other Server Components   ✅ Custom hooks using any of the above
❌ useState / useEffect             ❌ async component function
❌ Event handlers                   ❌ Direct DB access (use server actions)
❌ Browser APIs                     ❌ Server-only env vars (silently empty)
❌ React context (create/consume)   ✅ React context (consume via provider)
```

---

## Common Mistakes Agent Should Avoid

1. **Adding `'use client'` to every component** — only add to components that actually need it.
2. **Importing a Server Component inside a `'use client'` file** — pass via props/children instead.
3. **Using `useEffect` to fetch data** — use `async` Server Components with direct `await` instead.
4. **Accessing `process.env.SECRET` in a Client Component** — it will silently be `""`.
5. **Wrapping the entire app in a single context provider inside a Client Component** — nest providers only as deep as needed.
6. **Not awaiting `params`** — in Next.js v15+, `params` and `searchParams` are Promises.
7. **Using React context in a Server Component** — wrap context in a `'use client'` provider component.
8. **Assuming third-party packages are client-safe** — wrap missing-`'use client'` packages in your own client wrapper.

---

*Source: https://nextjs.org/docs/app/getting-started/server-and-client-components (v16.2.4, retrieved 2026-04-17)*