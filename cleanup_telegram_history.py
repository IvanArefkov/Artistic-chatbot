from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from db.engine import engine
from db.models.base import TelegramChatMessage

logger = logging.getLogger(__name__)

# Create scheduler instance
scheduler = AsyncIOScheduler()


def cleanup_old_conversations():
    """Delete conversations older than 7 days"""
    try:
        with Session(engine) as session:
            cutoff_date = datetime.now() - timedelta(days=7)

            deleted_count = session.query(TelegramChatMessage) \
                .filter(TelegramChatMessage.date_created < cutoff_date) \
                .delete()

            session.commit()
            logger.info(f"Cleaned up {deleted_count} old messages")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


def init_scheduler():
    """Initialize and configure the scheduler"""
    scheduler.add_job(
        cleanup_old_conversations,
        'interval',
        hours=24,  # Run daily
        id='cleanup_conversations',
        replace_existing=True
    )
    logger.info("Scheduler jobs configured")


def start_scheduler():
    """Start the scheduler"""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    """Stop the scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
