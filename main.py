from fastapi import FastAPI
from sqlalchemy import text

from app.db.database import Base, engine
from app.models import User, Subject, Document  # Register models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="StudyVault API")


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
