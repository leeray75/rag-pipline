# Auth & Security — RAG Context Documents

> **Phase**: Phase 7, Subtask 3 — Authentication & Security  
> **Created**: 2026-04-19  
> **Purpose**: RAG context documents for LLM knowledge gaps when implementing auth and security

> **Open-source only**: All tools are free and open-source. No paid services required.
> - `python-jose` — MIT license
> - `slowapi` — MIT license
> - SSRF prevention — Python standard library only

---

## Document Index

| Document | Technology | Version | Key Topics |
|---|---|---|---|
| [`python-jose-jwt-fastapi-rag.md`](./python-jose-jwt-fastapi-rag.md) | python-jose + FastAPI | 3.4.0 | JWT encode/decode, HTTPBearer, role-based deps, login endpoint |
| [`slowapi-rate-limiting-rag.md`](./slowapi-rate-limiting-rag.md) | slowapi | 0.1.9 | Rate limiting, decorator order, 429 handler, Redis backend |
| [`ssrf-url-validation-rag.md`](./ssrf-url-validation-rag.md) | Python stdlib | 3.9+ | SSRF prevention, private IP blocking, ipaddress, socket |
| [`auth-security-integration-overview-rag.md`](./auth-security-integration-overview-rag.md) | Full stack | All | main.py order, auth flow, SSRF flow, security checklist |

---

## Technology Versions

| Component | Package | Version | License |
|---|---|---|---|
| JWT | `python-jose[cryptography]` | 3.4.0 | MIT |
| Rate Limiting | `slowapi` | 0.1.9 | MIT |
| SSRF Prevention | Python stdlib (`ipaddress`, `socket`) | 3.9+ | PSF |

---

## Key Knowledge Gaps Covered

| Gap | Document |
|---|---|
| `algorithms=["HS256"]` must be a list (not string) | [`python-jose-jwt-fastapi-rag.md`](./python-jose-jwt-fastapi-rag.md) |
| slowapi decorator order: `@router.get` ABOVE `@limiter.limit` | [`slowapi-rate-limiting-rag.md`](./slowapi-rate-limiting-rag.md) |
| `request: Request` required in rate-limited routes | [`slowapi-rate-limiting-rag.md`](./slowapi-rate-limiting-rag.md) |
| `app.state.limiter` must be set before routers | [`auth-security-integration-overview-rag.md`](./auth-security-integration-overview-rag.md) |
| `socket.getaddrinfo` returns list of tuples, IP is `sockaddr[0]` | [`ssrf-url-validation-rag.md`](./ssrf-url-validation-rag.md) |
| IPv6 in URLs uses bracket notation `http://[::1]/` | [`ssrf-url-validation-rag.md`](./ssrf-url-validation-rag.md) |
| `HTTPBearer` returns 403 (not 401) when no header present | [`python-jose-jwt-fastapi-rag.md`](./python-jose-jwt-fastapi-rag.md) |

---

## Related Files

- **Subtask 3 plan**: [`../plans/phase-7/subtasks/phase-7-subtask-3-auth-and-security.md`](../plans/phase-7/subtasks/phase-7-subtask-3-auth-and-security.md)
- **Production hardening docs**: [`../production-hardening/README.md`](../production-hardening/README.md)
- **Observability docs**: [`../observability/README.md`](../observability/README.md)
