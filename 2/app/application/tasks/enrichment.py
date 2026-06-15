import logging

from app.infrastructure.db.session import async_session_factory
from app.infrastructure.factory import create_enrichment_pipeline

logger = logging.getLogger(__name__)


async def run_pending_enrichment(*, limit: int = 200) -> dict[str, int]:
    async with async_session_factory() as session:
        pipeline = create_enrichment_pipeline(session)
        try:
            result = await pipeline.process_all_pending(limit=limit)
            await session.commit()
            logger.info("Background enrichment finished: %s", result)
            return result
        except Exception:
            await session.rollback()
            logger.exception("Background enrichment failed")
            raise
