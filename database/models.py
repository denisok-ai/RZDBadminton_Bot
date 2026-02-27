"""
@file: models.py
@description: SQLAlchemy модели для пользователей, посещаемости, новостей
@dependencies: sqlalchemy
@created: 2025-02-25
"""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для моделей."""

    pass


class User(Base):
    """Пользователь Telegram."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    attendances: Mapped[list["Attendance"]] = relationship(back_populates="user")


class Poll(Base):
    """Опрос о посещаемости."""

    __tablename__ = "polls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_poll_id: Mapped[str] = mapped_column(String(255), unique=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    poll_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    votes: Mapped[list["PollVote"]] = relationship(back_populates="poll")


class PollVote(Base):
    """Голос пользователя в опросе (Да/Опоздаю — учитываем)."""

    __tablename__ = "poll_votes"

    __table_args__ = (UniqueConstraint("poll_id", "user_id", name="uq_poll_user"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("polls.id"))
    user_id: Mapped[int] = mapped_column(BigInteger)
    option_index: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    poll: Mapped["Poll"] = relationship(back_populates="votes")


class Attendance(Base):
    """Фактическая посещаемость (кто пришёл на тренировку)."""

    __tablename__ = "attendances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    attendance_date: Mapped[date] = mapped_column(Date)
    rating: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="attendances")


class ProcessedNews(Base):
    """Обработанные посты из каналов (дедупликация по message_id + channel_id)."""

    __tablename__ = "processed_news"

    __table_args__ = (UniqueConstraint("channel_id", "message_id", name="uq_channel_message"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FeedbackPoll(Base):
    """Опрос обратной связи (оценка 1–5 за тренировку)."""

    __tablename__ = "feedback_polls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_poll_id: Mapped[str] = mapped_column(String(255), unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    training_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NewsModeration(Base):
    """Новость на модерации (ожидает решения админа)."""

    __tablename__ = "news_moderation"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column()
    source_channel: Mapped[str] = mapped_column(String(255))
    original_text: Mapped[str] = mapped_column(Text)
    rewritten_text: Mapped[str] = mapped_column(Text)
    variants: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
