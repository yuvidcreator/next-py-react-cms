# PyPress CMS — Project Context & Development Status

> **Purpose:** Upload this file at the start of every new chat session to preserve full project context. This document captures everything built, architectural decisions made, the current project state, known issues, and the complete remaining work breakdown.
>
> **Last updated:** March 15, 2026 — End of Phase 4

---

## 1. What is PyPress?

PyPress is an **open-source CMS that replicates WordPress's architecture** — hooks, plugins, themes, template hierarchy, RBAC, the "everything is a post" philosophy — but using a modern Python + React tech stack. The goal is to eventually replace WordPress for developers who prefer Python over PHP.

**The WordPress-to-PyPress mental model** is the primary design guide. Every architectural decision mirrors a WordPress equivalent: `pp_posts` maps to `wp_posts`, `BasePlugin` maps to WordPress's plugin header system, `TemplateResolver` maps to WordPress's template hierarchy, `add_action`/`add_filter` maps to PyPress's `HookRegistry`, and so on.

---

## 2. Tech Stack & Versions

| Layer | Technology | Version |
|-------|-----------|---------|
| **Backend** | Python + FastAPI | 3.12 / 0.115 |
| **Database** | PostgreSQL | 16 (Alpine) |
| **Cache** | Redis | 7 (Alpine) |
| **ORM** | SQLAlchemy (async) | 2.0+ |
| **Migrations** | Alembic | 1.13+ |
| **Admin Frontend** | React + TypeScript | 19.2 |
| **Routing** | React Router DOM | **v7.13** |
| **State** | Zustand + TanStack Query | v5 / v5 |
| **Styling** | Tailwind CSS | **v4** (uses `@tailwindcss/vite` plugin) |
| **UI Components** | Shadcn/UI | radix-nova style |
| **Build** | Vite | **v8** |
| **Package Manager** | Yarn | v4 (corepack) |
| **Icons** | Lucide React | 0.383 |
| **Toasts** | Sonner | via shadcn |
| **Font** | Geist (@fontsource-variable/geist) | — |
| **Public Frontend** | NextJS + TypeScript | (Phase 5 — not started) |
| **Infrastructure** | Docker Compose | 3 networks, 7 services |
| **Auth** | httpOnly JWT cookies | bcrypt + SHA-256 |

### Important version notes for development:
- **React Router v7**: Routes must be defined as explicit JSX `<Route>` elements in `App.tsx`. The v6 pattern of spreading `RouteObject[]` onto `<Route>` components causes type errors in v7. Do NOT use `RouteObject` arrays with spread.
- **Tailwind CSS v4**: Uses `@import "tailwindcss"` in CSS (NOT `@tailwind base/components/utilities`). Custom colors are registered in `@theme { --color-*: var(--*); }` blocks. The `@tailwindcss/vite` plugin replaces the PostCSS plugin. The `tailwind.config.js` file is **not used** by Tailwind v4 (kept for reference only).
- **Yarn v4**: Use `corepack enable` then `yarn install`. Dockerfile uses `yarn install --frozen-lockfile`.

---

## 3. Architecture Overview

```
                    ┌──────────────────────────┐
                    │        INTERNET           │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │     Nginx (port 80/443)   │ ← SSL termination
                    │     pypress-public net    │
                    └──┬──────────┬──────────┬─┘
                       │          │          │
              ┌────────▼───┐ ┌───▼────┐     │
              │  NextJS    │ │ React  │     │ /api → BLOCKED
              │  Frontend  │ │ Admin  │     │ (404 for public)
              │  port 3000 │ │ p:3001 │     │
              │  CRAWLABLE │ │noindex │     │
              └────────────┘ └───┬────┘     │
                                 │          │
                    ┌────────────▼──────────▼──┐
                    │   pypress-internal net    │ ← internal: true
                    │   (NOT public)            │
                    │                           │
                    │  ┌─────────────────────┐  │
                    │  │  FastAPI Backend     │  │
                    │  │  port 8000           │  │
                    │  │  NO host port map    │  │
                    │  │  66 API endpoints    │  │
                    │  └──────┬──────┬───────┘  │
                    │         │      │           │
                    │  ┌──────▼──┐ ┌─▼────────┐ │
                    │  │  PgSQL  │ │  Redis    │ │
                    │  │  :5432  │ │  :6379    │ │
                    │  └─────────┘ └──────────┘ │
                    └───────────────────────────┘
```

**Key rule:** The backend API is INTERNAL ONLY — never publicly accessible. Only NextJS (crawlable) and React Admin (noindex) face the internet. The admin panel accesses the API through Nginx's internal proxy (`/internal-api/` → `backend:8000/api/`).

