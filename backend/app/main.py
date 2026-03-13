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
from fastapi import FastAPI


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
    app = FastAPI(
        title="PyPress CMS",
        description="WordPress-equivalent CMS built with FastAPI",
        version="0.2.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    @app.get("/api/health")
    async def health_check():
        """
        Health check endpoint — Docker and Nginx use this to verify
        the backend is alive and can connect to dependencies.

        WordPress equivalent: Site Health check in wp-admin.
        """
        return {
            "status": "healthy",
            "service": "pypress-backend",
            "version": "0.2.0",
        }

    return app
