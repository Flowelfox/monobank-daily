import datetime
import gettext
import json
from html import escape

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column
from telegram import Bot
from telegram import User as TelegramUser

from src.database.models.base import Base
from src.lib.crypto import decrypt_token, encrypt_token
from src.settings import PROJECT_ROOT, REPORT_HOUR, REPORT_MINUTE


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str] = mapped_column(String(10), default="uk")
    _monobank_token: Mapped[str | None] = mapped_column("monobank_token", String(512), nullable=True)
    _selected_accounts: Mapped[str | None] = mapped_column("selected_accounts", Text, nullable=True)
    report_hour: Mapped[int] = mapped_column(Integer, default=REPORT_HOUR)
    report_minute: Mapped[int] = mapped_column(Integer, default=REPORT_MINUTE)
    join_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    block_date: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def monobank_token(self) -> str | None:
        if self._monobank_token:
            return decrypt_token(self._monobank_token, self.id)
        return None

    @monobank_token.setter
    def monobank_token(self, value: str | None):
        if value:
            self._monobank_token = encrypt_token(value, self.id)
        else:
            self._monobank_token = None

    @property
    def selected_accounts(self) -> list[str]:
        if self._selected_accounts:
            return json.loads(self._selected_accounts)
        return []

    @selected_accounts.setter
    def selected_accounts(self, value: list[str]):
        self._selected_accounts = json.dumps(value) if value else None

    @hybrid_property
    def is_active(self):
        return not self.block_date

    @is_active.expression
    def is_active(cls):
        return cls.block_date.is_(None)

    @hybrid_property
    def has_token(self):
        return self._monobank_token is not None

    @has_token.expression
    def has_token(cls):
        return cls._monobank_token.isnot(None)

    def activate(self):
        self.block_date = None

    def deactivate(self):
        self.block_date = datetime.datetime.utcnow()

    @property
    def name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name and not self.last_name:
            return f"{self.first_name}"
        else:
            return ""

    @property
    def mention_url(self) -> str:
        return f"tg://user?id={self.id}"

    @property
    def mention(self) -> str:
        return f'<a href="{self.mention_url}">{escape(self.name)}</a>'

    def to_telegram_user(self, bot: Bot, **kwargs) -> TelegramUser:
        return TelegramUser(
            self.id, self.first_name, False, self.last_name, self.username, self.language_code, bot=bot, **kwargs
        )

    @property
    def _translation(self):
        if self.language_code is None:
            translation = gettext.translation("messages", str(PROJECT_ROOT / "locales"), languages=["en"], fallback=True)
        else:
            translation = gettext.translation(
                "messages", str(PROJECT_ROOT / "locales"), languages=[str(self.language_code)], fallback=True
            )
        return translation

    @property
    def translator(self):
        return self._translation.gettext

    @property
    def ntranslator(self):
        return self._translation.ngettext
