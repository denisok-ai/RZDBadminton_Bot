"""
@file: keyboards.py
@description: SportTech клавиатуры — цветные кнопки (success/danger/primary)
@dependencies: aiogram
@created: 2025-02-25
"""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)


def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Главное меню — компактная клавиатура."""
    keyboard: list[list[KeyboardButton]] = [
        [
            KeyboardButton(text="📍 Зал"),
            KeyboardButton(text="⏱ Расписание"),
            KeyboardButton(text="📋 Правила"),
        ],
        [
            KeyboardButton(text="📝 Оценить"),
            KeyboardButton(text="📈 Рейтинги"),
            KeyboardButton(text="❓ Помощь"),
        ],
    ]
    if is_admin:
        keyboard += [
            [
                KeyboardButton(text="🚀 Опрос"),
                KeyboardButton(text="📊 Отчёт"),
                KeyboardButton(text="📰 Новости"),
            ],
            [
                KeyboardButton(text="🎯 Квиз"),
                KeyboardButton(text="🏆 Топ-3"),
                KeyboardButton(text="🎬 YouTube"),
            ],
        ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    """Убрать клавиатуру."""
    return ReplyKeyboardRemove()


def news_moderation_keyboard(
    moderation_id: int,
    publish_cb: str,
    reject_cb: str,
    edit_cb: str,
) -> InlineKeyboardMarkup:
    """Кнопки модерации с безопасной иерархией действий (SportTech)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 В ленту",
                    callback_data=f"{publish_cb}{moderation_id}",
                    style="success",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Варианты",
                    callback_data=f"{edit_cb}{moderation_id}",
                    style="primary",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⛔ Отклонить",
                    callback_data=f"{reject_cb}{moderation_id}",
                    style="danger",
                ),
            ],
        ]
    )


def variant_buttons_keyboard(
    moderation_id: int,
    count: int,
    variant_cb: str,
    back_callback_data: str | None = None,
) -> InlineKeyboardMarkup:
    """Кнопки выбора варианта — компактная 2-колоночная сетка + опционально «Назад»."""
    buttons = [
        InlineKeyboardButton(
            text=f"▸ Вариант {i + 1}",
            callback_data=f"{variant_cb}{moderation_id}:{i}",
            style="primary",
        )
        for i in range(count)
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    if back_callback_data:
        rows.append(
            [
                InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data=back_callback_data,
                    style="primary",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Админ-панель в стиле SportTech: быстрые сценарии одной сеткой."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Опрос", callback_data="admin:poll", style="success"),
                InlineKeyboardButton(text="📊 Отчёт", callback_data="admin:report", style="primary"),
            ],
            [
                InlineKeyboardButton(text="📰 Новости", callback_data="admin:news", style="primary"),
                InlineKeyboardButton(text="🎯 Квиз", callback_data="admin:quiz", style="primary"),
            ],
            [
                InlineKeyboardButton(text="🏆 Топ-3", callback_data="admin:top3", style="primary"),
                InlineKeyboardButton(text="📈 Рейтинги", callback_data="admin:ratings", style="primary"),
            ],
            [
                InlineKeyboardButton(text="🎬 YouTube", callback_data="admin:youtube", style="primary"),
            ],
        ]
    )
