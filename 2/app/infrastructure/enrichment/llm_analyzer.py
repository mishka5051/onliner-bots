import json
import logging

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class LlmEventAnalyzer:
    """Optional LLM layer for onliner-fit analysis when API key is configured."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return self._settings.llm_provider == "openai" and bool(self._settings.llm_api_key)

    async def analyze(self, *, title: str, page_text: str) -> dict[str, object] | None:
        if not self.enabled:
            return None

        prompt = (
            "Проанализируй мероприятие для инфопартнёрства Onliner (e-commerce, tech, lifestyle). "
            "Верни JSON: onliner_fit_score (0-100), theme_tags (array), partner_assessment (string).\n\n"
            f"Название: {title}\n\nТекст:\n{page_text[:6000]}"
        )
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self._settings.llm_api_key}"},
                    json={
                        "model": self._settings.llm_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception:
            logger.exception("LLM analysis failed")
            return None