### Three Docker Networks:
- `pypress-public` — Nginx + Frontend + Admin (internet-facing)
- `pypress-internal` (internal: true) — Backend + DB + Redis + Worker (isolated)
- `pypress-admin-net` — Admin + Backend (admin-to-API bridge)

### Auth Architecture:
- **Access token**: httpOnly cookie, SameSite=Lax, 15min expiry
- **Refresh token**: httpOnly cookie, SameSite=Strict, path=/api/v1/auth, 30 days
- **CSRF token**: Regular cookie (JS-readable), double-submit pattern
- **Token rotation** on refresh — old hash replaced in session store
- **RBAC**: All 5 WordPress roles (administrator, editor, author, contributor, subscriber) with exact capability sets

---

## 4. Completed Phases

### Phase 1: Foundation ✅ (Previous session — packaged as pypress-phase1-complete.tar.gz)
- Hook system (async Observer pattern with priority queues)
- Database models (all `pp_*` tables mirroring WordPress)
- BaseRepository with hook integration + PostRepository with WP_Query-equivalent `query()`
- Plugin system (BasePlugin ABC + PluginLoader with dependency resolution)
- Theme system (TemplateResolver with WordPress-exact template hierarchy)
- Auth (JWT + bcrypt + RBAC + httpOnly cookies)
- Posts REST API + FastAPI app factory

### Phase 2: Docker + Admin Shell ✅
**Tasks 2.1-2.7 completed:**
- Docker Compose (7 services, 3 networks, 7 volumes, health checks)
- Nginx configuration (SSL, security headers, API blocking, noindex for admin)
- Backend Dockerfile (3-stage: base → development → production)
- Admin Dockerfile (4-stage: deps → development → build → production, Yarn)
- React Admin project setup (React 19, Router v7, TanStack Query v5, Zustand v5, Tailwind v4)
- Authentication flow (login page, httpOnly cookies, auto-refresh interceptor, ProtectedRoute)
- Admin layout shell (collapsible sidebar, topbar with user dropdown, content area)
- Dashboard page (6 widgets: Welcome, At-a-Glance, Quick Draft, Recent Posts, Site Health, Activity)

### Phase 3: Admin Core Features ✅
**All tasks 3.1-3.9 completed:**
- **Task 3.1** — Post List Page (status tabs, search, sort, pagination, bulk actions, row hover actions)
- **Task 3.2** — Post Editor Page (two-column layout, title/slug/content/excerpt, publish panel, categories checklist, tags input, featured image placeholder, auto-save 60s, unsaved changes warning)
- **Task 3.3** — Page Management (reuses PostEditor with post_type=page, hierarchical list with indentation, Page Builder placeholder)
- **Task 3.4** — Media Library (grid/list toggle, upload drop zone, MIME type filter tabs, detail sidebar panel with metadata editing, bulk delete)
- **Task 3.5** — User Management (role filter tabs, create/edit slide panel, password toggle, capabilities preview, delete with reassignment)
- **Task 3.6** — Category Management (two-panel layout: add form + hierarchical tree, recursive tree component, inline editing, expand/collapse)
- **Task 3.7** — Tag Management (two-panel layout: add form + flat list, tag cloud visualization, merge feature, inline editing)
- **Task 3.8** — Settings Pages (tabbed: General/Reading/Writing/Permalinks, dirty state tracking, Save Changes button)
- **Task 3.9** — All Backend API Endpoints (54 endpoints across 8 routers: Posts, Users, Taxonomies, Media, Comments, Menus, Options, Settings)

### Phase 4: Plugin & Theme System ✅
**All tasks 4.1-4.7 completed:**
- **Tasks 4.1+4.2** — Plugin backend API (list, get, upload, activate, deactivate, delete — 6 endpoints)
- **Task 4.3** — Plugin Management UI (Installed/Upload/Browse tabs, plugin cards with status + security badges, activate/deactivate/delete actions, validation results display)
- **Task 4.4** — Dynamic Admin Menu (GET /admin/menu merges core menu + plugin pages, sidebar fetches dynamically, cache invalidation on activate/deactivate, icon name → Lucide component mapping)
- **Task 4.5** — Theme backend API (list, get, upload, activate, delete — 5 endpoints)
- **Task 4.6** — Theme Management UI (active theme prominent card, theme gallery grid, upload zone, Customize/Preview placeholders for Phase 7)
- **Task 4.7** — Plugin Security Scanner (AST-based dangerous import detection, regex pattern scanning, manifest validation, Python syntax verification, file permission checking, severity system: critical/warning/info)

