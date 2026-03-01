"""
@file: test_constants.py
@description: Тесты общих констант проекта
@dependencies: utils.constants
@created: 2026-03-01
"""

from utils.constants import MONTHS_RU


class TestMonthsRu:
    """Тесты для MONTHS_RU."""

    def test_has_twelve_months(self) -> None:
        assert len(MONTHS_RU) == 12
        assert set(MONTHS_RU.keys()) == set(range(1, 13))

    def test_values_are_lowercase_russian(self) -> None:
        assert MONTHS_RU[1] == "январь"
        assert MONTHS_RU[12] == "декабрь"
        assert MONTHS_RU[6] == "июнь"

    def test_all_values_non_empty_strings(self) -> None:
        for month_num, name in MONTHS_RU.items():
            assert isinstance(month_num, int)
            assert isinstance(name, str)
            assert len(name) > 0
