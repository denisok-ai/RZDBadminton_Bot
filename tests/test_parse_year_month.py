"""
@file: test_parse_year_month.py
@description: Тесты разбора callback_data для выбора месяца (отчёт, статистика)
@dependencies: handlers.commands
@created: 2026-03-01
"""

from handlers.commands import _parse_year_month


class TestParseYearMonth:
    """Тесты для _parse_year_month (report_sel:/stats_sel:)."""

    def test_none_returns_none(self) -> None:
        assert _parse_year_month(None, "report_sel:") is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse_year_month("", "report_sel:") is None

    def test_wrong_prefix_returns_none(self) -> None:
        assert _parse_year_month("other:2026:3", "report_sel:") is None
        assert _parse_year_month("report_sel:2026:3", "stats_sel:") is None
        assert _parse_year_month("stats_sel:2026:3", "report_sel:") is None

    def test_valid_report_returns_tuple(self) -> None:
        assert _parse_year_month("report_sel:2026:3", "report_sel:") == (2026, 3)
        assert _parse_year_month("report_sel:2025:12", "report_sel:") == (2025, 12)
        assert _parse_year_month("report_sel:2024:1", "report_sel:") == (2024, 1)

    def test_valid_stats_returns_tuple(self) -> None:
        assert _parse_year_month("stats_sel:2026:3", "stats_sel:") == (2026, 3)
        assert _parse_year_month("stats_sel:2025:6", "stats_sel:") == (2025, 6)

    def test_month_out_of_range_returns_none(self) -> None:
        assert _parse_year_month("report_sel:2026:0", "report_sel:") is None
        assert _parse_year_month("report_sel:2026:13", "report_sel:") is None

    def test_non_numeric_returns_none(self) -> None:
        assert _parse_year_month("report_sel:2026:ab", "report_sel:") is None
        assert _parse_year_month("report_sel:xx:3", "report_sel:") is None
        assert _parse_year_month("report_sel:2026:3:1", "report_sel:") is None

    def test_single_part_after_prefix_returns_none(self) -> None:
        assert _parse_year_month("report_sel:2026", "report_sel:") is None
