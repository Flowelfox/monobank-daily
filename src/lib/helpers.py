from __future__ import annotations

import gettext
import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from telegram import Update

from src.database.models import User
from src.settings import PROJECT_ROOT

if TYPE_CHECKING:
    from src.lib.callback_context import CustomCallbackContext

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
    translation = gettext.translation(
        "messages", str(PROJECT_ROOT / "locales"), languages=[language_code], fallback=True
    )
    return translation.gettext


def ntranslator(language_code="en"):
    translation = gettext.translation(
        "messages", str(PROJECT_ROOT / "locales"), languages=[language_code], fallback=True
    )
    return translation.ngettext


async def prepare_user(update: Update, context: CustomCallbackContext, lang: str | None = None) -> User:
    if context.user_data and context.user_data.get("user", False) and context.user_data.get("_", False):
        user: User = context.user_data["user"]
        user.activate()
        user.save()
        return user

    tuser = update.effective_user
    if tuser is None:
        raise ValueError("No effective user in update")

    with context.session.begin():
        stmt = select(User).where(User.id == tuser.id)
        user = context.session.scalar(stmt)
        if lang is None:
            lang = tuser.language_code if tuser.language_code else "uk"

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
        if user is None:
            raise ValueError("Failed to get user from database")
        context.session.expunge(user)

    if context.user_data is not None:
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
