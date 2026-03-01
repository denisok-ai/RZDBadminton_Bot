"""
@file: keyboards.py
@description: SportTech клавиатуры — цветные кнопки (success/danger/primary)
@dependencies: aiogram
@created: 2025-02-25
"""

from datetime import date

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from utils.constants import MONTHS_RU


def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Главное меню.

    Обычные пользователи видят только 3 базовые кнопки.
    Для админа — дополнительные кнопки управления и утилиты.
    """
    keyboard: list[list[KeyboardButton]] = [
        [
            KeyboardButton(text="📍 Зал"),
            KeyboardButton(text="⏱ Расписание"),
            KeyboardButton(text="📋 Правила"),
        ],
    ]
    if is_admin:
        keyboard += [
            [
                KeyboardButton(text="📝 Оценить"),
                KeyboardButton(text="📈 Рейтинги"),
                KeyboardButton(text="❓ Помощь"),
            ],
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
            [
                KeyboardButton(text="📊 Статистика"),
                KeyboardButton(text="📋 Ответ квиза"),
                KeyboardButton(text="🧹 Очистить предложения"),
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


def youtube_moderation_keyboard(
    moderation_id: int,
    publish_cb: str,
    reject_cb: str,
) -> InlineKeyboardMarkup:
    """Кнопки модерации YouTube: Опубликовать в чат / Отклонить."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 В ленту",
                    callback_data=f"{publish_cb}{moderation_id}",
                ),
                InlineKeyboardButton(
                    text="⛔ Отклонить",
                    callback_data=f"{reject_cb}{moderation_id}",
                ),
            ],
        ]
    )


def news_moderation_keyboard(
    moderation_id: int,
    publish_cb: str,
    reject_cb: str,
    edit_cb: str,
) -> InlineKeyboardMarkup:
    """Кнопки модерации новости: В ленту / Варианты / Отклонить."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 В ленту",
                    callback_data=f"{publish_cb}{moderation_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Варианты",
                    callback_data=f"{edit_cb}{moderation_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⛔ Отклонить",
                    callback_data=f"{reject_cb}{moderation_id}",
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
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_month_keyboard(months_count: int = 12) -> InlineKeyboardMarkup:
    """Клавиатура выбора месяца для отчёта: последние months_count месяцев от текущего."""
    today = date.today()
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i in range(months_count):
        # Текущий месяц — 0, предыдущий — 1, ...
        y, m = today.year, today.month
        m -= i
        while m < 1:
            m += 12
            y -= 1
        month_name = MONTHS_RU.get(m, str(m)).capitalize()
        text = f"{month_name} {y}"
        row.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"report_sel:{y}:{m}",
            )
        )
        if len(row) == 3:  # по 3 кнопки в ряд
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def stats_month_keyboard(months_count: int = 12) -> InlineKeyboardMarkup:
    """Клавиатура выбора месяца для экрана «Статистика»: последние months_count месяцев."""
    today = date.today()
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i in range(months_count):
        y, m = today.year, today.month
        m -= i
        while m < 1:
            m += 12
            y -= 1
        month_name = MONTHS_RU.get(m, str(m)).capitalize()
        text = f"{month_name} {y}"
        row.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"stats_sel:{y}:{m}",
            )
        )
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Inline-панель управления для администратора."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Опрос", callback_data="admin:poll"),
                InlineKeyboardButton(text="📊 Отчёт", callback_data="admin:report"),
            ],
            [
                InlineKeyboardButton(text="📰 Новости", callback_data="admin:news"),
                InlineKeyboardButton(text="🎯 Квиз", callback_data="admin:quiz"),
            ],
            [
                InlineKeyboardButton(text="📋 Ответ квиза", callback_data="admin:quiz_answer"),
            ],
            [
                InlineKeyboardButton(text="🏆 Топ-3", callback_data="admin:top3"),
                InlineKeyboardButton(text="📈 Рейтинги", callback_data="admin:ratings"),
            ],
            [
                InlineKeyboardButton(text="🎬 YouTube", callback_data="admin:youtube"),
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats"),
            ],
        ]
    )
