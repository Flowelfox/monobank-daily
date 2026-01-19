from enum import Enum

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import BaseHandler, CallbackQueryHandler, MessageHandler, filters

from src.database.models import User
from src.lib.basemenu import BaseMenu
from src.lib.helpers import group_buttons
from src.lib.messages import delete_user_message, send_or_edit
from src.services.monobank import MonobankAPIError, MonobankService, format_account_name


class States(Enum):
    WAITING_TOKEN = 1
    SELECT_ACCOUNTS = 2


SUPPORTED_LANGUAGES = [
    ("uk", "🇺🇦 Українська"),
    ("en", "🇬🇧 English"),
]


class SettingsMenu(BaseMenu):
    class States(Enum):
        DEFAULT = 0
        WAITING_TOKEN = 1
        SELECT_ACCOUNTS = 2
        SELECT_HOUR = 3
        SELECT_MINUTE = 4
        SELECT_LANGUAGE = 5

    async def entry(self, update, context):
        if self.menu_name not in context.user_data:
            context.user_data[self.menu_name] = {}

        if update.callback_query:
            await update.callback_query.answer()

        await self.send_message(context)
        return self.States.DEFAULT

    async def send_message(self, context):
        user = context.user_data["user"]
        _ = user.translator

        has_token = user.monobank_token is not None
        token_status = _("✅ Token set") if has_token else _("❌ Token not set")

        accounts_count = len(user.selected_accounts)
        if accounts_count > 0:
            accounts_status = _("✅ {count} account(s) selected").format(count=accounts_count)
        else:
            accounts_status = _("❌ No accounts selected")

        report_time = f"{user.report_hour:02d}:{user.report_minute:02d}"

        language_name = next(
            (name for code, name in SUPPORTED_LANGUAGES if code == user.language_code), user.language_code
        )

        text = _(
            "⚙️ <b>Settings</b>\n\n"
            "🔑 Token: {token_status}\n"
            "💳 Accounts: {accounts_status}\n"
            "🕐 Report time: {report_time}\n"
            "🌐 Language: {language}"
        ).format(
            token_status=token_status, accounts_status=accounts_status, report_time=report_time, language=language_name
        )

        buttons = []

        if has_token:
            buttons.append([InlineKeyboardButton(_("🔄 Change token"), callback_data="set_token")])
            buttons.append([InlineKeyboardButton(_("💳 Select accounts"), callback_data="select_accounts")])
            buttons.append([InlineKeyboardButton(_("🕐 Change report time"), callback_data="set_time")])
            buttons.append([InlineKeyboardButton(_("🗑 Remove token"), callback_data="remove_token")])
        else:
            buttons.append([InlineKeyboardButton(_("➕ Add token"), callback_data="set_token")])

        buttons.append([InlineKeyboardButton(_("🌐 Change language"), callback_data="select_language")])
        buttons.append([InlineKeyboardButton(_("◀️ Back"), callback_data="start")])

        await send_or_edit(
            context, chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML"
        )

    async def request_token(self, update, context):
        user = context.user_data["user"]
        _ = user.translator

        text = _(
            "🔑 <b>Enter Monobank Token</b>\n\n"
            "Get your token:\n"
            "1. Open Monobank app\n"
            "2. Go to Settings → API\n"
            "3. Create a token\n"
            "4. Send the token here\n\n"
            "Token format: uXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        )

        buttons = [[InlineKeyboardButton(_("❌ Cancel"), callback_data="settings")]]

        await send_or_edit(
            context, chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML"
        )

        if update.callback_query:
            await update.callback_query.answer()

        return self.States.WAITING_TOKEN

    async def process_token(self, update, context):
        user = context.user_data["user"]
        _ = user.translator

        token = update.message.text.strip()

        await delete_user_message(update)

        if not token.startswith("u") or len(token) < 40:
            text = _(
                "❌ Invalid token format. Please try again.\n\nToken should start with 'u' and be at least 40 characters."
            )
            buttons = [[InlineKeyboardButton(_("❌ Cancel"), callback_data="settings")]]
            await send_or_edit(context, chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
            return self.States.WAITING_TOKEN

        service = MonobankService(token)
        try:
            is_valid = await service.validate_token()
            if not is_valid:
                text = _("❌ Invalid token. Please check and try again.")
                buttons = [[InlineKeyboardButton(_("❌ Cancel"), callback_data="settings")]]
                await send_or_edit(context, chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
                return self.States.WAITING_TOKEN
        except MonobankAPIError as e:
            text = _("❌ Error validating token: {error}").format(error=e.message)
            buttons = [[InlineKeyboardButton(_("❌ Cancel"), callback_data="settings")]]
            await send_or_edit(context, chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
            return self.States.WAITING_TOKEN

        with context.session.begin():
            stmt = select(User).where(User.id == user.id)
            db_user = context.session.scalar(stmt)
            db_user.monobank_token = token
            db_user.selected_accounts = []
            context.session.add(db_user)
            context.session.flush()
            context.session.expunge(db_user)
            context.user_data["user"] = db_user

        text = _("✅ Token saved successfully!\n\nNow select accounts to track.")
        buttons = [
            [InlineKeyboardButton(_("💳 Select accounts"), callback_data="select_accounts")],
            [InlineKeyboardButton(_("◀️ Back to settings"), callback_data="settings")],
        ]
        await send_or_edit(context, chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(buttons))

        return self.States.DEFAULT

    async def remove_token(self, update, context):
        user = context.user_data["user"]
        _ = user.translator

        with context.session.begin():
            stmt = select(User).where(User.id == user.id)
            db_user = context.session.scalar(stmt)
            db_user.monobank_token = None
            db_user.selected_accounts = []
            context.session.add(db_user)
            context.session.flush()
            context.session.expunge(db_user)
            context.user_data["user"] = db_user

        if update.callback_query:
            await update.callback_query.answer(_("Token removed"))

        await self.send_message(context)
        return self.States.DEFAULT

    async def show_accounts(self, update, context):
        user = context.user_data["user"]
        _ = user.translator

        if self.menu_name not in context.user_data:
            context.user_data[self.menu_name] = {}

        if not user.monobank_token:
            if update.callback_query:
                await update.callback_query.answer(_("Please add token first"), show_alert=True)
            return self.States.DEFAULT

        if update.callback_query:
            await update.callback_query.answer(_("Loading accounts..."))

        service = MonobankService(user.monobank_token)
        try:
            accounts = await service.get_accounts()
        except MonobankAPIError as e:
            text = _("❌ Error loading accounts: {error}").format(error=e.message)
            buttons = [[InlineKeyboardButton(_("◀️ Back"), callback_data="settings")]]
            await send_or_edit(context, chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
            return self.States.DEFAULT

        context.user_data[self.menu_name]["accounts"] = accounts

        text = _("💳 <b>Select accounts</b>\n\nTap to toggle selection:")

        buttons = []
        selected = user.selected_accounts

        for account in accounts:
            account_id = account.get("id")
            account_name = format_account_name(account)
            is_selected = account_id in selected
            prefix = "✅ " if is_selected else "⬜ "
            buttons.append(InlineKeyboardButton(prefix + account_name, callback_data=f"toggle_account_{account_id}"))

        buttons = group_buttons(buttons, 1)
        buttons.append([InlineKeyboardButton(_("💾 Save"), callback_data="save_accounts")])
        buttons.append([InlineKeyboardButton(_("◀️ Cancel"), callback_data="settings")])

        await send_or_edit(
            context, chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML"
        )

        return self.States.SELECT_ACCOUNTS

    async def toggle_account(self, update, context):
        user = context.user_data["user"]
        _ = user.translator

        account_id = update.callback_query.data.replace("toggle_account_", "")

        selected = list(user.selected_accounts)
        if account_id in selected:
            selected.remove(account_id)
        else:
            selected.append(account_id)

        with context.session.begin():
            stmt = select(User).where(User.id == user.id)
            db_user = context.session.scalar(stmt)
            db_user.selected_accounts = selected
            context.session.add(db_user)
            context.session.flush()
            context.session.expunge(db_user)
            context.user_data["user"] = db_user

        await update.callback_query.answer()

        accounts = context.user_data[self.menu_name].get("accounts", [])

        text = _("💳 <b>Select accounts</b>\n\nTap to toggle selection:")

        buttons = []
        for account in accounts:
            acc_id = account.get("id")
            account_name = format_account_name(account)
            is_selected = acc_id in selected
            prefix = "✅ " if is_selected else "⬜ "
            buttons.append(InlineKeyboardButton(prefix + account_name, callback_data=f"toggle_account_{acc_id}"))

        buttons = group_buttons(buttons, 1)
        buttons.append([InlineKeyboardButton(_("💾 Save"), callback_data="save_accounts")])
        buttons.append([InlineKeyboardButton(_("◀️ Cancel"), callback_data="settings")])

        await send_or_edit(
            context, chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML"
        )

        return self.States.SELECT_ACCOUNTS

    async def save_accounts(self, update, context):
        user = context.user_data["user"]
        _ = user.translator

        count = len(user.selected_accounts)
        if count > 0:
            await update.callback_query.answer(_("{count} account(s) saved").format(count=count))
        else:
            await update.callback_query.answer(_("No accounts selected"), show_alert=True)
            return self.States.SELECT_ACCOUNTS

        await self.send_message(context)
        return self.States.DEFAULT

    async def show_hour_selection(self, update, context):
        user = context.user_data["user"]
        _ = user.translator

        if update.callback_query:
            await update.callback_query.answer()

        text = _("🕐 <b>Select report hour</b>\n\nChoose hour for daily report (Kyiv time):")

        buttons = []
        for hour in range(24):
            prefix = "✅ " if hour == user.report_hour else ""
            buttons.append(InlineKeyboardButton(f"{prefix}{hour:02d}", callback_data=f"set_hour_{hour}"))

        buttons = group_buttons(buttons, 6)
        buttons.append([InlineKeyboardButton(_("◀️ Back"), callback_data="settings")])

        await send_or_edit(
            context, chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML"
        )

        return self.States.SELECT_HOUR

    async def set_report_hour(self, update, context):
        user = context.user_data["user"]
        _ = user.translator

        hour = int(update.callback_query.data.replace("set_hour_", ""))

        context.user_data[self.menu_name]["selected_hour"] = hour

        await update.callback_query.answer()

        text = _("🕐 <b>Select report minute</b>\n\nSelected hour: {hour}:XX\n\nChoose minute:").format(
            hour=f"{hour:02d}"
        )

        buttons = []
        minute_options = [0, 15, 30, 45]

        for minute in minute_options:
            prefix = "✅ " if hour == user.report_hour and minute == user.report_minute else ""
            buttons.append(InlineKeyboardButton(f"{prefix}:{minute:02d}", callback_data=f"set_minute_{minute}"))

        buttons = group_buttons(buttons, 4)
        buttons.append([InlineKeyboardButton(_("◀️ Back to hour"), callback_data="set_time")])
        buttons.append([InlineKeyboardButton(_("◀️ Cancel"), callback_data="settings")])

        await send_or_edit(
            context, chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML"
        )

        return self.States.SELECT_MINUTE

    async def set_report_minute(self, update, context):
        user = context.user_data["user"]
        _ = user.translator

        minute = int(update.callback_query.data.replace("set_minute_", ""))
        hour = context.user_data[self.menu_name].get("selected_hour", user.report_hour)

        with context.session.begin():
            stmt = select(User).where(User.id == user.id)
            db_user = context.session.scalar(stmt)
            db_user.report_hour = hour
            db_user.report_minute = minute
            context.session.add(db_user)
            context.session.flush()
            context.session.expunge(db_user)
            context.user_data["user"] = db_user

        await update.callback_query.answer(_("Report time set to {time}").format(time=f"{hour:02d}:{minute:02d}"))

        await self.send_message(context)
        return self.States.DEFAULT

    async def show_language_selection(self, update, context):
        user = context.user_data["user"]
        _ = user.translator

        if update.callback_query:
            await update.callback_query.answer()

        text = _("🌐 <b>Select language</b>\n\nChoose your preferred language:")

        buttons = []
        for code, name in SUPPORTED_LANGUAGES:
            prefix = "✅ " if code == user.language_code else ""
            buttons.append([InlineKeyboardButton(f"{prefix}{name}", callback_data=f"set_language_{code}")])

        buttons.append([InlineKeyboardButton(_("◀️ Back"), callback_data="settings")])

        await send_or_edit(
            context, chat_id=user.id, text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML"
        )

        return self.States.SELECT_LANGUAGE

    async def set_language(self, update, context):
        user = context.user_data["user"]

        language_code = update.callback_query.data.replace("set_language_", "")

        if user.language_code != language_code:
            with context.session.begin():
                stmt = select(User).where(User.id == user.id)
                db_user = context.session.scalar(stmt)
                db_user.language_code = language_code
                context.session.add(db_user)
                context.session.flush()
                user = context.session.scalar(stmt)
                context.user_data["user"] = user

        _ = user.translator
        language_name = next((name for code, name in SUPPORTED_LANGUAGES if code == language_code), language_code)
        await update.callback_query.answer(_("Language set to {language}").format(language=language_name))

        await self.send_message(context)
        return self.States.DEFAULT

    def entry_points(self) -> list[BaseHandler]:
        return [CallbackQueryHandler(self.entry, pattern="^settings$")]

    def states(self) -> dict[Enum, list[BaseHandler]]:
        return {
            self.States.DEFAULT: [
                CallbackQueryHandler(self.request_token, pattern="^set_token$"),
                CallbackQueryHandler(self.remove_token, pattern="^remove_token$"),
                CallbackQueryHandler(self.show_accounts, pattern="^select_accounts$"),
                CallbackQueryHandler(self.show_hour_selection, pattern="^set_time$"),
                CallbackQueryHandler(self.show_language_selection, pattern="^select_language$"),
            ],
            self.States.WAITING_TOKEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_token),
                CallbackQueryHandler(self.entry, pattern="^settings$"),
            ],
            self.States.SELECT_ACCOUNTS: [
                CallbackQueryHandler(self.toggle_account, pattern="^toggle_account_"),
                CallbackQueryHandler(self.save_accounts, pattern="^save_accounts$"),
                CallbackQueryHandler(self.entry, pattern="^settings$"),
            ],
            self.States.SELECT_HOUR: [
                CallbackQueryHandler(self.set_report_hour, pattern="^set_hour_"),
                CallbackQueryHandler(self.entry, pattern="^settings$"),
            ],
            self.States.SELECT_MINUTE: [
                CallbackQueryHandler(self.set_report_minute, pattern="^set_minute_"),
                CallbackQueryHandler(self.show_hour_selection, pattern="^set_time$"),
                CallbackQueryHandler(self.entry, pattern="^settings$"),
            ],
            self.States.SELECT_LANGUAGE: [
                CallbackQueryHandler(self.set_language, pattern="^set_language_"),
                CallbackQueryHandler(self.entry, pattern="^settings$"),
            ],
        }

    def fallbacks(self) -> list[BaseHandler]:
        return [MessageHandler(filters.ALL, lambda u, _c: delete_user_message(u))]
