# Next.js Proxy (formerly Middleware)
**Agent Knowledge Reference · Next.js v16+ · Last reviewed: 2026-04-17**

> **Purpose:** Optimized for AI coding agents. Most LLM training data knows this feature as `middleware.ts`. In Next.js 16, it was **deprecated and renamed to `proxy.ts`**. This guide covers everything needed to correctly implement Proxy, avoid the legacy patterns, and migrate existing middleware code.

---

## CRITICAL: Middleware → Proxy Rename (v16)

| What changed | Detail |
|---|---|
| **File name** | `middleware.ts` → `proxy.ts` |
| **Export name** | `export function middleware()` → `export function proxy()` |
| **`middleware` file** | Still runs but is **deprecated** — triggers a build warning |
| **Runtime** | Now defaults to **Node.js runtime** (was Edge by default) |
| **Functionality** | Identical — only naming changed |
| **Config keys renamed** | `skipMiddlewareUrlNormalize` → `skipProxyUrlNormalize` |
| | `experimental.middlewareClientMaxBodySize` → `experimental.proxyClientMaxBodySize` |
| | `experimental.externalMiddlewareRewritesResolve` → `experimental.externalProxyRewritesResolve` |

### Automated Migration (Codemod)

```bash
npx @next/codemod@canary middleware-to-proxy .
```

This renames the file and updates the export name automatically.

---

## What Is Proxy?

Proxy runs **server-side code before a request is completed**. It intercepts every incoming request at a network boundary in front of your app, allowing you to:

- **Redirect** the request to a different URL
- **Rewrite** — serve a different URL's content while keeping the original URL in the browser
- **Modify request headers** before they reach your route
- **Modify response headers** before they reach the client
- **Respond directly** with a `Response` or `NextResponse`
- Read and set **cookies**

---

## CRITICAL DEFAULTS — Read First

| Assumption (WRONG) | Correct Behavior |
|---|---|
| The file is called `middleware.ts` | It is now `proxy.ts` (v16+). `middleware.ts` is deprecated. |
| The export is `export function middleware()` | Must be `export function proxy()` or a default export |
| Proxy runs only on matched routes by default | Proxy runs on **every route** unless you configure a `matcher` |
| Proxy is the right place for auth session logic | Proxy should only do **optimistic/lightweight checks** — full auth belongs in Route Handlers or Server Actions |
| `fetch` caching options work inside Proxy | `fetch` with `options.cache`, `options.next.revalidate`, or `options.next.tags` has **no effect** in Proxy |
| Proxy shares modules/globals with the app | Proxy runs **isolated from render code** — do not rely on shared module state or globals |
| Use Proxy as a first solution | Proxy is a **last resort** — use `redirects` in `next.config.ts` or Route Handlers first |
| Static exports support Proxy | Proxy is **not supported** in static exports |
| `_next/data` exclusions in matcher skip Proxy | Proxy **always runs** for `_next/data` routes even if excluded — intentional security behavior |

---

## File Convention

```
project-root/
├── proxy.ts          ← place here (same level as app/ or pages/)
├── app/
└── src/
    └── proxy.ts      ← OR here if using src/ layout
```

- Only **one** `proxy.ts` file is supported per project.
- Break complex logic into separate modules and import them into `proxy.ts`.
- If you use `pageExtensions` (e.g. `.page.ts`), name the file `proxy.page.ts`.

---

## Basic Structure

```ts
// proxy.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Named export (preferred)
export function proxy(request: NextRequest) {
  return NextResponse.redirect(new URL('/home', request.url))
}

// OR default export — both are valid
// export default function proxy(request: NextRequest) { ... }

// Optional: restrict which paths trigger Proxy
export const config = {
  matcher: '/about/:path*',
}
```

---

## When to Use Proxy vs Alternatives

| Use case | Best solution |
|---|---|
| Simple static redirects | `redirects` in `next.config.ts` |
| Redirect based on request data (headers, cookies, URL) | **Proxy** ✅ |
| A/B testing / route rewrites | **Proxy** ✅ |
| Modifying headers for all pages | **Proxy** ✅ |
| CORS headers on API routes | Route Handler or **Proxy** |
| Auth — reading a session token for a quick optimistic redirect | **Proxy** (lightweight check only) ✅ |
| Auth — full session validation or DB lookups | Route Handlers / Server Actions ❌ not Proxy |
| Slow data fetching | ❌ Never in Proxy |
| Background analytics/logging | Proxy with `waitUntil` ✅ |

