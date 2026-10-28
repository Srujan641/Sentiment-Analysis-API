from app.connectors.app_store import AppStoreConnector
from app.connectors.firecrawl import FirecrawlConnector


def build_connectors(settings) -> dict:
    """All connectors, keyed by name. Unavailable ones are listed with what they need."""
    connectors = [
        AppStoreConnector(country=settings.store_country),
        FirecrawlConnector(api_key=settings.firecrawl_api_key),
    ]
    return {c.name: c for c in connectors}
