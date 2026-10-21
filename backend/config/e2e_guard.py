"""Safety checks for the browser end-to-end environment (`config.settings.e2e`).

Pure functions with no Django imports, so they are unit tested without a database and run before anything
connects. The end-to-end suite may only ever touch one dedicated database on this machine.
"""

from urllib.parse import unquote, urlparse

E2E_DATABASE_NAME = "libraryhive_e2e"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def parse_postgres_url(url: str) -> dict:
    parsed = urlparse(url or "")
    return {
        "scheme": parsed.scheme,
        "host": (parsed.hostname or "").lower(),
        "port": parsed.port or 5432,
        "name": unquote(parsed.path.lstrip("/")),
    }


def e2e_database_errors(e2e_url: str, *, other_urls: tuple[str, ...] = ()) -> list[str]:
    """Reasons `e2e_url` must not be used. An empty list means it is the dedicated, local e2e database.

    `other_urls` are the normal development and production URLs (never printed); the e2e database must differ
    from every one of them even if someone names a normal database `libraryhive_e2e`.
    """
    if not e2e_url:
        return ["E2E_DATABASE_URL is not set. It must point at the dedicated e2e database."]
    target = parse_postgres_url(e2e_url)
    errors: list[str] = []
    if target["scheme"] not in {"postgres", "postgresql"}:
        errors.append("E2E_DATABASE_URL must be a PostgreSQL URL.")
    if target["host"] not in LOCAL_HOSTS:
        errors.append("The e2e database must be on this machine (localhost or 127.0.0.1).")
    if target["name"] != E2E_DATABASE_NAME:
        errors.append(f"The e2e database must be named exactly '{E2E_DATABASE_NAME}'.")
    for other in other_urls:
        if other and parse_postgres_url(other) == target:
            errors.append("The e2e database must not be the same database as DATABASE_URL.")
    return errors