---

## Matcher Configuration

Without a `matcher`, Proxy runs on every request. Always add one.

### String matcher (single path)
```js
export const config = {
  matcher: '/dashboard/:path*',
}
```

### Array matcher (multiple paths)
```js
export const config = {
  matcher: ['/about/:path*', '/dashboard/:path*'],
}
```

### Regex negative lookahead (exclude static/internal paths)
```js
export const config = {
  matcher: [
    // Run on all paths EXCEPT these
    '/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)',
  ],
}
```

### Advanced object matcher (with `has` / `missing` conditions)
```js
export const config = {
  matcher: [
    {
      source: '/api/:path*',
      locale: false,                                              // ignore locale prefix
      has: [
        { type: 'header', key: 'Authorization' },                // only if header present
        { type: 'query', key: 'userId', value: '123' },
      ],
      missing: [
        { type: 'cookie', key: 'session', value: 'active' },     // only if cookie absent
      ],
    },
  ],
}
```

### Matcher path rules
- MUST start with `/`
- `/about/:path` matches `/about/a` but NOT `/about/a/b` (no deep nesting)
- `/about/:path*` matches `/about/a/b/c` (`*` = zero or more segments)
- `/about/:path?` matches `/about` or `/about/a` (`?` = zero or one)
- `/about/:path+` requires at least one segment (`+` = one or more)
- `/about/(.*)` is equivalent to `/about/:path*`
- `matcher` values must be **static constants** — dynamic variables are ignored at build time

> **Important:** Even if you exclude `_next/data` paths in your matcher, Proxy will still run for those routes. This is intentional to prevent security gaps where protecting a page but not its data route would leave an exposure.

---

## NextResponse API

All Proxy responses go through `NextResponse`:

```ts
import { NextResponse } from 'next/server'

// Redirect to a new URL (302 by default)
NextResponse.redirect(new URL('/login', request.url))

// Rewrite — serve /dashboard/user content but keep /dashboard in browser URL
NextResponse.rewrite(new URL('/dashboard/user', request.url))

// Pass through to the next handler
NextResponse.next()

// Respond directly with JSON
NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
```

---

## Common Patterns

### Redirect

```ts
// proxy.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function proxy(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith('/old-blog')) {
    return NextResponse.redirect(new URL('/blog', request.url))
  }
}
```

### Conditional Rewrite

```ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function proxy(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith('/about')) {
    return NextResponse.rewrite(new URL('/about-2', request.url))
  }
  if (request.nextUrl.pathname.startsWith('/dashboard')) {
    return NextResponse.rewrite(new URL('/dashboard/user', request.url))
  }
}
```

### Reading and Setting Cookies

```ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function proxy(request: NextRequest) {
  // Read incoming cookie
  const token = request.cookies.get('auth-token')

  if (!token) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  // Set cookie on the response
  const response = NextResponse.next()
  response.cookies.set('visited', 'true', { path: '/' })
  return response
}
```

Cookie methods on `NextRequest`: `get`, `getAll`, `has`, `set`, `delete`, `clear`
Cookie methods on `NextResponse`: `get`, `getAll`, `set`, `delete`

### Setting Headers

```ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function proxy(request: NextRequest) {
  // Clone and modify request headers (passed upstream to the route)
  const requestHeaders = new Headers(request.headers)
  requestHeaders.set('x-user-id', 'abc123')

  const response = NextResponse.next({
    request: { headers: requestHeaders },   // ← upstream headers
  })

  // Set response headers (sent to the client)
  response.headers.set('x-powered-by', 'my-app')
  return response
}
```

> **Key distinction:**
> - `NextResponse.next({ request: { headers } })` → headers go **upstream to the route handler**
> - `response.headers.set(...)` → headers go **downstream to the client**
> - Do NOT use `NextResponse.next({ headers })` to pass upstream — that sends them to the client instead.

### Optimistic Auth Check (Lightweight)

```ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function proxy(request: NextRequest) {
  const session = request.cookies.get('session')

  // Optimistic: just check if the cookie exists, not if it's valid
  if (!session && request.nextUrl.pathname.startsWith('/dashboard')) {
    return NextResponse.redirect(new URL('/login', request.url))
  }
}

export const config = {
  matcher: '/dashboard/:path*',
}
```

