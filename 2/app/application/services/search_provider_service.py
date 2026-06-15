from app.application.ports.search_provider import SearchProvider
from app.core.config import Settings
from app.core.exceptions import SearchApiKeyMissingError
from app.infrastructure.search.fake_provider import FakeSearchProvider
from app.infrastructure.search.searxng_provider import SearXngSearchProvider
from app.infrastructure.search.serpapi_provider import SerpApiSearchProvider


class SearchProviderService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._provider: SearchProvider | None = None

    def get_provider(self) -> SearchProvider:
        if self._provider is not None:
            return self._provider

        if self._settings.search_provider == "serpapi":
            if not self._settings.serpapi_api_key:
                raise SearchApiKeyMissingError()
            self._provider = SerpApiSearchProvider(api_key=self._settings.serpapi_api_key)
        elif self._settings.search_provider == "searxng":
            self._provider = SearXngSearchProvider(base_url=self._settings.searxng_base_url)
        else:
            self._provider = FakeSearchProvider()

        return self._provider
