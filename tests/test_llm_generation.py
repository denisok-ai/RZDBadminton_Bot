"""
@file: test_llm_generation.py
@description: Тесты уникальности и парсинга LLM-генерации
@dependencies: unittest, services.llm
@created: 2026-02-26
"""

from pathlib import Path
import tempfile
import unittest

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
        )
        parsed = llm._parse_quiz_response(text)
        self.assertIsNotNone(parsed)
        question, options, correct = parsed  # type: ignore[misc]
        self.assertEqual(question, "Сколько очков в гейме до победы?")
        self.assertEqual(options, ["11", "15", "21", "25"])
        self.assertEqual(correct, 2)

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


if __name__ == "__main__":
    unittest.main()