> **Warning:** Do NOT perform full session validation (DB lookups, JWT verification with external keys) here. That belongs in Route Handlers or Server Actions. Proxy is for fast, optimistic checks only.

### Producing a Direct Response

```ts
import type { NextRequest } from 'next/server'
import { isAuthenticated } from '@/lib/auth'

export const config = {
  matcher: '/api/:function*',
}

export function proxy(request: NextRequest) {
  if (!isAuthenticated(request)) {
    return Response.json(
      { success: false, message: 'authentication failed' },
      { status: 401 }
    )
  }
}
```

### CORS

```ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const allowedOrigins = ['https://acme.com', 'https://my-app.org']
const corsOptions = {
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
}

export function proxy(request: NextRequest) {
  const origin = request.headers.get('origin') ?? ''
  const isAllowedOrigin = allowedOrigins.includes(origin)
  const isPreflight = request.method === 'OPTIONS'

  if (isPreflight) {
    return NextResponse.json({}, {
      headers: {
        ...(isAllowedOrigin && { 'Access-Control-Allow-Origin': origin }),
        ...corsOptions,
      },
    })
  }

  const response = NextResponse.next()
  if (isAllowedOrigin) {
    response.headers.set('Access-Control-Allow-Origin', origin)
  }
  Object.entries(corsOptions).forEach(([k, v]) => response.headers.set(k, v))
  return response
}

export const config = { matcher: '/api/:path*' }
```

### Background Work with `waitUntil`

```ts
import { NextResponse } from 'next/server'
import type { NextFetchEvent, NextRequest } from 'next/server'

export function proxy(req: NextRequest, event: NextFetchEvent) {
  // Non-blocking background task — does not delay the response
  event.waitUntil(
    fetch('https://analytics.example.com', {
      method: 'POST',
      body: JSON.stringify({ pathname: req.nextUrl.pathname }),
    })
  )

  return NextResponse.next()
}
```

### Using `NextProxy` Type (Shorthand)

```ts
import type { NextProxy } from 'next/server'

export const proxy: NextProxy = (request, event) => {
  event.waitUntil(Promise.resolve())
  return Response.json({ pathname: request.nextUrl.pathname })
}
```

---

## Modular Organization Pattern

Only one `proxy.ts` is allowed, but you can split logic across files:

```ts
// proxy.ts
import { handleAuth } from './lib/proxy/auth'
import { handleI18n } from './lib/proxy/i18n'
import { handleFeatureFlags } from './lib/proxy/feature-flags'
import type { NextRequest } from 'next/server'

export function proxy(request: NextRequest) {
  const authResponse = handleAuth(request)
  if (authResponse) return authResponse

  const i18nResponse = handleI18n(request)
  if (i18nResponse) return i18nResponse

  return handleFeatureFlags(request)
}

export const config = {
  matcher: '/((?!_next/static|_next/image|favicon.ico).*)',
}
```

---

## Execution Order

Proxy runs **third** in the request pipeline:

```
1. headers        (next.config.ts)
2. redirects      (next.config.ts)
3. Proxy          ← runs here
4. beforeFiles rewrites  (next.config.ts)
5. Filesystem routes (public/, _next/static/, pages/, app/)
6. afterFiles rewrites   (next.config.ts)
7. Dynamic routes (/blog/[slug])
8. fallback rewrites     (next.config.ts)
```

> **Server Functions note:** Server Functions (Server Actions) are not separate routes — they are POST requests to the route where they are defined. A matcher that excludes a path will also skip Proxy for Server Function calls on that path. **Do not rely on Proxy alone for auth — always validate inside each Server Function too.**

---

## RSC Requests and Rewrites

Next.js strips internal RSC Flight headers (`rsc`, `next-router-state-tree`, `next-router-prefetch`) from the `request` object inside Proxy. This prevents accidentally handling RSC and HTML requests differently (they must align).

When using `NextResponse.rewrite()`, RSC headers are automatically propagated. If you implement custom rewrite logic using `fetch()`, you must forward RSC headers manually, or enable `skipProxyUrlNormalize`:

```js
// next.config.js
module.exports = {
  skipProxyUrlNormalize: true,
}
```

---

## Advanced Config Flags

