"""
@file: app_state.py
@description: Глобальное состояние приложения (session_factory для handlers)
@dependencies: sqlalchemy
@created: 2025-02-25
"""

session_factory = None


def set_session_factory(factory):
    """Установить фабрику сессий (вызывается из bot.py)."""
    global session_factory
    session_factory = factory


def get_session_factory():
    """Получить фабрику сессий."""
    return session_factory
