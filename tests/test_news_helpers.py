"""
@file: test_news_helpers.py
@description: Тесты хелперов модерации новостей (парсинг callback_data)
@dependencies: handlers.news
@created: 2026-03-01
"""

from handlers.news import _parse_moderation_id

PREFIX_PUBLISH = "news_mod:publish:"
PREFIX_BACK = "news_mod:back:"


class TestParseModerationId:
    """Тесты для _parse_moderation_id."""

    def test_none_data_returns_none(self) -> None:
        assert _parse_moderation_id(None, PREFIX_PUBLISH) is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse_moderation_id("", PREFIX_PUBLISH) is None

    def test_wrong_prefix_returns_none(self) -> None:
        assert _parse_moderation_id("other:42", PREFIX_PUBLISH) is None
        assert _parse_moderation_id("news_mod:reject:1", PREFIX_PUBLISH) is None

    def test_valid_id_returns_int(self) -> None:
        assert _parse_moderation_id("news_mod:publish:42", PREFIX_PUBLISH) == 42
        assert _parse_moderation_id("news_mod:publish:1", PREFIX_PUBLISH) == 1
        assert _parse_moderation_id("news_mod:back:99", PREFIX_BACK) == 99

    def test_whitespace_after_prefix_stripped(self) -> None:
        assert _parse_moderation_id("news_mod:publish:  7  ", PREFIX_PUBLISH) == 7

    def test_empty_after_prefix_returns_none(self) -> None:
        assert _parse_moderation_id("news_mod:publish:", PREFIX_PUBLISH) is None
        assert _parse_moderation_id("news_mod:publish:  ", PREFIX_PUBLISH) is None

    def test_non_numeric_returns_none(self) -> None:
        assert _parse_moderation_id("news_mod:publish:abc", PREFIX_PUBLISH) is None
        assert _parse_moderation_id("news_mod:publish:12:34", PREFIX_PUBLISH) is None
