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
    ]
    if is_admin:
        lines.extend([
            "",
            section("Админ", "Управление — кнопки меню: Опрос, Отчёт, Новости, Квиз, Топ-3, Рейтинги, YouTube, Статистика, Ответ квиза."),
            "",
            section("Оценка и отчёты", block([
                "«📝 Оценить» — опрос 1–5 за последнюю тренировку в чат",
                "«📈 Рейтинги» — средний балл по тренировкам за месяц",
                "«📊 Статистика» — сводка по опросам, новостям, квизам за месяц",
            ])),
            "",
            section("YouTube", block([
                "/clearyoutube — сбросить список опубликованных видео (повторная проверка)",
                "«🧹 Очистить предложения» — очистить очередь видео на модерации",
            ])),
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
            section("Админ", "Используйте кнопки меню: Опрос, Отчёт, Новости, Квиз, Топ-3, Рейтинги, YouTube, Статистика, Ответ квиза."),
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


def feedback_weekly_card(
    week_label: str,
    data: dict[str, tuple[float, int]],
    trainer_mon: str,
    trainer_wed: str,
) -> str:
    """Карточка итогов обратной связи за неделю (Пн + Ср). data — результат get_ratings_by_trainer."""
    mon_avg, mon_count = data.get("mon", (0.0, 0))
    wed_avg, wed_count = data.get("wed", (0.0, 0))
    overall_avg, overall_count = data.get("overall", (0.0, 0))

    if overall_count == 0:
        return card("📝 Обратная связь за неделю · " + week_label, "За эту неделю оценок пока нет")

    def _stars(avg: float) -> str:
        return "⭐" * min(round(avg), 5)

    lines: list[str] = []
    if mon_count > 0:
        lines.append(f"🟦 {trainer_mon}: <b>{mon_avg}</b> {_stars(mon_avg)} · {mon_count} оц.")
    if wed_count > 0:
        lines.append(f"🟩 {trainer_wed}: <b>{wed_avg}</b> {_stars(wed_avg)} · {wed_count} оц.")
    lines.append(SEP)
    lines.append(f"Общий: <b>{overall_avg}</b> {_stars(overall_avg)} · {overall_count} оценок")
    return card("📝 Обратная связь за неделю · " + week_label, *lines)


def news_moderation_card(source: str, text: str) -> str:
    """Карточка новости на модерации."""
    return card(
        "📰 На модерации",
        f"Источник: <code>{source}</code>",
        "",
        text,
    )


def activity_stats_card(
    month: str,
    year: int,
    stats: dict,
    llm_tokens: int | None = None,
    llm_limit: int = 0,
) -> str:
    """Карточка статистики активности чата за месяц.

    Args:
        month: Название месяца.
        year: Год.
        stats: Словарь из get_activity_stats().
        llm_tokens: Потрачено токенов DeepSeek за месяц (если учёт включён).
        llm_limit: Месячный лимит токенов (0 — не показывать блок).
    """
    polls_sent = stats.get("polls_sent", 0)
    poll_participants = stats.get("poll_participants", 0)
    poll_attending = stats.get("poll_attending", 0)
    news_published = stats.get("news_published", 0)
    quizzes_sent = stats.get("quizzes_sent", 0)
    feedback_sent = stats.get("feedback_sent", 0)
    feedback_avg = stats.get("feedback_avg", 0.0)
    feedback_count = stats.get("feedback_count", 0)

    def _stars(avg: float) -> str:
        return "⭐" * min(round(avg), 5) if avg > 0 else ""

    lines: list[str] = []

    # Опросы посещаемости
    lines.append("📋 <b>Опросы посещаемости</b>")
    lines.append(f"  {DOT} Отправлено: <b>{polls_sent}</b>")
    lines.append(f"  {DOT} Участников (уник.): <b>{poll_participants}</b>")
    lines.append(f"  {DOT} Планировали прийти: <b>{poll_attending}</b>")
    lines.append("")

    # Новости
    lines.append("📰 <b>Новости</b>")
    lines.append(f"  {DOT} Опубликовано: <b>{news_published}</b>")
    lines.append("")

    # Квизы
    quiz_participants = stats.get("quiz_participants", 0)
    lines.append("🎯 <b>Квизы</b>")
    lines.append(f"  {DOT} Отправлено: <b>{quizzes_sent}</b>")
    lines.append(f"  {DOT} Участников: <b>{quiz_participants}</b>")
    lines.append("")

    # YouTube
    youtube_sent = stats.get("youtube_sent", 0)
    youtube_published = stats.get("youtube_published", 0)
    youtube_rejected = stats.get("youtube_rejected", 0)
    youtube_pending_total = stats.get("youtube_pending_total", 0)
    lines.append("🎬 <b>YouTube</b>")
    lines.append(f"  {DOT} Отправлено на модерацию: <b>{youtube_sent}</b>")
    lines.append(f"  {DOT} Опубликовано: <b>{youtube_published}</b> · Отклонено: <b>{youtube_rejected}</b>")
    lines.append(f"  {DOT} В очереди (сейчас): <b>{youtube_pending_total}</b>")
    lines.append("")

    # Обратная связь
    lines.append("📝 <b>Обратная связь</b>")
    lines.append(f"  {DOT} Опросов: <b>{feedback_sent}</b>")
    if feedback_count > 0:
        stars = _stars(feedback_avg)
        lines.append(f"  {DOT} Средняя оценка: <b>{feedback_avg}</b> {stars} · {feedback_count} оц.")
    else:
        lines.append(f"  {DOT} Оценок пока нет")

    if llm_limit and llm_tokens is not None:
        lines.append("")
        lines.append("🤖 <b>DeepSeek</b>")
        lines.append(f"  {DOT} Токенов за месяц: <b>{llm_tokens}</b> (лимит {llm_limit})")

    return card(f"📊 Статистика · {month} {year}", *lines)
