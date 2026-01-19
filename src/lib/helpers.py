import gettext
import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.database.models import User
from src.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)


def available_languages():
    locales_folder = PROJECT_ROOT / "locales"
    if locales_folder.exists():
        languages = [d.name for d in locales_folder.iterdir() if d.is_dir()]
    else:
        languages = []
    if "en" not in languages:
        languages.append("en")

    return languages


def translator(language_code="en"):
    translation = gettext.translation("messages", str(PROJECT_ROOT / "locales"), languages=[language_code], fallback=True)
    return translation.gettext


def ntranslator(language_code="en"):
    translation = gettext.translation("messages", str(PROJECT_ROOT / "locales"), languages=[language_code], fallback=True)
    return translation.ngettext


async def prepare_user(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str | None = None) -> User:
    if context.user_data.get("user", False) and context.user_data.get("_", False):
        user = context.user_data["user"]
        user.activate()
        user.save()
        return user

    with context.session.begin():
        stmt = select(User).where(User.id == update.effective_user.id)
        user = context.session.scalar(stmt)
        tuser = update.effective_user
        if lang is None and tuser.language_code:
            lang = tuser.language_code
        elif lang is None and tuser.language_code is None:
            lang = "uk"

        if not user:
            user = User()
            user.id = tuser.id
            user.first_name = tuser.first_name
            user.last_name = tuser.last_name
            user.username = tuser.username
            user.language_code = lang
            logger.info(f'New user joined bot: "{user.name}".')

        user.first_name = tuser.first_name
        user.last_name = tuser.last_name
        user.username = tuser.username
        user.activate()

        context.session.add(user)
        context.session.flush()
        user = context.session.scalar(stmt)
        context.session.expunge(user)

    context.user_data["user"] = user
    context.user = user
    return user


def group_buttons(buttons: list, group_size: int = 2) -> list[list]:
    group = []
    subgroup = []
    for button in buttons:
        subgroup.append(button)
        if len(subgroup) == group_size:
            group.append(subgroup)
            subgroup = []

    if subgroup:
        group.append(subgroup)

    return group


def format_money(amount: int) -> str:
    amount_uah = amount / 100
    if amount_uah < 0:
        return f"-{abs(amount_uah):,.2f}".replace(",", " ")
    return f"{amount_uah:,.2f}".replace(",", " ")
