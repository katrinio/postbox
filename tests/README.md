# Test Structure

Tests are organized by domain to keep modules focused and easy to understand.

## Top-level tests

- `test_api.py` - FastAPI app creation and setup
- `test_auth_hub.py` - Hub Bot authentication and JWT verification  
- `test_config.py` - Configuration and environment loading
- `test_migrations.py` - Database migrations and schema
- `test_models.py` - ORM models and database logic
- `test_packaging.py` - Package metadata and distribution
- `test_sqlite_parity.py` - SQLite/PostgreSQL compatibility

## Web tests (`tests/web/`)

Organized by feature. Each module tests one aspect of the web app.

### `conftest.py`

Shared fixtures and utilities for all web tests:
- `build_settings()` - Create test WebSettings
- `create_hub_auth_url()` - Generate Hub JWT tokens
- `login()` - Authenticate and get user_id
- `get_csrf()` - Retrieve CSRF token from cookies
- `web_app` - FastAPI app fixture
- `web_client` - Authenticated HTTP client fixture

### Feature modules

- **`test_auth.py`** - Authentication flow
  - Dev login mode
  - Session management
  - CSRF protection
  - Logout

- **`test_country_select.py`** - Country dropdown autocomplete
  - ISO code validation with pycountry
  - Format and existence checks
  - UI elements (inputs, dropdown)
  - Form submission with country codes

- **`test_caching.py`** - HTTP caching and versioning
  - Cache-Control headers on HTML
  - Static asset caching with version query params
  - Automatic git SHA-based versioning
  - Cache invalidation

- **`test_journal.py`** *(planned)* - Journal view and filtering
  - Pagination
  - Filtering by direction, correspondent, country
  - Sorting

- **`test_mail_crud.py`** *(planned)* - Mail create/read/update
  - Create mail with validation
  - Edit mail and geography
  - Delete operations

- **`test_correspondents.py`** *(planned)* - Correspondent management
  - Create correspondent
  - Update correspondent
  - List with stats

## Running tests

Run all tests:
```bash
pytest
```

Run tests in a specific module:
```bash
pytest tests/web/test_country_select.py
```

Run specific test class:
```bash
pytest tests/web/test_country_select.py::TestCountryValidation
```

Run with verbose output:
```bash
pytest -v
```

Watch mode (requires pytest-watch):
```bash
ptw
```

## Writing new tests

1. Determine which module or create a new one
2. Import fixtures from `conftest.py` if needed
3. Use descriptive test class names (e.g., `TestCountryValidation`)
4. Use descriptive test method names (e.g., `test_valid_iso_codes`)
5. Add docstrings explaining what is being tested

Example:

```python
class TestMyFeature:
    """Tests for my new feature."""
    
    async def test_happy_path(self, web_client) -> None:
        """Feature should work correctly with valid input."""
        client, user_id = web_client
        response = await client.get("/my-endpoint")
        assert response.status_code == 200
```
