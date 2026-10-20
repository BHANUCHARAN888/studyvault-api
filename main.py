from fastapi import FastAPI
from sqlalchemy import text

from app.db.database import Base, engine
from app.models import User, Subject, Document
from app.routers.auth import router as auth_router
from app.routers.documents import router as documents_router


def create_app(create_tables: bool = False) -> FastAPI:
    app = FastAPI(title="StudyVault API")

    if create_tables:
        Base.metadata.create_all(bind=engine)

    app.include_router(auth_router)
    app.include_router(documents_router)

    @app.get("/health")
    def health_check():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))

            return {
                "status": "healthy",
                "database": "connected",
            }
        except Exception:
            return {
                "status": "unhealthy",
                "database": "disconnected",
            }

    return app


app = create_app()
