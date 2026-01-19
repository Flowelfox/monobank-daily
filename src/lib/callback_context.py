from typing import Any

from telegram._bot import BT
from telegram.ext import Application, CallbackContext
from telegram.ext._utils.types import BD, CCT, CD, UD

from src.database.configuration import get_session


class CustomCallbackContext(CallbackContext):
    def __init__(
        self: "CCT",
        application: "Application[BT, CCT, UD, CD, BD, Any]",
        chat_id: int = None,
        user_id: int = None,
    ):
        super().__init__(application, chat_id, user_id)

        self.session = get_session()
        self.user = self.user_data.get("user") if self.user_data is not None else None

    def __del__(self):
        self.session.expunge_all()
        self.session.close()
