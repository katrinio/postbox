# Web Tests Structure

Each module focuses on a specific aspect of the web application.

## Modules

### test_auth.py
- Login page rendering
- Authentication flow (Hub Bot JWT)
- Session cookies and CSRF protection  
- Logout and session clearing
- JWT validation and token expiry

### test_journal.py
- Journal (mail list) access control
- Filtering by direction, correspondent, country
- Pagination
- Empty state
- Sorting and display formatting
- Geography rendering
- Data isolation per user

### test_mail_crud.py
- Creating mail (outgoing/incoming)
- Required fields validation
- Date validation (no future dates)
- Geography (city/country) input
- Editing mail details (note, correspondent, geography)
- Mail detail access control
- CSRF protection
- XSS escaping

### test_correspondents.py
- List correspondents with mail counts
- Correspondent detail page
- Mail history display
- Correspondent notes (add, update, delete)
- Note length validation
- Access control per user

### test_caching.py  
- Cache-Control headers on HTML (no-cache)
- Cache-Control headers on static assets (long cache with version)
- Static asset versioning with git SHA
- Version query parameters (?v=...)
- Browser cache invalidation on deploy

### test_country_select.py
- ISO 3166-1 alpha-2 code validation with pycountry
- Format validation (must be 2 ASCII letters)
- Form submission with country codes
- Dropdown UI elements
- Autocomplete functionality
