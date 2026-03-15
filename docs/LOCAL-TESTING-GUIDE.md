# PyPress — Local Development Testing Guide

## Prerequisites

Before starting, make sure you have installed:

- **Docker Desktop** (v24+) — includes Docker Compose v2
- **Node.js** (v20+) with **Yarn** (corepack enable)
- **Git** for version control

Verify your installations:

```bash
docker --version          # Docker version 24.x+
docker compose version    # Docker Compose version v2.x+
node --version            # v20.x+
yarn --version            # 4.x+ (via corepack)
```

---

## Step 1: Project Setup

If you haven't already, clone and enter the project:

```bash
cd ~/projects/pypress    # or wherever your project lives
```

Make sure the extracted tar files are in the correct structure:

```
pypress/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── alembic.ini
│   ├── alembic/
│   ├── scripts/
│   │   ├── entrypoint.sh
│   │   └── entrypoint-dev.sh
│   └── app/
│       ├── main.py
│       └── core/
│           ├── config.py
│           ├── auth/
│           ├── api/
│           └── security/
├── admin/
│   ├── Dockerfile
│   ├── package.json
│   ├── yarn.lock          ← You need to generate this (Step 2)
│   ├── components.json
│   ├── vite.config.ts
│   └── src/
├── docker/
│   ├── nginx/
│   └── postgres/
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.local.yml    ← Use this for testing
└── Makefile
```

---

## Step 2: Generate yarn.lock (First Time Only)

The admin panel needs a `yarn.lock` file. Generate it:

```bash
cd admin
yarn install
cd ..
```

This creates `admin/yarn.lock` and installs node_modules locally.

---

## Step 3: Make Scripts Executable

```bash
chmod +x backend/scripts/entrypoint.sh
chmod +x backend/scripts/entrypoint-dev.sh
```

---

## Step 4: Start Backend Services

Start **only** the backend (PostgreSQL + Redis + FastAPI):

```bash
docker compose -f docker-compose.local.yml up --build
```

You should see output like:

```
pypress-db       | PostgreSQL init process complete; ready for start up.
pypress-redis    | Ready to accept connections
pypress-backend  | [entrypoint-dev] PostgreSQL ready
pypress-backend  | [entrypoint-dev] Redis ready
pypress-backend  | [entrypoint-dev] App module OK
pypress-backend  | INFO:     Uvicorn running on http://0.0.0.0:8000
pypress-backend  | INFO:     Started reloader process
```

Wait until you see "Uvicorn running" — the backend is ready.

---

## Step 5: Test the Backend API

### Health Check

Open your browser or use curl:

```bash
curl http://localhost:8000/api/health
```

Expected response:

```json
{
  "status": "healthy",
  "service": "pypress-backend",
  "version": "0.2.0"
}
```

### Swagger UI (Interactive API Docs)

Open in your browser:

```
http://localhost:8000/api/docs
```

This shows ALL 66 API endpoints with interactive testing. You can try any endpoint directly from the browser.

### Test Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}' \
  -c cookies.txt -v
```

You should see three `Set-Cookie` headers in the response:
- `pypress_access_token` (httpOnly)
- `pypress_refresh_token` (httpOnly)
- `pypress_csrf_token` (not httpOnly — JS can read it)

### Test Authenticated Endpoints

```bash
# List posts (using the cookies from login)
curl http://localhost:8000/api/v1/posts -b cookies.txt | python3 -m json.tool

# List users
curl http://localhost:8000/api/v1/users -b cookies.txt | python3 -m json.tool

# Get settings
curl http://localhost:8000/api/v1/settings/general -b cookies.txt | python3 -m json.tool

# List plugins
curl http://localhost:8000/api/v1/plugins -b cookies.txt | python3 -m json.tool

# Get admin menu (dynamic, includes plugin pages)
curl http://localhost:8000/api/v1/admin/menu -b cookies.txt | python3 -m json.tool

# Activate a plugin
curl -X POST http://localhost:8000/api/v1/plugins/seo-pro/activate -b cookies.txt

# Check admin menu again — SEO Pro pages should now appear
curl http://localhost:8000/api/v1/admin/menu -b cookies.txt | python3 -m json.tool
```

---

## Step 6: Start the Admin Panel

Open a **new terminal** (keep Docker running in the first one):

```bash
cd admin
yarn dev
```

This starts the Vite dev server at:

```
http://localhost:3001/admin
```

### Configure API Proxy

The admin panel needs to talk to the backend. The `vite.config.ts` is already configured to proxy `/internal-api` to `http://localhost:8000`. For direct development without Nginx, you can also set the environment variable:

