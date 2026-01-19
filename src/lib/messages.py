import html
import logging
from copy import deepcopy
from html.parser import HTMLParser
from io import StringIO

from telegram import (
    Bot,
    InlineKeyboardMarkup,
    InputFile,
    InputMedia,
    InputMediaAnimation,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.error import BadRequest, TelegramError
from telegram.ext import CallbackContext

logger = logging.getLogger("sender")


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, data: str) -> None:
        self.text.write(data)

    def get_data(self):
        return self.text.getvalue()


def strip_tags(html_text):
    s = MLStripper()
    s.feed(html_text)
    return s.get_data()


class Interface:
    def __init__(self, name, message=None):
        self.name = name
        self._message = message
        self.reply_markup = None
        self.parse_mode = None
        self.disable_web_page_preview = None
        self.disable_notification = None
        self.media = None

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, value: Message | None) -> None:
        self._message = value

    def __getstate__(self):
        return vars(self)

    def __setstate__(self, state):
        vars(self).update(state)

    def __getattr__(self, attr: str):
        if attr == "_message":
            result = self.__dict__.get("_message", None)
            if result is None:
                raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")
            return result
        elif "_message" in self.__dict__:
            return getattr(self._message, attr)
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")

    def __deepcopy__(self, memo: dict):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, deepcopy(v, memo))

        return result

    def extend(self, data: dict):
        self.reply_markup = data.get("reply_markup")
        self.parse_mode = data.get("parse_mode")
        self.disable_web_page_preview = data.get("disable_web_page_preview")
        self.disable_notification = data.get("disable_notification")
        photo = data.get("photo")
        document = data.get("document")
        video = data.get("video")
        animation = data.get("animation")
        if photo is not None:
            if hasattr(photo, "read"):
                photo.seek(0)
            self.media = InputMediaPhoto(photo, self.caption, self.parse_mode)
        if document is not None:
            if hasattr(document, "read"):
                document.seek(0)
            self.media = InputMediaDocument(document, self.caption, self.parse_mode)
        if video is not None:
            if hasattr(video, "read"):
                video.seek(0)
            self.media = InputMediaVideo(video, self.caption, self.parse_mode)
        if animation is not None:
            if hasattr(animation, "read"):
                animation.seek(0)
            self.media = InputMediaAnimation(animation, self.caption, self.parse_mode)

    def edit_media(self, media: InputMedia, **kwargs):
        self.media = media
        new_kwargs = {}
        for param in ["chat_id", "message_id", "inline_message_id", "reply_markup", "timeout", "api_kwargs"]:
            if param in kwargs:
                new_kwargs.update({param: kwargs[param]})

        return self.message.edit_media(media, **new_kwargs)

    async def resend(self, bot: Bot):
        if self.message is not None:
            try:
                await self.message.delete()
            except BadRequest:
                pass

            kwargs = {
                "chat_id": self.chat_id,
                "text": self.text,
                "parse_mode": self.parse_mode,
                "disable_web_page_preview": self.disable_web_page_preview,
                "disable_notification": self.disable_notification,
                "reply_markup": self.reply_markup,
                "photo": self.photo[-1].file_id if self.photo else None,
                "caption": self.caption,
                "document": self.document,
                "video": self.video,
                "animation": self.animation,
                "reply_to_message_id": self.reply_to_message.id if self.reply_to_message else None,
            }
            kwargs = {k: v for k, v in kwargs.items() if v is not None}
            self.message = await _send_telegram_message(bot, **kwargs)

    @property
    def reply_markup_type(self):
        if self.reply_markup:
            return self.reply_markup.__class__

    def save(self, user_data: dict):
        user_data["interfaces"][self.name] = self


