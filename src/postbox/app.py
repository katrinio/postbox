import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from postbox.config import Settings
from postbox.database import Database
from postbox.database.middleware import DatabaseSessionMiddleware
from postbox.handlers import routers
from postbox.logging import configure_logging

logger = logging.getLogger(__name__)


def create_dispatcher(session_factory: async_sessionmaker[AsyncSession]) -> Dispatcher:
    """Create the root dispatcher and register all bot routes."""
    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(DatabaseSessionMiddleware(session_factory))
    dispatcher.include_routers(*routers)
    return dispatcher


async def start_bot() -> None:
    """Configure and start the Telegram bot."""
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    database = Database(settings.database_url)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = create_dispatcher(database.session_factory)

    logger.info("Postbox is starting")
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await database.dispose()
        logger.info("Postbox has stopped")
