import asyncio
import datetime
from enum import Enum

import pytz
from telegram import KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import BaseHandler, MessageHandler, PrefixHandler, filters

from src.lib.basemenu import BaseMenu
from src.lib.helpers import format_money, prepare_user
from src.lib.menu_filters import FILTER_GET_REPORT, FILTER_HELP
from src.lib.messages import delete_interface, delete_user_message, send_or_edit
from src.menus.settings_menu import SettingsMenu
from src.services.monobank import MonobankAPIError, get_daily_spending
from src.settings import TIMEZONE


class StartMenu(BaseMenu):
    async def entry(self, update, context):
        await prepare_user(update, context)

        if self.menu_name not in context.user_data:
            context.user_data[self.menu_name] = {}

        if update.effective_message and update.effective_message.text == "/start":
            await delete_interface(context)

        await self.send_message(context)
        return self.States.DEFAULT

    async def send_message(self, context):
        user = context.user_data["user"]
        _ = user.translator

        has_token = user.monobank_token is not None
        has_accounts = len(user.selected_accounts) > 0

        if has_token and has_accounts:
            status = _("✅ Bot configured")
        elif has_token and not has_accounts:
            status = _("⚠️ Select accounts in settings")
        else:
            status = _("⚠️ Add Monobank token in settings")

        report_time = f"{user.report_hour:02d}:{user.report_minute:02d}"
        text = _("📊 Monobank Daily Report Bot\n\n{status}\n\nDaily report at {report_time} Kyiv time.").format(
            status=status, report_time=report_time
        )

        buttons = []

        if has_token and has_accounts:
            buttons.append([KeyboardButton(_("📈 Get Report Now"))])

        buttons.append([KeyboardButton(_("⚙️ Settings")), KeyboardButton(_("❓ Help"))])

        await send_or_edit(
            context,
            chat_id=user.id,
            text=text,
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True),
            parse_mode="HTML",
        )

    async def get_report(self, update, context):
        await delete_user_message(update)
        user = context.user_data["user"]
        _ = user.translator

        if not user.monobank_token:
            await context.bot.send_message(user.id, _("Please add Monobank token first"))
            return self.States.DEFAULT

        if not user.selected_accounts:
            await context.bot.send_message(user.id, _("Please select accounts first"))
            return self.States.DEFAULT

        loading_msg = await context.bot.send_message(chat_id=user.id, text=_("⏳ Querying API..."))

        asyncio.create_task(self._fetch_and_send_report(context.bot, user, loading_msg.message_id))

        return self.States.DEFAULT

    async def _fetch_and_send_report(self, bot, user, loading_message_id):
        _ = user.translator

        tz = pytz.timezone(TIMEZONE)
        now = datetime.datetime.now(tz)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        from_ts = int(start_of_day.timestamp())
        to_ts = int(now.timestamp())

        try:
            result = await asyncio.wait_for(
                get_daily_spending(
                    user.monobank_token, user.selected_accounts, from_ts, to_ts, user.language_code or "uk"
                ),
                timeout=30,
            )

            date_str = now.strftime("%d.%m.%Y")
            text = _("📊 Spending for {date}\n\n").format(date=date_str)

            if result["total_spending"] > 0:
                text += _("💰 Total: -{amount} ₴\n\n").format(amount=format_money(result["total_spending"]))

                if result["categories"]:
                    text += _("📁 By category:\n")
                    for cat in result["categories"]:
                        text += f"{cat['name']}: -{format_money(cat['amount'])} ₴\n"
            else:
                text += _("No spending today! 🎉")

            if result["total_income"] > 0:
                text += _("\n\n📥 Income: +{amount} ₴").format(amount=format_money(result["total_income"]))

            await bot.delete_message(chat_id=user.id, message_id=loading_message_id)
            await bot.send_message(chat_id=user.id, text=text, parse_mode="HTML")

        except TimeoutError:
            await bot.delete_message(chat_id=user.id, message_id=loading_message_id)
            await bot.send_message(chat_id=user.id, text=_("❌ Request timed out. Please try again later."))

        except MonobankAPIError as e:
            await bot.delete_message(chat_id=user.id, message_id=loading_message_id)
            await bot.send_message(chat_id=user.id, text=_("❌ Error: {error}").format(error=e.message))

        except Exception:
            await bot.delete_message(chat_id=user.id, message_id=loading_message_id)
            await bot.send_message(chat_id=user.id, text=_("❌ Something went wrong. Please try again later."))

    async def show_help(self, update, context):
        await delete_user_message(update)
        user = context.user_data["user"]
        _ = user.translator

        text = _(
            "❓ <b>How to use this bot:</b>\n\n"
            "1. Get your Monobank token:\n"
            "   • Open Monobank app\n"
            "   • Go to Settings → API\n"
            "   • Create a token\n\n"
            "2. Add token in Settings\n\n"
            "3. Select accounts to track\n\n"
            "4. Set your preferred report time in Settings\n\n"
            "You can also get report manually anytime!"
        )

        await context.bot.send_message(chat_id=user.id, text=text, parse_mode="HTML")

        return self.States.DEFAULT

    def entry_points(self) -> list[BaseHandler]:
        return [PrefixHandler("/", "start", self.entry)]

    def states(self) -> dict[Enum, list[BaseHandler]]:
        return {
            self.States.DEFAULT: [
                SettingsMenu(self).handler,
                MessageHandler(FILTER_GET_REPORT, self.get_report),
                MessageHandler(FILTER_HELP, self.show_help),
            ],
        }

    def fallbacks(self) -> list[BaseHandler]:
        return [MessageHandler(filters.ALL, lambda u, _c: delete_user_message(u))]
