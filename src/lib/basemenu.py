import functools
import logging
import re
from abc import ABC
from enum import Enum
from inspect import signature

from telegram import Update
from telegram.ext import BaseHandler, CallbackContext, ContextTypes, ConversationHandler


class States(Enum):
    DEFAULT = 1


def pascal_to_snake(name: str):
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()


class BaseMenu(ABC):
    allow_reentry = True

    def __init__(self, parent=None, application=None):
        self.parent = parent

        if application is None:
            menu = self
            self.application = None
            while menu.parent is not None:
                if menu.parent and menu.parent.application:
                    self.application = menu.parent.application
                    break
                else:
                    menu = menu.parent
            if self.application is None:
                raise ValueError("`application` must be passed at least to root menu.")
        else:
            self.application = application

        if not hasattr(self, "States"):
            self.States = States

        if not hasattr(self.States, "DEFAULT"):
            self.States = Enum("States", [m.name for m in self.States] + ["DEFAULT"])

        self.bot = self.application.bot
        self.logger = logging.getLogger(self.__class__.__name__)
        self.menu_name = pascal_to_snake(self.__class__.__name__)
        self.handler = self.get_handler()
        self.update_queue = self.application.update_queue
        self.job_queue = self.application.job_queue

    def conv_fallback(self, context: ContextTypes.DEFAULT_TYPE):
        user_data = context.user_data
        if "keyboard" in user_data and user_data["keyboard"]:
            self.bot.send_message(
                chat_id=user_data["user"].id,
                text="Something went wrong, try again later.",
                reply_markup=user_data["keyboard"],
            )
            del user_data["keyboard"]
        else:
            self.bot.send_message(chat_id=user_data["user"].id, text="Something went wrong, try again later.")

        return ConversationHandler.END

    def entry_points(self) -> list[BaseHandler]:
        raise NotImplementedError

    def states(self) -> dict[Enum, list[BaseHandler]]:
        return {}

    def fallbacks(self) -> list[BaseHandler]:
        return []

    def get_handler(self):
        return ConversationHandler(
            entry_points=self.entry_points(),
            states=self.states(),
            fallbacks=self.fallbacks(),
            allow_reentry=self.allow_reentry,
            name=self.menu_name,
        )

    def send_message(self, context: ContextTypes.DEFAULT_TYPE):
        raise NotImplementedError

    async def back_to_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.send_message(context)
        if update.callback_query and update.callback_query.id != 0:
            await update.callback_query.answer()
        return self.States.DEFAULT

    async def back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.parent.send_message(context)
        if update.callback_query and update.callback_query.id != 0:
            await update.callback_query.answer()
        return ConversationHandler.END

    def __getattribute__(self, item):
        attr = super().__getattribute__(item)

        if callable(attr):
            sig = signature(attr)
            if (
                sig
                and "update" in sig.parameters
                and "context" in sig.parameters
                and sig.parameters["update"].annotation is Update
                and sig.parameters["context"].annotation is CallbackContext
            ):

                def update_state(func):
                    @functools.wraps(func)
                    def wrapper(*args, **kwargs):
                        value = func(*args, **kwargs)
                        for arg in args:
                            if isinstance(arg, CallbackContext):
                                context = arg
                                if self.menu_name not in context.user_data:
                                    context.user_data[self.menu_name] = {}

                                context.user_data[self.menu_name]["_state"] = value
                        return value

                    return wrapper

                return update_state(attr)
        return attr

    def get_current_state(self, context: ContextTypes.DEFAULT_TYPE):
        if self.menu_name in context.user_data:
            return context.user_data[self.menu_name].get("_state", None)
