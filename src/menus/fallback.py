from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import Update

from src.lib.helpers import prepare_user
from src.lib.messages import delete_interface

if TYPE_CHECKING:
    from src.lib.callback_context import CustomCallbackContext

logger = logging.getLogger(__name__)


async def goto_start(update: Update, context: CustomCallbackContext):
    logger.debug(f"goto_start called, callback_data={update.callback_query.data if update.callback_query else 'N/A'}")
    await prepare_user(update, context)
    await delete_interface(context)

    if update.callback_query:
        await update.callback_query.answer()

    from src.menus.start import StartMenu

    start_menu = StartMenu(application=context.application)
    return await start_menu.entry(update, context)