### `skipTrailingSlashRedirect`

Disables Next.js automatic trailing-slash redirects, allowing Proxy to handle them selectively (useful for incremental migrations):

```js
// next.config.js
module.exports = { skipTrailingSlashRedirect: true }
```

### `skipProxyUrlNormalize`

Disables URL normalization — Proxy receives the raw original URL instead of the normalized one. Useful for advanced custom rewrite logic that needs the exact URL shape:

```js
// next.config.js
module.exports = { skipProxyUrlNormalize: true }
```

---

## Unit Testing (Experimental)

Available since v15.1 via `next/experimental/testing/server`:

```ts
import {
  unstable_doesProxyMatch,
  isRewrite,
  getRewrittenUrl,
} from 'next/experimental/testing/server'

// Test if proxy runs for a given URL
expect(
  unstable_doesProxyMatch({ config, nextConfig, url: '/test' })
).toEqual(false)

// Test the full proxy function output
const request = new NextRequest('https://example.com/docs')
const response = await proxy(request)
expect(isRewrite(response)).toEqual(true)
expect(getRewrittenUrl(response)).toEqual('https://other-domain.com/docs')
```

---

## Platform Support

| Deployment option | Proxy supported? |
|---|---|
| Node.js server | ✅ Yes |
| Docker container | ✅ Yes |
| Static export | ❌ No |
| Adapters (Vercel, Netlify, etc.) | Platform-specific |

---

## Version History

| Version | Change |
|---|---|
| v16.0.0 | `middleware` deprecated; renamed to `proxy`. Defaults to Node.js runtime. |
| v15.5.0 | Node.js runtime for middleware became stable |
| v15.2.0 | Node.js runtime for middleware (experimental) |
| v13.1.0 | Advanced flags (`skipMiddlewareUrlNormalize`, `skipTrailingSlashRedirect`) added |
| v13.0.0 | Can modify request headers, response headers, and respond directly |
| v12.2.0 | Middleware stable |
| v12.0.0 | Middleware (Beta) introduced |

---

## Migration Diff Reference

```diff
// File rename
- middleware.ts
+ proxy.ts

// Export rename
- export function middleware(request: NextRequest) {
+ export function proxy(request: NextRequest) {

// next.config.js key renames
- skipMiddlewareUrlNormalize: true
+ skipProxyUrlNormalize: true

- experimental.middlewareClientMaxBodySize
+ experimental.proxyClientMaxBodySize

- experimental.externalMiddlewareRewritesResolve
+ experimental.externalProxyRewritesResolve
```

---

## Common Mistakes Agent Should Avoid

1. **Generating `middleware.ts`** — always generate `proxy.ts` for v16+ projects.
2. **Exporting `middleware` function** — the named export must be `proxy` (or a default export).
3. **Omitting the `matcher`** — without it, Proxy runs on every request including `_next/static`, `_next/image`, API routes, etc. Always configure a matcher.
4. **Using `fetch` with caching options** — `options.cache`, `options.next.revalidate`, and `options.next.tags` are silently ignored inside Proxy.
5. **Full auth/session validation in Proxy** — Proxy is for lightweight optimistic checks only. Real validation goes in Route Handlers or Server Actions.
6. **Relying on shared module state** — Proxy is isolated from app render code; globals and module-level state are not shared.
7. **Mixing up upstream vs downstream headers** — `NextResponse.next({ request: { headers } })` sends headers to the route handler; `response.headers.set(...)` sends them to the client.
8. **Expecting `_next/data` exclusions to work** — Proxy always runs for `_next/data` routes regardless of matcher exclusions.
9. **Placing heavy logic or DB calls in Proxy** — this adds latency to every matched request. Keep Proxy fast.
10. **Using legacy `next/router` imports** — Proxy uses `next/server` (`NextRequest`, `NextResponse`, `NextFetchEvent`).

---

*Sources:*
- *https://nextjs.org/docs/app/getting-started/proxy (v16.2.3, retrieved 2026-04-17)*
- *https://nextjs.org/docs/app/api-reference/file-conventions/proxy (v16.2.3, retrieved 2026-04-17)*
- *https://nextjs.org/docs/messages/middleware-to-proxy (retrieved 2026-04-17)*
- *https://nextjs.org/blog/next-16 (retrieved 2026-04-17)*