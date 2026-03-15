"""
PyPress CMS — Application Factory

WordPress equivalent: wp-settings.php + wp-load.php — bootstraps the entire
application in the correct sequence.

This is the entry point referenced by:
  - Gunicorn (production): gunicorn app.main:create_app --factory
  - Uvicorn (development): uvicorn app.main:create_app --factory --reload
  - Alembic (migrations): imports Base from app.core.models

NOTE: Your Phase 1 code (from pypress-phase1-complete.tar.gz) should be
merged into the app/ directory. This placeholder ensures the Docker image
builds and the entrypoint health check can import the module.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events — startup and shutdown.

    WordPress equivalent:
        Startup  → plugins_loaded + init + wp_loaded action hooks
        Shutdown → shutdown action hook
    """
    settings = get_settings()

    # ── Startup ──────────────────────────────────────────────────────────
    # TODO: Initialize database connection (Phase 1 merge)
    # TODO: Initialize Redis connection
    # TODO: Load active plugins (PluginLoader)
    # TODO: Fire 'pypress_loaded' hook

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    # TODO: Close database connections
    # TODO: Close Redis connections
    # TODO: Fire 'pypress_shutdown' hook


def create_app() -> FastAPI:
    """
    Application factory — creates and configures the FastAPI application.

    WordPress equivalent: This is like wp-settings.php which:
        1. Loads wp-config.php (our Settings/Pydantic)
        2. Connects to the database
        3. Loads active plugins (our PluginLoader)
        4. Sets up the active theme (our ThemeResolver)
        5. Registers rewrite rules (our API routers)

    Returns a fully configured FastAPI instance ready to handle requests.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        description="WordPress-equivalent CMS built with FastAPI",
        version=settings.APP_VERSION,
        docs_url="/api/docs" if settings.APP_DEBUG else None,
        redoc_url="/api/redoc" if settings.APP_DEBUG else None,
        openapi_url="/api/openapi.json" if settings.APP_DEBUG else None,
        lifespan=lifespan,
    )

    # ── CORS Middleware ──────────────────────────────────────────────────
    # In production, the admin panel runs on the same origin (via Nginx),
    # so CORS isn't needed. In development, the Vite dev server runs on
    # port 3001 while the backend runs on port 8000, so we need CORS.
    if settings.APP_ENV == "development":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:3000",   # NextJS frontend dev
                "http://localhost:3001",   # React admin dev
            ],
            allow_credentials=True,  # Required for httpOnly cookies
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )

    # ── Register API Routes ──────────────────────────────────────────────
    _register_routes(app)

    return app



def _register_routes(app: FastAPI) -> None:
    """
    Register all API routers under /api/v1.

    WordPress equivalent: WordPress's rewrite rules that map URLs to
    query handlers. In PyPress, each router is a module with its own
    endpoints, registered under a common /api/v1 prefix.
    """
    from app.core.api.v1.auth import router as auth_router
    from app.core.api.v1.posts import router as posts_router
    from app.core.api.v1.options import options_router, settings_router
    from app.core.api.v1.users import router as users_router
    from app.core.api.v1.taxonomies import router as taxonomies_router
    from app.core.api.v1.media import router as media_router
    from app.core.api.v1.comments import router as comments_router
    from app.core.api.v1.menus import router as menus_router

    # Main API router — all v1 endpoints live under /api/v1
    api_v1 = APIRouter(prefix="/api/v1")

    # Auth endpoints (Task 2.5)
    api_v1.include_router(auth_router)

    # Posts CRUD (Task 3.9a)
    api_v1.include_router(posts_router)

    # Options key-value store + structured settings (Task 3.9a)
    api_v1.include_router(options_router)
    api_v1.include_router(settings_router)

    # Users CRUD (Task 3.9b)
    api_v1.include_router(users_router)

    # Taxonomies — categories, tags, custom (Task 3.9b)
    api_v1.include_router(taxonomies_router)

    # Media library (Task 3.9c)
    api_v1.include_router(media_router)

    # Comments moderation (Task 3.9c)
    api_v1.include_router(comments_router)

    # Navigation menus (Task 3.9c)
    api_v1.include_router(menus_router)

    # Plugins & Themes (Phase 4 — Task 4.1 + 4.2)
    from app.core.api.v1.plugins_themes import plugins_router, themes_router
    api_v1.include_router(plugins_router)
    api_v1.include_router(themes_router)

    # Dynamic Admin Menu (Phase 4 — Task 4.4)
    from app.core.api.v1.admin_menu import router as admin_menu_router
    api_v1.include_router(admin_menu_router)

    app.include_router(api_v1)

    # ── Health Check ─────────────────────────────────────────────────────
    # Used by Docker HEALTHCHECK and Nginx to verify the backend is alive.
    # WordPress equivalent: Site Health check in wp-admin.
    @app.get("/api/health")
    async def health_check():
        return {
            "status": "healthy",
            "service": "pypress-backend",
            "version": settings.APP_VERSION if (settings := get_settings()) else "unknown",
        }
