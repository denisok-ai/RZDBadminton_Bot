"""
@file: __init__.py
@description: SportTech UI — дизайн-система и клавиатуры
@created: 2025-02-25
"""

from ui.design import (
    block,
    card,
    error_msg,
    section,
    success_msg,
    title,
)
from ui.keyboards import (
    main_menu_keyboard,
    news_moderation_keyboard,
    variant_buttons_keyboard,
)

__all__ = [
    "block",
    "card",
    "error_msg",
    "main_menu_keyboard",
    "news_moderation_keyboard",
    "section",
    "success_msg",
    "title",
    "variant_buttons_keyboard",
]
