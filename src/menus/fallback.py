from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import Update

from src.lib.helpers import prepare_user
from src.lib.messages import delete_interface, delete_user_message

if TYPE_CHECKING:
    from src.lib.callback_context import CustomCallbackContext

logger = logging.getLogger(__name__)


async def goto_start(update: Update, context: CustomCallbackContext):
    logger.debug(f"goto_start called, callback_data={update.callback_query.data if update.callback_query else 'N/A'}")
    await delete_user_message(update)
    await prepare_user(update, context)
    await delete_interface(context)

    if update.callback_query:
        await update.callback_query.answer()

    start_menu = context.bot_data.get("start_menu")
    if start_menu is None:
        from src.menus.start import StartMenu

        start_menu = StartMenu(application=context.application)

    handler = start_menu.handler
    key = handler._get_key(update)
    handler._conversations[key] = start_menu.States.DEFAULT

    await start_menu.send_message(context)