```bash
VITE_API_BASE_URL=http://localhost:8000 yarn dev
```

Or create `admin/.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

### Test the Admin Panel

1. Open `http://localhost:3001/admin` in your browser
2. You should see the **Login Page**
3. Enter: Username `admin`, Password `admin`
4. After login, you should see the **Dashboard** with:
   - Welcome card with your name
   - At a Glance stats
   - Quick Draft widget
   - Recent Posts
   - Site Health (all green)
   - Activity timeline

5. Click through the sidebar to test each page:
   - **Posts** → Post list with 4 demo posts, status tabs, search
   - **Posts → Add New** → Post editor with title, slug, content, categories
   - **Pages** → Page list with hierarchical display
   - **Media** → Media library with grid/list toggle
   - **Users** → User list with 3 demo users, role badges
   - **Posts → Categories** → Two-panel layout with add form + tree
   - **Posts → Tags** → Tag list with cloud visualization
   - **Plugins** → 3 demo plugins, activate/deactivate
   - **Themes** → Theme gallery with active theme card
   - **Settings** → Tabbed settings (General, Reading, Writing, Permalinks)

---

## Step 7: Test Plugin Dynamic Menu

This is the Phase 4 highlight — test that the sidebar updates when plugins activate/deactivate:

1. Go to **Plugins** page
2. Note the sidebar — it shows core items only
3. Click **Activate** on "SEO Pro" plugin
4. The sidebar should update to show "SEO Dashboard" under the plugin section
5. Click **Deactivate** on "SEO Pro"
6. The sidebar item should disappear

---

## Troubleshooting

### Backend won't start — "App module import failed"

Check that all Python files have correct syntax:

```bash
cd backend
python3 -c "from app.main import create_app; print('OK')"
```

If this fails, check the specific import error and fix the file.

### "Connection refused" on localhost:8000

Make sure Docker services are running:

```bash
docker compose -f docker-compose.local.yml ps
```

All services should show "Up (healthy)".

### Admin panel shows blank page

Check the browser console (F12 → Console) for errors. Common issues:
- CORS error → Set `VITE_API_BASE_URL=http://localhost:8000`
- 401 Unauthorized → Login session expired, log in again
- Network error → Backend isn't running

### Admin panel login fails

Verify the backend is responding:

```bash
curl http://localhost:8000/api/health
```

Then test login directly:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

### Docker running out of disk space

```bash
docker system prune -a    # WARNING: removes all unused images/containers
```

### Reset everything

```bash
docker compose -f docker-compose.local.yml down -v    # -v removes volumes (database data)
docker compose -f docker-compose.local.yml up --build  # fresh start
```

---

## Stopping Services

```bash
# Stop all services (preserves data)
docker compose -f docker-compose.local.yml down

# Stop and delete all data (fresh start)
docker compose -f docker-compose.local.yml down -v
```

---

## What's Working (Phases 1-4)

| Feature | Status | Test |
|---------|--------|------|
| Backend Health | ✅ | `curl localhost:8000/api/health` |
| Auth (login/logout) | ✅ | Login with admin/admin |
| Posts CRUD | ✅ | Create, edit, trash, restore posts |
| Pages CRUD | ✅ | Same as posts with hierarchy |
| Media Library | ✅ | Grid/list view, upload simulation |
| User Management | ✅ | Create users, assign roles |
| Categories | ✅ | Hierarchical tree, add/edit/delete |
| Tags | ✅ | Tag cloud, merge, add/edit/delete |
| Settings | ✅ | All 4 settings pages |
| Plugin Management | ✅ | Activate/deactivate, upload |
| Theme Management | ✅ | Activate themes, upload |
| Dynamic Sidebar | ✅ | Plugins add/remove menu items |
| Security Scanner | ✅ | Runs on plugin upload |
| RBAC | ✅ | Role-based capability checks |
| 66 API Endpoints | ✅ | All testable via Swagger UI |

---

## Next Steps

Once local testing is successful:

1. Push to GitHub
2. Move to **Phase 5** (NextJS Frontend with SSR)
3. Then Phases 6-8 (Page Builder, Advanced Features, Production)
