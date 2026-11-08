from __future__ import annotations
import logging
from typing import Callable
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session as SyncSession
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_size=10, max_overflow=20, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Действия вне базы, привязанные к транзакции ─────────
# Файлы фото лежат на диске, а не в базе, поэтому откат транзакции их не трогает.
# Чтобы диск не расходился с базой:
#   - новый файл пишется сразу, но удаляется, если транзакция откатилась (on_rollback);
#   - удаление файла откладывается до успешного коммита (on_commit).
# Срабатывает для любой сессии (запрос, скрипт, фоновая очистка), а не только в get_db.

logger = logging.getLogger("nsusosed")


def on_commit(db, fn: Callable[[], None]) -> None:
    db.info.setdefault("on_commit", []).append(fn)


def on_rollback(db, fn: Callable[[], None]) -> None:
    db.info.setdefault("on_rollback", []).append(fn)


def _run(callbacks: list[Callable[[], None]]) -> None:
    for fn in callbacks:
        try:
            fn()
        except Exception:
            logger.exception("Post-transaction action failed")


@event.listens_for(SyncSession, "after_commit")
def _after_commit(session) -> None:
    session.info.pop("on_rollback", None)
    _run(session.info.pop("on_commit", []))


@event.listens_for(SyncSession, "after_rollback")
def _after_rollback(session) -> None:
    session.info.pop("on_commit", None)
    _run(session.info.pop("on_rollback", []))
