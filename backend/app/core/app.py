"""
PyPress App Factory — bootstraps the entire application.

Equivalent to WordPress's wp-settings.php + wp-load.php.
Application Factory pattern creates a fully configured FastAPI instance.
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.core.config import get_settings
from backend.core.database import init_db, close_db
from backend.core.hooks import hooks, CoreHooks
from backend.core.exceptions import PyPressError
from backend.plugins.loader import PluginLoader

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME, version=settings.APP_VERSION,
        description="PyPress CMS — WordPress-compatible, Python-powered",
        docs_url="/api/docs", redoc_url="/api/redoc",
        openapi_url="/api/openapi.json", lifespan=_lifespan,
    )

    # CORS — configured for internal Docker communication
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,  # Required for cookie-based auth
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-CSRF-Token"],
    )

    @app.exception_handler(PyPressError)
    async def pypress_error_handler(request: Request, exc: PyPressError):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(status_code=500, content={
            "error": "internal_error",
            "message": "Internal server error" if not settings.DEBUG else str(exc),
        })

    _register_routes(app)
    return app


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("=" * 50)
    logger.info("PyPress %s starting...", settings.APP_VERSION)

    # Step 1: Database
    await init_db()
    # Step 2: Init hook
    await hooks.do_action(CoreHooks.PYPRESS_INIT)
    # Step 3: Plugins
    loader = PluginLoader()
    loader.discover_all()
    active = settings.AUTO_ACTIVATE_PLUGINS or ["hello_world"]
    loaded = await loader.load_active_plugins(active)
    app.state.plugin_loader = loader
    app.state.loaded_plugins = loaded
    logger.info("Loaded %d plugins: %s", len(loaded), list(loaded.keys()))

    # Register plugin routes on the v1 router
    if hasattr(app.state, "api_v1_router"):
        loader.register_plugin_routes(app.state.api_v1_router)

    # Step 4: Theme
    await hooks.do_action(CoreHooks.AFTER_SETUP_THEME)
    # Step 5: Ready
    await hooks.do_action(CoreHooks.PYPRESS_LOADED)
    logger.info("PyPress is ready!")

    yield

    logger.info("PyPress shutting down...")
    await hooks.do_action(CoreHooks.PYPRESS_SHUTDOWN)
    await close_db()


def _register_routes(app: FastAPI) -> None:
    from fastapi import APIRouter
    from backend.core.api.v1.posts import router as posts_router
    from backend.core.api.v1.auth import router as auth_router

    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(auth_router)
    api_v1.include_router(posts_router)
    # Future: users, taxonomies, comments, media, options, menus, themes, plugins

    app.state.api_v1_router = api_v1
    app.include_router(api_v1)

    @app.get("/api/health")
    async def health_check():
        return {"status": "healthy", "app": get_settings().APP_NAME,
                "version": get_settings().APP_VERSION}


app = create_app()
