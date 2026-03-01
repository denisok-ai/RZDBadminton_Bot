"""
@file: test_llm_generation.py
@description: Тесты уникальности, парсинга LLM-генерации и учёта токенов
@dependencies: unittest, unittest.mock, services.llm
@created: 2026-02-26
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services import llm


class LlmGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_history = llm.HISTORY_FILE
        llm.HISTORY_FILE = Path(self._tmp.name) / "history.json"

    def tearDown(self) -> None:
        llm.HISTORY_FILE = self._old_history
        self._tmp.cleanup()

    def test_parse_quiz_response_ok(self) -> None:
        text = (
            "QUESTION: Сколько очков в гейме до победы?\n"
            "OPTIONS:\n"
            "1. 11\n"
            "2. 15\n"
            "3. 21\n"
            "4. 25\n"
            "CORRECT: 3\n"
            "EXPLANATION: По правилам НФБР гейм идёт до 21 очка.\n"
        )
        parsed = llm._parse_quiz_response(text)
        self.assertIsNotNone(parsed)
        question, options, correct, explanation = parsed  # type: ignore[misc]
        self.assertEqual(question, "Сколько очков в гейме до победы?")
        self.assertEqual(options, ["11", "15", "21", "25"])
        self.assertEqual(correct, 2)  # 0-based индекс для варианта 3
        self.assertIn("21", explanation)
        self.assertIn(llm.NFBR_RULES_URL, explanation)

    def test_poll_duplicate_detection(self) -> None:
        first = llm._remember_generation("poll", "Всем привет! Кто сегодня на тренировку? 🏸")
        second = llm._remember_generation("poll", "  Всем   привет! Кто сегодня на тренировку? 🏸  ")
        self.assertTrue(first)
        self.assertFalse(second)

    def test_quiz_signature_duplicate_detection(self) -> None:
        sig1 = llm._quiz_signature("Что такое смеш?", ["Удар сверху", "Подача", "Прием", "Пауза"])
        sig2 = llm._quiz_signature("  Что   такое смеш? ", ["Удар сверху", "Подача", "Прием", "Пауза"])
        self.assertEqual(sig1, sig2)
        self.assertTrue(llm._remember_generation("quiz", sig1))
        self.assertFalse(llm._remember_generation("quiz", sig2))

    def test_parse_quiz_response_empty_returns_none(self) -> None:
        self.assertIsNone(llm._parse_quiz_response(""))
        self.assertIsNone(llm._parse_quiz_response("   \n  "))

    def test_parse_quiz_response_incomplete_returns_none(self) -> None:
        # Нет вопроса
        self.assertIsNone(llm._parse_quiz_response("OPTIONS:\n1. A\n2. B\n3. C\n4. D\nCORRECT: 1"))
        # Только 3 варианта
        text = (
            "QUESTION: Тест?\nOPTIONS:\n1. A\n2. B\n3. C\nCORRECT: 1\nEXPLANATION: x"
        )
        self.assertIsNone(llm._parse_quiz_response(text))
        # CORRECT вне диапазона (0-based: 0..3)
        text = (
            "QUESTION: Тест?\nOPTIONS:\n1. A\n2. B\n3. C\n4. D\nCORRECT: 5\nEXPLANATION: x"
        )
        self.assertIsNone(llm._parse_quiz_response(text))

    def test_parse_quiz_response_correct_first_option(self) -> None:
        text = (
            "QUESTION: Первый вариант?\n"
            "OPTIONS:\n1. Да\n2. Нет\n3. Может\n4. Не знаю\n"
            "CORRECT: 1\nEXPLANATION: Правильный — первый."
        )
        parsed = llm._parse_quiz_response(text)
        self.assertIsNotNone(parsed)
        question, options, correct, explanation = parsed  # type: ignore[misc]
        self.assertEqual(question, "Первый вариант?")
        self.assertEqual(correct, 0)
        self.assertIn(llm.NFBR_RULES_URL, explanation)


class LlmUsageTests(unittest.TestCase):
    """Тесты учёта расхода токенов (DeepSeek)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_usage_file = llm.USAGE_FILE
        llm.USAGE_FILE = Path(self._tmp.name) / "llm_usage.json"

    def tearDown(self) -> None:
        llm.USAGE_FILE = self._old_usage_file
        self._tmp.cleanup()

    def test_current_month_key_format(self) -> None:
        key = llm._current_month_key()
        self.assertRegex(key, r"^\d{4}-\d{2}$", "Формат ключа месяца YYYY-MM")

    def test_read_usage_when_no_file(self) -> None:
        self.assertFalse(llm.USAGE_FILE.exists())
        data = llm._read_usage()
        self.assertEqual(data["total_tokens"], 0)
        self.assertEqual(data["year_month"], llm._current_month_key())

    def test_record_and_get_usage(self) -> None:
        self.assertEqual(llm._get_monthly_usage(), 0)
        llm._record_usage(100)
        self.assertEqual(llm._get_monthly_usage(), 100)
        llm._record_usage(50)
        self.assertEqual(llm._get_monthly_usage(), 150)

    def test_record_usage_ignores_zero_and_negative(self) -> None:
        llm._record_usage(0)
        llm._record_usage(-10)
        self.assertEqual(llm._get_monthly_usage(), 0)

    def test_is_over_limit_disabled_when_zero(self) -> None:
        with patch.object(llm, "get_settings") as m:
            m.return_value.deepseek_monthly_token_limit = 0
            self.assertFalse(llm._is_over_limit())
            m.return_value.deepseek_monthly_token_limit = None
            self.assertFalse(llm._is_over_limit())

    def test_is_over_limit_when_under(self) -> None:
        llm._record_usage(50)
        with patch.object(llm, "get_settings") as m:
            m.return_value.deepseek_monthly_token_limit = 100
            self.assertFalse(llm._is_over_limit())

    def test_is_over_limit_when_reached(self) -> None:
        llm._record_usage(100)
        with patch.object(llm, "get_settings") as m:
            m.return_value.deepseek_monthly_token_limit = 100
            self.assertTrue(llm._is_over_limit())


if __name__ == "__main__":
    unittest.main()
