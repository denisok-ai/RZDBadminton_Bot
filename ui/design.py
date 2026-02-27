"""
@file: design.py
@description: SportTech Design System — типографика, блоки, паттерны UX
@created: 2025-02-25
"""

# SportTech: динамичный, технологичный, минималистичный
# Принципы: чёткая иерархия, сканируемость, action-first

SEP = "▬▬▬"
BRAND = "🏸"
DOT = "•"


def title(text: str, emoji: str = BRAND) -> str:
    """Главный заголовок — жирный, с брендом."""
    return f"{emoji} <b>{text}</b>"


def section(header: str, body: str, sep: str = SEP) -> str:
    """Секция: заголовок + разделитель + контент."""
    return f"<b>{header}</b>\n{sep}\n{body}"


def block(items: list[str], prefix: str = DOT) -> str:
    """Список пунктов с единообразным префиксом."""
    return "\n".join(f"{prefix} {item}" for item in items)


def card(header: str, *lines: str, footer: str | None = None) -> str:
    """Карточка: заголовок, строки, опциональный футер."""
    parts = [f"<b>{header}</b>", SEP]
    parts.extend(lines)
    if footer:
        parts.append("")
        parts.append(footer)
    return "\n".join(parts)


def success_msg(action: str, detail: str = "") -> str:
    """Сообщение об успехе — краткое, позитивное."""
    base = f"✓ {action}"
    return f"{base}\n{detail}" if detail else base


def error_msg(problem: str, hint: str = "") -> str:
    """Сообщение об ошибке — проблема + подсказка."""
    base = f"⚠ {problem}"
    return f"{base}\n\n{hint}" if hint else base


def admin_action_start(action: str, detail: str = "") -> str:
    """Стартовое сообщение для действия админ-панели."""
    return card("⚙️ Админ · Выполняю", action, detail) if detail else card("⚙️ Админ · Выполняю", action)


def admin_action_success(action: str, detail: str = "") -> str:
    """Успешное завершение действия админ-панели."""
    return card("✅ Админ · Готово", action, detail) if detail else card("✅ Админ · Готово", action)


def admin_action_error(action: str, problem: str) -> str:
    """Ошибка действия админ-панели в едином формате."""
    return card("⚠️ Админ · Ошибка", action, problem)


def help_screen(is_admin: bool = False) -> str:
    """Экран справки по командам в стиле SportTech."""
    lines = [
        title("Справка", "📖"),
        "",
        section("Для всех", block([
            "/location — зал и карта",
            "/timetable — расписание тренировок",
            "/rules — экипировка",
            "/help — эта справка",
        ])),
        "",
        section("Оценка тренировки", "Кнопка «📝 Оценить» или команда /feedback — опрос 1–5 за последнюю тренировку."),
    ]
    if is_admin:
        lines.extend([
            "",
            section("Админ", "Кнопка «⚙️ Админ» — панель: опрос, отчёт, новости, квиз, топ-3, рейтинги, YouTube."),
        ])
    return "\n".join(lines)


# Готовые шаблоны для частых сценариев
def start_screen(is_admin: bool = False) -> str:
    """Главный экран /start в стиле SportTech."""
    main = [
        title("Бадминтон РЖД", "⚡"),
        "",
        section("Быстрые действия", block([
            "/location — зал на карте",
            "/timetable — расписание",
            "/rules — экипировка",
        ])),
    ]
    if is_admin:
        main.extend([
            "",
            section("Админ-панель", "Нажмите ⚙️ Админ и выберите действие в inline-панели"),
        ])
    return "\n".join(main)


def location_card(name: str, address: str, map_url: str) -> str:
    """Карточка локации."""
    return card(
        "📍 Локация",
        name,
        address,
        footer=f"<a href='{map_url}'>Открыть на карте →</a>",
    )


def timetable_card(days: str, time: str, venue: str) -> str:
    """Карточка расписания."""
    return card(
        "⏱ Расписание",
        f"Дни: {days}",
        f"Время: {time}",
        f"Место: {venue}",
    )


def top3_card(month: str, year: int, items: list[tuple[str, str, int]], empty_msg: str) -> str:
    """Карточка Топ-3. items: (user_id, name, count)."""
    if not items:
        return card(f"🏆 Топ-3 · {month} {year}", empty_msg)
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"{medals[i]} {name} — {cnt} тренировок" for i, (_, name, cnt) in enumerate(items)]
    return card(f"🏆 Топ-3 · {month} {year}", *lines)


def ratings_card(
    month: str,
    year: int,
    data: dict[str, tuple[float, int]],
    trainer_mon: str,
    trainer_wed: str,
) -> str:
    """Карточка рейтингов с разбивкой по тренерам и итогом."""
    mon_avg, mon_count = data.get("mon", (0.0, 0))
    wed_avg, wed_count = data.get("wed", (0.0, 0))
    overall_avg, overall_count = data.get("overall", (0.0, 0))

    if overall_count == 0:
        return card(f"📈 Рейтинги · {month} {year}", "Оценок пока нет")

    def _stars(avg: float) -> str:
        return "⭐" * min(round(avg), 5)

    lines: list[str] = []
    if mon_count > 0:
        lines.append(f"🟦 {trainer_mon}: <b>{mon_avg}</b> {_stars(mon_avg)} · {mon_count} оц.")
    if wed_count > 0:
        lines.append(f"🟩 {trainer_wed}: <b>{wed_avg}</b> {_stars(wed_avg)} · {wed_count} оц.")
    lines.append("▬▬▬")
    lines.append(f"Общий: <b>{overall_avg}</b> {_stars(overall_avg)} · {overall_count} оценок")

    return card(f"📈 Рейтинги · {month} {year}", *lines)


def news_moderation_card(source: str, text: str) -> str:
    """Карточка новости на модерации."""
    return card(
        "📰 На модерации",
        f"Источник: <code>{source}</code>",
        "",
        text,
    )
