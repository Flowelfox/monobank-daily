import logging
import pprint
import traceback

from telegram.ext import ApplicationBuilder, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from src.database.configuration import engine
from src.database.models import Base
from src.jobs.daily_report import start_daily_report_job, stop_daily_report_job
from src.lib.callback_context import CustomCallbackContext
from src.menus.fallback import goto_start
from src.menus.start import StartMenu
from src.settings import BOT_TOKEN

logger = logging.getLogger(__name__)


async def error(update, context):
    if update:
        pp = pprint.PrettyPrinter(indent=4)
        logger.error(f'Update "{pp.pformat(update.to_dict())}" caused error \n{context.error}"')
    traceback.print_exc()


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Please set it in .env file.")
        return

    Base.metadata.create_all(engine)
    logger.info("Database tables created")

    context_types = ContextTypes(context=CustomCallbackContext)
    application = ApplicationBuilder().token(BOT_TOKEN).context_types(context_types).build()

    start_menu = StartMenu(application=application)

    application.add_handler(start_menu.handler)
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE, goto_start))
    application.add_handler(CallbackQueryHandler(goto_start))
    application.add_error_handler(error)

    start_daily_report_job(application.job_queue)

    logger.info("Bot started")
    application.run_polling(allowed_updates=["message", "edited_message", "callback_query"])

    stop_daily_report_job(application.job_queue)


if __name__ == "__main__":
    main()
