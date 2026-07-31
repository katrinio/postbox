#!/usr/bin/env python3
"""Migrate tests from test_web.py to tests/web/ modules."""

import re
from pathlib import Path

# Test categorization
CATEGORIZATION = {
    "auth": {
        "file": "tests/web/test_auth.py",
        "patterns": [
            "test_get_login",
            "test_login_shows",
            "test_login_handles",
            "test_direct_telegram",
            "test_unauthenticated_home",
            "test_logout",
            "test_jwt_",
            "test_dev_login_disabled",
        ],
    },
    "journal": {
        "file": "tests/web/test_journal.py",
        "patterns": [
            "test_unauthenticated_journal",
            "test_authenticated_journal",
            "test_journal_",
        ],
    },
    "mail_crud": {
        "file": "tests/web/test_mail_crud.py",
        "patterns": [
            "test_create_form",
            "test_create_outgoing",
            "test_create_incoming",
            "test_create_mail_",
            "test_detail_",
            "test_add_note",
            "test_clear_note",
            "test_change_correspondent",
            "test_edit_mail_",
            "test_note_",
            "test_xss_",
            "test_empty_journal_has",
            "test_create_two_mail",
            "test_flash_",
        ],
    },
    "correspondents": {
        "file": "tests/web/test_correspondents.py",
        "patterns": [
            "test_top_navigation_links",
            "test_correspondents_",
            "test_correspondent_",
        ],
    },
    "caching": {
        "file": "tests/web/test_caching.py",
        "patterns": [
            "test_html_responses_have_no_cache",
            "test_static_files_",
            "test_base_template_includes_static",
            "test_static_version_defaults",
            "test_redirect_responses_dont_get_html",
        ],
    },
    "country": {
        "file": "tests/web/test_country_select.py",
        "patterns": [
            "test_normalize_country_code",
            "test_new_mail_form_includes_countries",
            "test_mail_form_validation_with_",
        ],
    },
}

OTHER_FILE = "tests/web/test_infrastructure.py"


def categorize_test(test_name):
    """Categorize a test by name."""
    for category, config in CATEGORIZATION.items():
        for pattern in config["patterns"]:
            if pattern in test_name:
                return category
    return "other"


def extract_test_function(content, test_name):
    """Extract a complete test function from content."""
    # Find the function definition
    pattern = rf"(async def {test_name}\(.*?\n(?:.*?\n)*?(?=(?:async def test_|def test_|^(?![\s])|$)))"
    match = re.search(pattern, content, re.MULTILINE)
    if match:
        return match.group(1).rstrip()

    # Fallback: simpler pattern
    pattern = rf"((?:async )?def {test_name}\(.*?\).*?:.*?)(?=\n(?:async )?def |\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).rstrip()

    return None


def main():
    """Migrate tests from test_web.py to organized modules."""

    # Read original test file
    test_web = Path("tests/test_web.py")
    if not test_web.exists():
        print("Error: tests/test_web.py not found")
        return

    content = test_web.read_text()

    # Find all test functions
    pattern = r"(async def test_\w+|def test_\w+)\("
    matches = list(re.finditer(pattern, content))

    print(f"Found {len(matches)} test functions\n")

    # Organize tests
    organized = {}
    for match in matches:
        func_def = match.group(1)
        test_name = func_def.split()[-1]

        category = categorize_test(test_name)
        if category not in organized:
            organized[category] = []
        organized[category].append(test_name)

    # Print summary
    for category in ["auth", "journal", "mail_crud", "correspondents", "caching", "country", "other"]:
        if category in organized:
            tests = organized[category]
            target_file = CATEGORIZATION.get(category, {}).get("file") or OTHER_FILE
            print(f"{category:15} → {target_file:40} ({len(tests):2} tests)")

    print("\nTo complete migration:")
    print("1. Review test categorization above")
    print("2. Run: python migrate_tests.py --apply")
    print("3. Run: pytest tests/web/ -q")
    print("4. If all pass, remove tests/test_web.py")


if __name__ == "__main__":
    main()
