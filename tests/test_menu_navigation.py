import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Chat, Message, Update
from telegram import User as TelegramUser
from telegram.ext import ApplicationBuilder, ContextTypes, ExtBot

from src.lib.callback_context import CustomCallbackContext
from src.menus.start import StartMenu

USER_ID = 123456789


def _make_text_update(update_id, text):
    return Update(
        update_id=update_id,
        message=Message(
            message_id=update_id,
            date=datetime.datetime.now(tz=datetime.UTC),
            chat=Chat(id=USER_ID, type="private"),
            from_user=TelegramUser(id=USER_ID, first_name="Test", is_bot=False),
            text=text,
        ),
    )


def _make_callback_update(update_id, data, bot):
    msg = Message(
        message_id=1,
        date=datetime.datetime.now(tz=datetime.UTC),
        chat=Chat(id=USER_ID, type="private"),
        from_user=TelegramUser(id=USER_ID, first_name="Test", is_bot=False),
        text="dummy",
    )
    msg.set_bot(bot)
    cq = CallbackQuery(
        id=str(update_id),
        chat_instance="test",
        from_user=TelegramUser(id=USER_ID, first_name="Test", is_bot=False),
        message=msg,
        data=data,
    )
    cq.set_bot(bot)
    update = Update(update_id=update_id, callback_query=cq)
    update.set_bot(bot)
    return update


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = USER_ID
    user.monobank_token = "uTestToken123456789012345678901234567890"
    user.selected_accounts = ["account1"]
    user.language_code = "en"
    user.translator = lambda x: x
    user.report_hour = 21
    user.report_minute = 0
    return user


class TestMenuNavigation:
    async def test_settings_back_then_get_report(self, mock_user):
        """After Settings -> Back -> Get Report, the report handler should fire."""
        mock_session = MagicMock()
        mock_sent_msg = MagicMock()
        mock_sent_msg.message_id = 999
        mock_send_message = AsyncMock(return_value=mock_sent_msg)

        with patch("src.lib.callback_context.get_session", return_value=mock_session):
            context_types = ContextTypes(context=CustomCallbackContext)
            app = ApplicationBuilder().token("0:TEST").context_types(context_types).build()

            start_menu = StartMenu(application=app)
            app.add_handler(start_menu.handler)

            async def setup_user(update, context):
                context.user_data["user"] = mock_user
                return mock_user

            with (
                patch.object(ExtBot, "initialize", new_callable=AsyncMock),
                patch.object(ExtBot, "shutdown", new_callable=AsyncMock),
                patch.object(ExtBot, "send_message", mock_send_message),
                patch.object(ExtBot, "delete_message", new_callable=AsyncMock),
                patch.object(ExtBot, "answer_callback_query", new_callable=AsyncMock),
                patch("src.menus.start.prepare_user", new_callable=AsyncMock, side_effect=setup_user),
                patch("src.menus.start.delete_user_message", new_callable=AsyncMock),
                patch("src.menus.start.delete_interface", new_callable=AsyncMock),
                patch("src.menus.start.send_or_edit", new_callable=AsyncMock),
                patch("src.menus.settings_menu.send_or_edit", new_callable=AsyncMock),
                patch("src.menus.settings_menu.delete_user_message", new_callable=AsyncMock),
            ):
                async with app:
                    # Step 1: /start -> enter main menu
                    await app.process_update(_make_text_update(1, "/start"))

                    # Step 2: Press "⚙️ Settings" -> enter settings
                    await app.process_update(_make_text_update(2, "⚙️ Settings"))

                    # Step 3: Press inline "Back" (callback_data="start") -> exit settings
                    await app.process_update(_make_callback_update(3, "start", app.bot))

                    # Step 4: Press "📈 Get Report Now" -> should trigger get_report
                    mock_send_message.reset_mock()
                    await app.process_update(_make_text_update(4, "📈 Get Report Now"))

                    # Verify get_report was reached (it sends the loading message)
                    mock_send_message.assert_any_call(chat_id=USER_ID, text="⏳ Querying API...")
