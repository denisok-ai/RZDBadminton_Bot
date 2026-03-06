"""
@file: config.py
@description: Конфигурация приложения через Pydantic Settings и .env
@dependencies: pydantic-settings, python-dotenv
@created: 2025-02-25
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str
    admin_id: int
    main_chat_id: int
    test_chat_id: int | None = None

    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"
    # Лимит токенов в месяц (DeepSeek). 0 или не задан — учёт отключён. Цель по qa: ~200–400 ₽/мес.
    deepseek_monthly_token_limit: int = 0

    yandex_disk_token: str

    telegram_api_id: int
    telegram_api_hash: str

    database_url: str = "sqlite+aiosqlite:///./data/badminton_bot.db"

    debug_mode: bool = False  # true в .env — опросы в TEST_CHAT_ID

    timezone: str = "Europe/Moscow"
    sources_file: Path = Path("Doc/sources.txt")
    vk_sources_file: Path = Path("Doc/vk_sources.txt")  # Ссылки на каналы VK Видео (по одной на строку)
    vk_access_token: str | None = None  # Токен VK API для video.get (если пусто — VK не опрашивается)

    @field_validator("vk_sources_file", mode="before")
    @classmethod
    def _coerce_vk_sources_path(cls, v) -> Path:
        if v is None:
            return Path("Doc/vk_sources.txt")
        return Path(v) if isinstance(v, str) else v

    @field_validator("vk_access_token", mode="before")
    @classmethod
    def _strip_vk_token(cls, v: str | None) -> str | None:
        if v is None or not isinstance(v, str):
            return None
        cleaned = v.strip().strip('"\'')
        return cleaned if cleaned else None

    rules_file: Path = Path("Doc/rules")
    # Файл правил НФБР (.docx) для контекста квиза — если задан и существует, текст подставляется в промпт
    rules_docx_file: str | None = None  # например Doc/pravila_nfbr.docx
    report_file: Path = Path("Doc/Бадминтон.xlsx")
    report_template_file: Path = Path("Doc/Бадминтон_шаблон.xlsx")  # шаблон — копировать при создании
    attendance_report_file: Path = Path("Doc/Attendance_Report.xlsx")  # рабочий файл отчёта (excel_reporter)
    report_template_url: str = "https://disk.yandex.ru/i/AJkaQ3HpEjz0aw"
    report_upload_path: str = "/Отчёты/Бадминтон"  # к имени добавится _YYYY-MM-DD.xlsx
    youtube_channel_id: str | None = None  # BWF TV: UChh-akEbUM8_6ghGVnJd6cQ или UCdBDkMCBO1Ni7Fkys-1dKdA
    # Ключ YouTube Data API v3 — без кавычек в .env; в Google Cloud включите YouTube Data API v3
    youtube_api_key: str | None = None

    @field_validator("youtube_api_key", mode="before")
    @classmethod
    def _strip_youtube_api_key(cls, v: str | None) -> str | None:
        """Убрать кавычки и пробелы (частая ошибка при копировании из .env)."""
        if v is None or not isinstance(v, str):
            return v
        cleaned = v.strip().strip('"\'')
        return cleaned if cleaned else None

    # Имена тренеров по дням (можно переопределить в .env: TRAINER_MON=Иванов, TRAINER_WED=Петрова)
    trainer_mon: str = "Тренер (Пн)"
    trainer_wed: str = "Тренер (Ср)"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Возвращает закэшированный экземпляр настроек (читает .env один раз)."""
    return Settings()


def get_poll_chat_id(settings: Settings) -> int:
    """Чат для опросов: тестовый при DEBUG_MODE, иначе основной."""
    if settings.debug_mode and settings.test_chat_id is not None:
        return settings.test_chat_id
    return settings.main_chat_id


def get_publish_chat_id(settings: Settings) -> int:
    """Чат для публикации новостей/отчётов: тестовый при DEBUG_MODE, иначе основной."""
    if settings.debug_mode and settings.test_chat_id is not None:
        return settings.test_chat_id
    return settings.main_chat_id


def get_moderation_chat_id(settings: Settings) -> int:
    """Чат для модерации новостей: группа (как и публикация), чтобы «В ленту» работало."""
    if settings.debug_mode and settings.test_chat_id is not None:
        return settings.test_chat_id
    return settings.main_chat_id