---

## 5. Current Project State

### Backend: 66 API Endpoints
| Router | Endpoints | File |
|--------|-----------|------|
| Auth | 4 | auth.py (login, refresh, logout, me) |
| Posts | 8 | posts.py (list, get, get-by-slug, create, update, delete, restore, bulk) |
| Options | 4 | options.py (get, set, delete, bulk-update) |
| Settings | 8 | options.py (4× GET + 4× PATCH for general/reading/writing/permalinks) |
| Users | 5 | users.py (list, get, create, update, delete) |
| Taxonomies | 7 | taxonomies.py (list, tree, get, create, update, delete, merge) |
| Media | 6 | media.py (list, get, upload, update, delete, bulk-delete) |
| Comments | 6 | comments.py (list, get, create, update, delete, bulk) |
| Menus | 6 | menus.py (list, get, create, update, delete, save-items) |
| Plugins | 6 | plugins_themes.py (list, get, upload, activate, deactivate, delete) |
| Themes | 5 | plugins_themes.py (list, get, upload, activate, delete) |
| Admin | 1 | admin_menu.py (dynamic sidebar menu) |

### Admin Frontend: 17 Pages
| Page | Status | Size | Description |
|------|--------|------|-------------|
| LoginPage | ✅ Full | 9.6KB | Username/password, show/hide toggle, redirect-after-login |
| DashboardPage | ✅ Full | 3KB | 6 widget cards (Welcome, Stats, Draft, Posts, Health, Activity) |
| PostListPage | ✅ Full | 23KB | Status tabs, search, sort, pagination, bulk actions |
| PostEditorPage | ✅ Full | 24KB | Two-column, slug editor, categories, tags, auto-save |
| PageListPage | ✅ Full | 22KB | Hierarchical display, Page Builder placeholder |
| MediaLibraryPage | ✅ Full | 23KB | Grid/list toggle, MIME filter, detail sidebar |
| UserListPage | ✅ Full | 24KB | Role tabs, create/edit panel, capabilities preview |
| CategoriesPage | ✅ Full | 14KB | Two-panel, recursive tree, inline editing |
| TagsPage | ✅ Full | 14KB | Tag cloud, merge feature, inline editing |
| SettingsPage | ✅ Full | 16KB | 4 tabs (General/Reading/Writing/Permalinks) |
| PluginsPage | ✅ Full | 12KB | Installed/Upload/Browse tabs, security badges |
| ThemesPage | ✅ Full | 9KB | Active theme card, gallery grid, upload |
| CommentsPage | ⬜ Stub | 0.7KB | Placeholder |
| MenusPage | ⬜ Stub | 0.7KB | Placeholder |
| WidgetsPage | ⬜ Stub | 0.7KB | Placeholder |
| ToolsPage | ⬜ Stub | 0.7KB | Placeholder |
| NotFoundPage | ⬜ Stub | 0.7KB | Placeholder |

### Data Layer: In-Memory (NOT connected to database yet)
- All API endpoints use Python dictionaries as data stores
- Every router file has `# Replace with DB query` or `# Replace with Phase 1` comments marking where SQLAlchemy integration goes
- Demo data is loaded on startup: 3 users, 5 posts, 4 categories, 3 tags, 4 media items, 9 comments, 3 plugins, 2 themes, 20+ options
- Data resets on container restart
- Default login: username `admin`, password `admin`

### Feature Architecture Pattern (used everywhere):
```
features/{feature}/
  api/
    {feature}-api.ts     ← Typed API client (Axios calls)
    index.ts             ← Barrel export
  hooks/
    use-{feature}.ts     ← TanStack Query hooks (cache + mutations)
    index.ts             ← Barrel export
  components/            ← Feature-specific components (if needed)

pages/
  {Feature}Page.tsx      ← Full page component using hooks
```

---

## 6. Known Issues & Fixes Applied

1. **auth/__init__.py import error** — The file must be empty/comments only. All imports use full paths like `from app.core.auth.jwt_handler import hash_password`. Do NOT add re-exports to `__init__.py`.

2. **index.html double /admin/ path** — Script src must be `/src/main.tsx` (NOT `/admin/src/main.tsx`). Vite's `base: "/admin"` config adds the prefix automatically.

3. **Infinite 401 auth loop** — The Axios interceptor must skip retry logic for auth URLs (`/auth/me`, `/auth/refresh`, `/auth/login`, `/auth/logout`). The `isAuthUrl()` check in `api/client.ts` handles this.