async def _send_telegram_message(bot: Bot, **kwargs) -> Message | None:
    if "text" in kwargs:
        return await bot.send_message(**kwargs)
    elif "photo" in kwargs:
        try:
            if not isinstance(kwargs["photo"], str):
                kwargs["photo"].seek(0)

            if "disable_web_page_preview" in kwargs:
                kwargs.pop("disable_web_page_preview")
            return await bot.send_photo(**kwargs)
        except BadRequest as exc:
            if exc.message == "Media_caption_too_long" and "caption" in kwargs and kwargs["caption"] is not None:
                try:
                    kwargs["caption"] = strip_tags(kwargs["caption"])
                    return await bot.send_photo(**kwargs)
                except BadRequest:
                    kwargs["caption"] = kwargs["caption"][:1020] + "✂️"
                    return await bot.send_photo(**kwargs)
            else:
                raise exc
        finally:
            if not isinstance(kwargs["photo"], str):
                kwargs["photo"].seek(0)
    elif "animation" in kwargs:
        return await bot.send_animation(**kwargs)
    elif "video" in kwargs:
        return await bot.send_video(**kwargs)
    elif "document" in kwargs:
        return await bot.send_document(**kwargs)
    elif "location" in kwargs:
        return await bot.send_location(**kwargs)
    elif "sticker" in kwargs:
        return await bot.send_sticker(**kwargs)


def _init_interfaces(user_data):
    if "interfaces" not in user_data:
        user_data["interfaces"] = {}


def get_user_data(application, chat_id: str) -> dict:
    key = chat_id
    user_data = application.user_data.get(key, None)
    if user_data is None:
        application.user_data[key] = {}
        user_data = application.user_data[key]

    return user_data


