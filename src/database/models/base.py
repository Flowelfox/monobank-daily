from __future__ import annotations

import logging
from typing import Self

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, object_session

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    def save(self) -> Self | None:
        session = object_session(self)
        if session is None:
            logger.critical(f"No session found for {self} object")
            return None

        with session.begin():
            try:
                session.add(self)
                return self
            except SQLAlchemyError as e:
                session.rollback()
                logger.critical(f"Database error while saving {self} object: {e!s}")
                return None

    def delete(self) -> Self | None:
        session = object_session(self)
        if session is None:
            logger.critical(f"No session found for {self} object")
            return None

        with session.begin():
            try:
                session.delete(self)
                return self
            except SQLAlchemyError as e:
                session.rollback()
                logger.critical(f"Database error while removing {self.__class__} object: {e!s}")
                return None
