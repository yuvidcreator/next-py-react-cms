# PyPress CMS — Master Blueprint

> Single source of truth. Reference this document at the start of every coding session.

## Three-Tier Architecture (Internal-Only APIs)

1. **NextJS Frontend** (port 3000) — PUBLIC, crawlable, SSR for SEO
2. **React Admin** (port 3001) — PRIVATE, noindex/nofollow, wp-admin equivalent
3. **FastAPI Backend** (port 8000) — INTERNAL ONLY, zero public exposure

All APIs consumed internally via Docker network. Only NextJS is publicly accessible.

## Auth Security Model

- Access token: httpOnly cookie (JS cannot read it — XSS-proof)
- Refresh token: httpOnly cookie with restricted path (/api/v1/auth only)
- CSRF token: Regular cookie (JS reads it, sends as X-CSRF-Token header)
- Sessions tracked in pp_user_sessions (revocable)
- OAuth2.0 scaffolded for Google/GitHub/Facebook (future Phase 9+)
- Password hashing: bcrypt (not WordPress's MD5/phpass)

## Phase Status

- Phase 1: Foundation — COMPLETE (hooks, models, repos, plugins, themes, auth, posts API)
- Phase 2: Docker Architecture + React Admin Shell — NEXT
- Phase 3-10: See IMPLEMENTATION-PHASES.md

## Core Design Rules

1. Every data operation fires appropriate hooks
2. All APIs internal-only — NextJS frontend is sole public interface
3. Plugins extend via hooks, never by patching core
4. SOLID principles throughout
5. WordPress parity: same roles, capabilities, template hierarchy, post types