async def send_or_edit(
    context: CallbackContext,
    interface_name: str | None = "interface",
    user_id: str | None = None,
    application=None,
    **kwargs,
) -> Interface | None:
    if user_id and application is None:
        logger.error("You must pass application with user_id")
        return None
    if user_id and application:
        user_data = get_user_data(application, user_id)
    else:
        user_data = context.user_data

    if user_data is None:
        logger.error("Can't send message to user because user_data not found")
        return None
    _init_interfaces(user_data)

    interface = user_data["interfaces"].get(interface_name, Interface(interface_name))
    logger.debug(f"send_or_edit: interface={interface_name}, has_message={interface.message is not None}")

    if len(kwargs.get("text", "")) > 4090:
        chunk_size = 4090
        chunks = len(kwargs["text"])
        message_list = [kwargs["text"][i : i + chunk_size] for i in range(0, chunks, chunk_size)]

        if "reply_markup" in kwargs:
            reply_markup = kwargs["reply_markup"]
            kwargs["reply_markup"] = None
        else:
            reply_markup = None

        for idx, message in enumerate(message_list):
            kwargs["text"] = message
            if idx == len(message_list) - 1:
                kwargs["reply_markup"] = reply_markup

            interface.message = await _send_telegram_message(context.bot, **kwargs)
            interface.extend(kwargs)
            interface.save(user_data)

        return interface

    if interface.message:
        new_reply_markup = kwargs.get("reply_markup")
        new_message_reply_markup_type = new_reply_markup.__class__ if new_reply_markup else None

        if (
            interface.reply_markup_type is not None
            and new_message_reply_markup_type is not None
            and new_message_reply_markup_type is not interface.reply_markup_type
        ):
            await remove_interface_markup(context, interface_name)
            interface.message = await _send_telegram_message(context.bot, **kwargs)
        elif new_message_reply_markup_type is ReplyKeyboardMarkup:
            interface.message = await _send_telegram_message(context.bot, **kwargs)
        elif (kwargs.get("reply_to_message_id", False) and not interface.reply_to_message) or (
            kwargs.get("reply_to_message_id", False)
            and interface.reply_to_message
            and kwargs.get("reply_to_message_id", False) != interface.reply_to_message.message_id
        ):
            await delete_interface(context, interface_name)
            interface.message = await _send_telegram_message(context.bot, **kwargs)
            interface.save(user_data)
            return interface
        else:
            text_same = False
            markup_same = True

            if kwargs.get("photo", False) or kwargs.get("document", False):
                new_caption = kwargs.get("caption", "").strip(" \n\t")
                if (interface.caption_html and html.unescape(interface.caption_html) == new_caption) or (
                    interface.caption_markdown_v2 and html.unescape(interface.caption_markdown_v2) == new_caption
                ):
                    text_same = True
            else:
                new_text = kwargs.get("text", "").replace("<s>", "").replace("</s>", "").strip(" \n\t")
                old_text_html = interface.text_html if hasattr(interface, "text_html") and interface.text_html else None
                old_text_md = (
                    interface.text_markdown_v2
                    if hasattr(interface, "text_markdown_v2") and interface.text_markdown_v2
                    else None
                )
                logger.debug(
                    f"text comparison: new='{new_text[:50]}...' old_html='{old_text_html[:50] if old_text_html else None}...'"
                )
                if (old_text_html and html.unescape(old_text_html) == new_text) or (
                    old_text_md and html.unescape(old_text_md) == new_text
                ):
                    text_same = True

            if new_message_reply_markup_type is InlineKeyboardMarkup:
                new_keyboard = new_reply_markup.inline_keyboard
                if interface.reply_markup:
                    try:
                        for y, row in enumerate(interface.reply_markup.inline_keyboard):
                            for x, button in enumerate(row):
                                if (
                                    new_keyboard[y][x].text != button.text
                                    or (
                                        hasattr(new_keyboard[y][x], "callback_data")
                                        and hasattr(button, "callback_data")
                                        and new_keyboard[y][x].callback_data != button.callback_data
                                    )
                                    or (
                                        hasattr(new_keyboard[y][x], "url")
                                        and hasattr(button, "url")
                                        and new_keyboard[y][x].url != button.url
                                    )
                                ):
                                    raise IndexError
                    except IndexError:
                        markup_same = False
                else:
                    markup_same = False
            elif new_message_reply_markup_type is ReplyKeyboardMarkup:
                new_keyboard = new_reply_markup.keyboard
                if interface.reply_markup:
                    try:
                        for y, row in enumerate(interface.reply_markup.keyboard):
                            for x, button in enumerate(row):
                                if new_keyboard[y][x] != button:
                                    raise IndexError
                    except IndexError:
                        markup_same = False
                else:
                    markup_same = False

            if "photo" in kwargs and interface.photo:
                media = InputMediaPhoto(kwargs["photo"], kwargs.get("caption"), kwargs.get("parse_mode"))
            elif "document" in kwargs and interface.document:
                media = InputMediaDocument(kwargs["document"], kwargs.get("caption"), kwargs.get("parse_mode"))
            elif "video" in kwargs and interface.video:
                media = InputMediaVideo(kwargs["video"], kwargs.get("caption"), kwargs.get("parse_mode"))
            elif "animation" in kwargs and interface.animation:
                media = InputMediaAnimation(kwargs["animation"], kwargs.get("caption"), kwargs.get("parse_mode"))
            else:
                media = None

            if media and interface.media:
                if media.media == interface.media.media:
                    media_same = True
                elif (
                    media is None
                    and interface.media.media is not None
                    or type(media.media) != type(interface.media.media)
                ):
                    media_same = False
                elif isinstance(media.media, str) and isinstance(interface.media.media, str):
                    media_same = interface.media.media == media.media
                elif isinstance(media.media, InputFile) and isinstance(interface.media.media, InputFile):
                    media_same = media.media.input_file_content == interface.media.media.input_file_content
                else:
                    media_same = interface.media == media
            else:
                media_same = True

            logger.debug(f"comparison: text_same={text_same}, markup_same={markup_same}, media_same={media_same}")

            if text_same and media_same and markup_same:
                logger.debug("Nothing changed, returning existing interface")
                interface.save(user_data)
                return interface
            elif text_same and media_same and not markup_same:
                logger.debug("Only markup changed, editing reply markup")
                interface.message = await interface.message.edit_reply_markup(reply_markup=new_reply_markup)
                interface.reply_markup = new_reply_markup
                interface.save(user_data)
                return interface

            try:
                text_changed = False
                media_changed = False
                if media is not None and not media_same:
                    logger.debug("Media changed, editing media")
                    interface.message = await interface.edit_media(
                        media=media, **{k: v for k, v in kwargs.items() if k != "chat_id"}
                    )
                    interface.reply_markup = new_reply_markup
                    media_changed = True
                elif "text" in kwargs and interface.text and not text_same:
                    logger.debug("Text changed, editing text")
                    interface.message = await interface.message.edit_text(
                        **{k: v for k, v in kwargs.items() if k != "chat_id"}
                    )
                    interface.reply_markup = new_reply_markup
                    text_changed = True
                elif "caption" in kwargs and interface.caption and not text_same:
                    logger.debug("Caption changed, editing caption")
                    interface.message = await interface.message.edit_caption(
                        **{k: v for k, v in kwargs.items() if k not in ("chat_id", "photo", "disable_web_page_preview")}
                    )
                    interface.reply_markup = new_reply_markup
                    text_changed = True

                if text_changed or media_changed:
                    interface.save(user_data)
                    return interface

                logger.debug(
                    f"Checking message type change: text in kwargs={('text' in kwargs)}, interface.text={interface.text is not None if hasattr(interface, 'text') else 'N/A'}"
                )
                if (
                    ("text" in kwargs and not interface.text)
                    or ("caption" in kwargs and not interface.caption)
                    or ("photo" in kwargs and not interface.photo)
                    or ("document" in kwargs and not interface.document)
                    or ("video" in kwargs and not interface.video)
                    or ("animation" in kwargs and not interface.animation)
                    or ("sticker" in kwargs)
                    or ("location" in kwargs)
                ):
                    logger.debug("Message type changed, deleting and resending")
                    if interface.message:
                        await interface.message.delete()
                    interface.message = await _send_telegram_message(context.bot, **kwargs)
                else:
                    logger.debug("Fallback: sending new message")
                    interface.message = await _send_telegram_message(context.bot, **kwargs)

            except (TelegramError, AttributeError) as exc:
                warning_text = f"Can't edit message: {exc}"
                if "Can't parse entities" in str(exc):
                    warning_text += "\nMessage text:\n"
                    warning_text += kwargs.get("text", kwargs.get("caption", ""))

                logger.warning(warning_text)
                interface.message = await _send_telegram_message(context.bot, **kwargs)

    else:
        await delete_interface(context, interface_name=interface_name)
        interface.message = await _send_telegram_message(context.bot, **kwargs)

    interface.extend(kwargs)
    interface.save(user_data)
    return interface


