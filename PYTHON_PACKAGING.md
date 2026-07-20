# Production Python Packaging Flow

## Overview

The Postbox application uses a **wheel-based production deployment** with a clean separation between build and runtime.

### Build vs. Runtime Distinction

- **Build**: Poetry manages dependencies and builds a wheel (PEP 517)
- **Runtime**: The wheel is installed with pip into a virtual environment; **Poetry is not needed**

## The Flow

```
source code
    ↓
[Builder Stage] poetry build --format wheel
    ↓
[Builder Stage] pip install postbox-*.whl
    ↓
[Builder Stage] validate in /opt/venv
    ↓
[Runtime Stage] copy /opt/venv (autonomous)
    ↓
production: postbox-api runs directly
```

## Key Principles

1. **Poetry is a build tool only**: Used in the Docker builder stage to manage dependencies and create a wheel; not present in the runtime image.

2. **Wheel contains the complete package**: The wheel includes all Python code from `src/postbox/` and all required metadata.

3. **Runtime environment is autonomous**: The `/opt/venv` directory copied to the runtime image is completely self-contained:
   - All dependencies are installed
   - The `postbox` package is fully installed
   - `postbox-api` console script is executable
   - No references to the source tree (`/app/src`) exist
   - No editable installation is used

4. **External runtime data is explicitly copied**: Files outside the wheel are copied as distinct runtime resources:
   - `migrations/` — database migration scripts (Alembic)
   - `alembic.ini` — database configuration (not in wheel)

## File Locations in Runtime

| Path | Purpose | Source |
|------|---------|--------|
| `/opt/venv` | Virtual environment with installed wheel | Built in Docker |
| `/app/migrations` | Database migrations | Copied from repo |
| `/app/alembic.ini` | Alembic configuration | Copied from repo |
| `/app/web/` | Frontend (Node.js) | Copied from frontend builder |
| `/app/data/` (runtime) | SQLite database | Created at runtime |

**NOT in runtime**:
- `/app/src/` — Source code not needed after wheel installation
- Poetry — Not needed at runtime
- Build tools — Only in builder stage
- PYTHONPATH overrides — Not needed
- Editable installation hacks — Not used

## Alembic Configuration

The `alembic.ini` file has been updated to remove `prepend_sys_path`:

```ini
[alembic]
script_location = %(here)s/migrations
# NO prepend_sys_path — postbox is installed via pip, not source tree
```

This allows Alembic to import the installed `postbox` package directly without requiring source tree paths.

## Validation

Build-time checks confirm:

1. Wheel is built successfully
2. Wheel contains the `postbox` package
3. Wheel installs into `/opt/venv` with all dependencies
4. `import postbox` works from outside `/app` and `/opt/venv`
5. `postbox.__file__` points inside `/opt/venv` (not `/app/src`)
6. `postbox-api` console script is installed and callable

Runtime check:

- `postbox-api` resolves to `/opt/venv/bin/postbox-api`
- Imports work without source tree

## Testing

Run the packaging smoke test:

```bash
python tests/test_packaging.py
```

This verifies:
- Wheel can be built
- Wheel contains expected package files
- Wheel installs into a clean virtual environment
- Imports work in isolation (no repository dependency)

## Dependencies

All runtime dependencies are declared in `[tool.poetry.dependencies]` in `pyproject.toml`:

- **FastAPI** — Web framework
- **Uvicorn** — ASGI server (with standard extras)
- **SQLAlchemy** — ORM (with asyncio)
- **Alembic** — Database migrations (required at runtime for `alembic upgrade`)
- **aiosqlite** — Async SQLite driver
- **psycopg** — PostgreSQL driver (with binary extras)
- **python-dotenv** — Environment variable loading
- **PyJWT** — JWT token handling
- **httpx** — HTTP client (for Telegram API)

Development-only dependencies are in `[dependency-groups].dev` and are not installed in production.

## Backward Compatibility

This packaging approach is compatible with:

- **Local development**: `poetry install` + `poetry run postbox-api` still works
- **Docker**: Clean wheel-based builds
- **CI/CD**: `poetry build` + wheel testing
- **Alternative runtimes**: The wheel can be installed anywhere Python 3.14+ is available

## See Also

- `Dockerfile` — Build stages implementing this flow
- `pyproject.toml` — Package metadata and dependency declarations
- `tests/test_packaging.py` — Automated verification