4. **React Router v7 type errors** — Routes must be defined as explicit JSX `<Route>` elements. Do NOT use `RouteObject[]` arrays with spread `{...route}` pattern.

5. **Tailwind v4 no CSS output** — Must use `@import "tailwindcss"` (not `@tailwind base`), register colors in `@theme { --color-*: var(--*); }`, and add `@tailwindcss/vite` to vite plugins.

6. **Admin UI needs styling improvement** — Colors are functional but the overall design needs polish. CSS variables are properly wired but some components may need visual refinement.

---

## 7. Remaining Work — Phase by Phase

### Phase 5: NextJS Frontend (SSR + SEO) 🔲
Build the public-facing website that visitors see. This is where SEO happens — all pages are server-side rendered with meta tags.

| Task | Description |
|------|-------------|
| 5.1 | NextJS project setup (TypeScript, app router, SSR config) |
| 5.2 | Theme engine (loads templates from active theme, template hierarchy) |
| 5.3 | Public routing: `/`, `/blog`, `/page/:slug`, `/category/:slug`, `/tag/:slug`, `/author/:slug` |
| 5.4 | SEO: meta tags, Open Graph, JSON-LD structured data, sitemap.xml |
| 5.5 | Default theme React components (Header, Footer, Single, Archive, Page, etc.) |

### Phase 6: Live Page Builder (Drag-and-Drop) 🔲
Build the Elementor-like block editor for visual page building.

| Task | Description |
|------|-------------|
| 6.1 | Block editor using dnd-kit (palette, canvas, properties panel) |
| 6.2 | Core blocks: Heading, Paragraph, Image, Video, Columns, Spacer, Divider, Button, List, Quote, Table, HTML, Embed |
| 6.3 | Theme block registration (custom blocks from active theme) |
| 6.4 | Block storage format (JSON structure in database) |
| 6.5 | Block rendering in NextJS (BlockRenderer component with SSR) |
| 6.6 | Live preview mode (split-screen editor + preview) |

### Phase 7: Advanced Features 🔲

| Task | Description |
|------|-------------|
| 7.1 | Elasticsearch plugin (auto-indexing, search replacement, admin page) |
| 7.2 | Redis caching plugin (page cache, query cache, object cache, stats page) |
| 7.3 | Comment system (full CRUD, nested/threaded, moderation workflow, guest comments) |
| 7.4 | Menu editor (drag-and-drop builder, nested items, theme location assignment) |
| 7.5 | Widget editor (drag widgets into theme-defined areas) |

### Phase 8: IaC, Monitoring, Production 🔲

| Task | Description |
|------|-------------|
| 8.1 | Complete Makefile (all commands from IaC guide) |
| 8.2 | Monitoring stack (Prometheus, Grafana, Loki, Alertmanager) |
| 8.3 | Backup system (automated daily, pre-operation snapshots, one-click restore) |
| 8.4 | Security hardening (headers, CSP, rate limiting, audit logging) |

### Critical Pre-Frontend Task: Database Integration 🔲
Before Phase 5, the in-memory data stores need to be replaced with real PostgreSQL queries. This involves:
- Merging Phase 1's SQLAlchemy models into the current codebase
- Creating Alembic migration files for all `pp_*` tables
- Writing a seed script (creates admin user, default categories, default options)
- Replacing `_POSTS`, `_USERS`, `_COMMENTS`, etc. dicts with actual repository calls
- Adding database session management to FastAPI's dependency injection

---

## 8. Key Conventions & Patterns

