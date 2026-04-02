import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import patch, MagicMock
import src.sheets_reader as sheets_module


def make_service(rows):
    mock_service = MagicMock()
    mock_values = mock_service.spreadsheets.return_value.values.return_value
    mock_values.get.return_value.execute.return_value = {"values": rows}
    mock_values.update.return_value.execute.return_value = {}
    return mock_service


class TestReadPrompts(unittest.TestCase):

    def _patch(self, rows):
        return patch.object(sheets_module, 'get_service', return_value=make_service(rows))

    def test_returns_pending_only(self):
        rows = [
            ["prompt", "status", "response"],
            ["Монгол нийслэл?", "pending", ""],
            ["Python гэж юу?", "done", "Python бол..."],
            ["AI гэж юу?", "pending", ""],
        ]
        with self._patch(rows):
            result = sheets_module.read_prompts()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["prompt"], "Монгол нийслэл?")
        self.assertEqual(result[0]["row"], 2)
        self.assertEqual(result[1]["row"], 4)

    def test_empty_sheet(self):
        with self._patch([]):
            result = sheets_module.read_prompts()
        self.assertEqual(result, [])

    def test_all_done(self):
        rows = [
            ["prompt", "status", "response"],
            ["Q1", "done", "A1"],
            ["Q2", "done", "A2"],
        ]
        with self._patch(rows):
            result = sheets_module.read_prompts()
        self.assertEqual(result, [])

    def test_skips_empty_prompt(self):
        rows = [
            ["prompt", "status", "response"],
            ["", "pending", ""],
            ["Зөв prompt", "pending", ""],
        ]
        with self._patch(rows):
            result = sheets_module.read_prompts()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["prompt"], "Зөв prompt")

    def test_row_number_correct(self):
        rows = [
            ["prompt", "status", "response"],
            ["Q1", "done", ""],
            ["Q2", "done", ""],
            ["Q3", "pending", ""],
        ]
        with self._patch(rows):
            result = sheets_module.read_prompts()
        self.assertEqual(result[0]["row"], 4)


class TestMarkRow(unittest.TestCase):

    def _patch(self):
        svc = make_service([])
        return patch.object(sheets_module, 'get_service', return_value=svc), svc

    def test_mark_done_calls_update(self):
        p, svc = self._patch()
        with p:
            sheets_module.mark_row_done(3, "Хариу")
        update = svc.spreadsheets.return_value.values.return_value.update
        update.assert_called_once()
        kwargs = update.call_args[1]
        self.assertIn("B3:C3", kwargs["range"])
        self.assertEqual(kwargs["body"]["values"][0][0], "done")
        self.assertEqual(kwargs["body"]["values"][0][1], "Хариу")

    def test_mark_error_calls_update(self):
        p, svc = self._patch()
        with p:
            sheets_module.mark_row_error(5, "Алдаа")
        update = svc.spreadsheets.return_value.values.return_value.update
        update.assert_called_once()
        kwargs = update.call_args[1]
        self.assertEqual(kwargs["body"]["values"][0][0], "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
