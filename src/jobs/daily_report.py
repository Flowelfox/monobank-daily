import datetime
import logging

import pytz
from sqlalchemy import select
from telegram.error import BadRequest, Forbidden

from src.database.configuration import get_session
from src.database.models import User
from src.lib.helpers import format_money
from src.services.monobank import MonobankAPIError, get_daily_spending
from src.settings import TIMEZONE

logger = logging.getLogger(__name__)


def start_daily_report_job(job_queue):
    stop_daily_report_job(job_queue)

    job_queue.run_repeating(send_daily_reports, interval=60, first=0, name="daily_report_job")
    logger.info(f"Daily report job scheduled to run every minute ({TIMEZONE})")


def stop_daily_report_job(job_queue):
    for job in job_queue.get_jobs_by_name("daily_report_job"):
        job.schedule_removal()
        logger.info("Daily report job stopped")


async def send_daily_reports(context):
    tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(tz)
    current_hour = now.hour
    current_minute = now.minute

    session = get_session()

    try:
        stmt = select(User).where(
            User.is_active,
            User.has_token,
            User.report_hour == current_hour,
            User.report_minute == current_minute,
        )
        users = session.scalars(stmt).all()

        if not users:
            return

        logger.info(f"Sending daily reports to {len(users)} users at {current_hour:02d}:{current_minute:02d}")

        for user in users:
            if not user.selected_accounts:
                logger.debug(f"User {user.id} has no selected accounts, skipping")
                continue

            try:
                await send_report_to_user(context, user)
            except Exception as e:
                logger.error(f"Error sending report to user {user.id}: {e}")
                continue

    finally:
        session.close()


async def send_report_to_user(context, user: User):
    _ = user.translator

    tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    from_ts = int(start_of_day.timestamp())
    to_ts = int(now.timestamp())

    try:
        result = await get_daily_spending(
            user.monobank_token, user.selected_accounts, from_ts, to_ts, user.language_code or "uk"
        )
    except MonobankAPIError as e:
        logger.warning(f"Failed to get spending for user {user.id}: {e}")
        return

    date_str = now.strftime("%d.%m.%Y")

    text = _("📊 Daily Report for {date}\n\n").format(date=date_str)

    if result["total_spending"] > 0:
        text += _("💰 Total spent: -{amount} ₴\n\n").format(amount=format_money(result["total_spending"]))

        if result["categories"]:
            text += _("📁 By category:\n")
            for cat in result["categories"]:
                text += f"{cat['name']}: -{format_money(cat['amount'])} ₴\n"
    else:
        text += _("No spending today! 🎉\n")

    if result["total_income"] > 0:
        text += _("\n📥 Income: +{amount} ₴").format(amount=format_money(result["total_income"]))

    text += _("\n\n📱 Transactions: {count}").format(count=result["transaction_count"])

    try:
        await context.bot.send_message(chat_id=user.id, text=text, parse_mode="HTML")
        logger.info(f"Report sent to user {user.id}")
    except Forbidden:
        logger.warning(f"User {user.id} blocked the bot")
        session = get_session()
        try:
            with session.begin():
                stmt = select(User).where(User.id == user.id)
                db_user = session.scalar(stmt)
                if db_user:
                    db_user.deactivate()
                    session.add(db_user)
        finally:
            session.close()
    except BadRequest as e:
        logger.error(f"Failed to send message to user {user.id}: {e}")