async def remove_interface(
    context: CallbackContext, interface_name: str | None = "interface", user_id: str | None = None, application=None
):
    if user_id and application is None:
        logger.error("You must pass application with user_id")
        return
    if user_id and application:
        user_data = get_user_data(application, user_id)
    else:
        user_data = context.user_data

    if user_data is None:
        logger.error("Can't send message to user because user_data not found")
        return

    _init_interfaces(user_data)

    if interface_name in user_data["interfaces"]:
        del user_data["interfaces"][interface_name]


async def delete_interface(
    context: CallbackContext, interface_name: str | None = "interface", user_id: str | None = None, application=None
):
    if user_id and application is None:
        logger.error("You must pass application with user_id")
        return
    if user_id and application:
        user_data = get_user_data(application, user_id)
    else:
        user_data = context.user_data

    if user_data is None:
        logger.error("Can't send message to user because user_data not found")
        return

    _init_interfaces(user_data)

    interface = user_data["interfaces"].get(interface_name, None)
    if interface and interface.message:
        try:
            await interface.message.delete()
        except (TelegramError, AttributeError) as e:
            logger.warning(f"Can't delete interface message: {e}")

    await remove_interface(context, interface_name, user_id, application)


async def remove_interface_markup(
    context: CallbackContext, interface_name: str | None = "interface", user_id: str | None = None, application=None
):
    if user_id and application is None:
        logger.error("You must pass application with user_id")
        return
    if user_id and application:
        user_data = get_user_data(application, user_id)
    else:
        user_data = context.user_data

    if user_data is None:
        logger.error("Can't send message to user because user_data not found")
        return

    _init_interfaces(user_data)

    interface = user_data["interfaces"].get(interface_name, None)

    if interface:
        try:
            if interface.reply_markup and interface.reply_markup_type is ReplyKeyboardMarkup:
                await delete_interface(context, interface_name, user_id, application)
            else:
                await interface.message.edit_reply_markup()
        except (TelegramError, AttributeError) as e:
            logger.warning(f"Can't remove keyboard markup in interface message: {e}")

    await remove_interface(context, interface_name, user_id, application)


def get_interface(context: CallbackContext, name: str) -> Interface | None:
    if context.user_data and "interfaces" in context.user_data and name in context.user_data["interfaces"]:
        return context.user_data["interfaces"][name]
    return None


async def delete_user_message(update: Update):
    if update.message and update.message.message_id:
        await update.message.delete()
