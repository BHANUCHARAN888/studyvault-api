|**Package**|**Purpose**|
|-----------|-----------|
|fastapi|Build the API|
|uvicorn|Run the API server|
|sqlalchemy|Communicate with PostgreSQL|
|psycopg\[binary]|PostgreSQL database driver|
|pydantic-settings|Load configuration from environment variables|
|python-dotenv|Read .env files|

### Structure
- core/config.py — application settings.
- db/database.py — PostgreSQL connection and SQLAlchemy setup.
- .env — private configuration, including the database password.
- main.py — FastAPI application entry point.