### Naming:
- Table prefix: `pp_` (mirrors WordPress's `wp_`)
- Hook system: `CoreHooks` constants class, `add_action`/`add_filter`/`do_action`/`apply_filters`
- Plugin base class: `BasePlugin` ABC with `PluginManifest` from `plugin.json`
- Template resolver: WordPress-exact hierarchy (SingleRecipePasta → SingleRecipe → Single → Singular → Index)

### Design Principles:
- **WordPress is the north star** — when in doubt, mirror WordPress's approach
- **Security-first auth**: httpOnly cookies + double-submit CSRF, never expose tokens in response bodies
- **Plugin-first extensibility**: Elasticsearch, caching, and optional features belong in the plugin layer
- **Phase-by-phase progression**: Complete and package one phase before moving to the next
- **Backend-first for new phases**: Build all API endpoints first, then frontend pages

### Config:
- Auto-save interval: 60 seconds (for draft posts)
- Max upload size: 64MB (configurable via `UPLOAD_MAX_SIZE_MB`)
- Admin base path: `/admin`
- API base URL: `/api/v1` (internal), `/internal-api/v1` (via Nginx)
- CSRF cookie name: `pypress_csrf_token`
- CSRF header name: `X-CSRF-Token`

---

## 9. How to Run Locally

```bash
# Start backend (PostgreSQL + Redis + FastAPI)
docker compose -f docker-compose.local.yml up --build

# In a second terminal, start admin panel
cd admin
yarn install    # first time only
yarn dev

# Access:
#   Backend API docs: http://localhost:8000/api/docs
#   Admin panel:      http://localhost:3001/admin
#   Login:            admin / admin
```

Create `admin/.env.local` with:
```
VITE_API_BASE_URL=http://localhost:8000
```

---

## 10. File Structure Reference

```
pypress/
├── backend/
│   ├── Dockerfile                    # 3-stage (base/dev/prod)
│   ├── requirements.txt              # Pinned Python dependencies
│   ├── alembic.ini + alembic/        # Database migration config
│   ├── scripts/
│   │   ├── entrypoint.sh             # Production startup (migrations + health)
│   │   └── entrypoint-dev.sh         # Dev startup (skip migrations)
│   └── app/
│       ├── main.py                   # FastAPI app factory + route registration
│       └── core/
│           ├── config.py             # Pydantic Settings (env vars)
│           ├── auth/
│           │   ├── jwt_handler.py    # Token creation/validation, bcrypt
│           │   └── dependencies.py   # get_current_user, require_capability, RBAC
│           ├── api/
│           │   ├── schemas/          # 9 Pydantic schema files
│           │   └── v1/               # 10 router files (66 endpoints total)
│           └── security/
│               └── scanner.py        # Plugin security scanner (AST + regex)
├── admin/
│   ├── Dockerfile                    # 4-stage (deps/dev/build/prod), Yarn
│   ├── package.json                  # React 19, Router v7, Tailwind v4
│   ├── vite.config.ts                # @tailwindcss/vite plugin, /admin base
│   ├── index.html                    # Entry point (script src: /src/main.tsx)
│   └── src/
│       ├── main.tsx                  # React root + providers (BrowserRouter basename="/admin")
│       ├── App.tsx                   # Routes as JSX (React Router v7 pattern)
│       ├── api/
│       │   ├── client.ts             # Axios + CSRF + 401 interceptor (auth URLs excluded)
│       │   └── auth.ts               # Auth API functions
│       ├── stores/
│       │   ├── auth-store.ts         # Zustand: user state, login, logout, can()
│       │   └── sidebar-store.ts      # Zustand: sidebar collapse state (persisted)
│       ├── hooks/
│       │   └── use-admin-menu.ts     # Dynamic sidebar menu from API
│       ├── config/
│       │   ├── index.ts              # App config (env vars, constants)
│       │   └── navigation.ts         # Static admin menu (fallback)
│       ├── components/layout/
│       │   ├── AdminLayout.tsx        # Sidebar + Topbar + Content + Footer
│       │   ├── Sidebar.tsx            # Dynamic menu, collapse, capability filter
│       │   └── Topbar.tsx             # User dropdown, notifications, Visit Site
│       ├── features/                  # Feature-sliced architecture
│       │   ├── dashboard/components/  # 6 dashboard widget components
│       │   ├── posts/api/ + hooks/    # Posts API client + TanStack hooks
│       │   ├── media/api/ + hooks/    # Media API client + TanStack hooks
│       │   ├── users/api/ + hooks/    # Users API client + TanStack hooks
│       │   ├── taxonomies/api/+hooks/ # Taxonomies API client + TanStack hooks
│       │   ├── settings/api/ + hooks/ # Settings API client + TanStack hooks
│       │   ├── plugins/api/           # Plugins API client + TanStack hooks
│       │   └── themes/api/            # Themes API client + TanStack hooks
│       ├── pages/                     # 17 page components (13 full, 4 stubs)
│       ├── styles/globals.css         # Tailwind v4 (@import "tailwindcss" + @theme)
│       └── lib/utils.ts               # cn() for shadcn class merging
├── docker/
│   ├── nginx/                         # Nginx configs (prod, dev, SSL, security headers)
│   └── postgres/init/                 # PostgreSQL extensions (uuid-ossp, pg_trgm)
├── docker-compose.yml                 # Production (7 services, 3 networks)
├── docker-compose.dev.yml             # Dev override (port exposure, hot reload)
├── docker-compose.local.yml           # Local testing (backend + DB + Redis only)
├── Makefile                           # Developer CLI (make dev, make up, etc.)
└── LOCAL-TESTING-GUIDE.md             # Step-by-step local testing instructions
```
