from typing import Any

from telegram._bot import BT
from telegram.ext import Application, CallbackContext
from telegram.ext._utils.types import BD, CD, UD

from src.database.configuration import get_session
from src.database.models import User


class CustomCallbackContext(CallbackContext[Any, Any, Any, Any]):
    user: User | None

    def __init__(
        self,
        application: "Application[BT, Any, UD, CD, BD, Any]",
        chat_id: int | None = None,
        user_id: int | None = None,
    ):
        super().__init__(application, chat_id, user_id)

        self.session = get_session()
        self.user = self.user_data.get("user") if self.user_data is not None else None

    def __del__(self) -> None:
        self.session.expunge_all()
        self.session.close()
