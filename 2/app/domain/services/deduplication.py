import hashlib
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

UTM_PARAMS = frozenset(
    {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id"}
)


class DeduplicationService:
    def normalize_url(self, url: str) -> str:
        parsed = urlparse(url.strip())
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]

        filtered_params = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in UTM_PARAMS
        ]
        filtered_params.sort()
        query = urlencode(filtered_params)

        path = parsed.path.rstrip("/") or "/"
        normalized = urlunparse(
            (
                parsed.scheme.lower() if parsed.scheme else "https",
                netloc,
                path,
                "",
                query,
                "",
            )
        )
        return normalized

    def compute_duplicate_key(self, url: str) -> str:
        normalized = self.normalize_url(url)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
