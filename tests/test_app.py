"""Tests for the event bus, commands, model, memory, history and settings."""

from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from calcengine.app import (
    CalculatorModel,
    EventBus,
    History,
    HistoryEntry,
    MemoryBank,
    Settings,
    SettingsStore,
    Topic,
)
from calcengine.app.commands import (
    Backspace,
    ClearAll,
    CommandStack,
    InsertText,
    SetExpression,
    ToggleSign,
)
from calcengine.core import AngleMode, NotationMode


class EventBusTests(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()

    def test_publish_reaches_subscriber(self):
        received = []
        self.bus.subscribe(Topic.STATUS, received.append)
        self.bus.publish(Topic.STATUS, text="hello")
        self.assertEqual(received[0].get("text"), "hello")

    def test_unsubscribe(self):
        received = []
        off = self.bus.subscribe(Topic.STATUS, received.append)
        off()
        self.bus.publish(Topic.STATUS, text="ignored")
        self.assertEqual(received, [])

    def test_subscriber_may_unsubscribe_during_dispatch(self):
        calls = []

        def listener(event):
            calls.append(event)
            off()

        off = self.bus.subscribe(Topic.STATUS, listener)
        self.bus.publish(Topic.STATUS)
        self.bus.publish(Topic.STATUS)
        self.assertEqual(len(calls), 1)

    def test_subscribe_many(self):
        received = []
        self.bus.subscribe_many([Topic.STATUS, Topic.MODE_CHANGED], received.append)
        self.bus.publish(Topic.STATUS)
        self.bus.publish(Topic.MODE_CHANGED)
        self.assertEqual(len(received), 2)

    def test_journal_is_bounded(self):
        self.bus.journal_limit = 10
        for _ in range(50):
            self.bus.publish(Topic.STATUS)
        self.assertLessEqual(len(self.bus.journal), 10)

    def test_mute(self):
        received = []
        self.bus.subscribe(Topic.STATUS, received.append)
        self.bus.mute()
        self.bus.publish(Topic.STATUS)
        self.assertEqual(received, [])
        self.bus.unmute()
        self.bus.publish(Topic.STATUS)
        self.assertEqual(len(received), 1)


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.model = CalculatorModel()
        self.stack = CommandStack()

    def test_insert_at_cursor(self):
        self.stack.run(InsertText("12"), self.model)
        self.model.set_cursor(1)
        self.stack.run(InsertText("9"), self.model)
        self.assertEqual(self.model.expression, "192")

    def test_undo_restores_previous_state(self):
        self.stack.run(InsertText("5+"), self.model)
        self.stack.run(ClearAll(), self.model)
        self.assertEqual(self.model.expression, "")
        self.stack.undo(self.model)
        self.assertEqual(self.model.expression, "5+")

    def test_redo(self):
        self.stack.run(InsertText("7"), self.model)
        self.stack.undo(self.model)
        self.stack.redo(self.model)
        self.assertEqual(self.model.expression, "7")

    def test_alphanumeric_runs_coalesce(self):
        for char in "1234":
            self.stack.run(InsertText(char), self.model)
        self.assertEqual(len(self.stack), 1)
        self.stack.undo(self.model)
        self.assertEqual(self.model.expression, "")

    def test_operators_are_their_own_undo_step(self):
        for char in "12+34":
            self.stack.run(InsertText(char), self.model)
        self.assertEqual(len(self.stack), 3)
        self.stack.undo(self.model)
        self.assertEqual(self.model.expression, "12+")

    def test_backspace_at_start_is_a_noop(self):
        self.stack.run(Backspace(), self.model)
        self.assertEqual(self.model.expression, "")

    def test_new_edit_clears_redo(self):
        self.stack.run(InsertText("1"), self.model)
        self.stack.undo(self.model)
        self.stack.run(InsertText("2"), self.model)
        self.assertFalse(self.stack.can_redo)

    def test_stack_is_bounded(self):
        stack = CommandStack(limit=5)
        for index in range(20):
            stack.run(SetExpression(str(index)), self.model)
        self.assertLessEqual(len(stack), 5)

    def test_undo_on_empty_stack_returns_none(self):
        self.assertIsNone(self.stack.undo(self.model))
        self.assertIsNone(self.stack.redo(self.model))


class ToggleSignTests(unittest.TestCase):
    def setUp(self):
        self.model = CalculatorModel()

    def toggle(self, text: str, cursor: int | None = None) -> str:
        self.model.set_expression(text)
        if cursor is not None:
            self.model.set_cursor(cursor)
        self.model.toggle_sign()
        return self.model.expression

    def test_negates_trailing_literal(self):
        self.assertEqual(self.toggle("5+7"), "5+-7")

    def test_round_trip(self):
        self.model.set_expression("42")
        self.model.toggle_sign()
        self.model.toggle_sign()
        self.assertEqual(self.model.expression, "42")

    def test_empty_buffer_starts_a_negative(self):
        self.assertEqual(self.toggle(""), "-")

    def test_negates_literal_at_cursor(self):
        self.assertEqual(self.toggle("12+345", 3), "12+-345")


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.model = CalculatorModel()
        self.events: list[str] = []
        self.model.bus.subscribe_many(
            list(Topic), lambda event: self.events.append(event.topic.name)
        )

    def type(self, text: str) -> None:
        for char in text:
            self.model.insert(char)

    def test_evaluate_replaces_buffer_with_result(self):
        self.type("12+34")
        result = self.model.evaluate()
        self.assertEqual(result.formatted, "46")
        self.assertEqual(self.model.expression, "46")

    def test_result_is_chainable(self):
        self.type("6*7")
        self.model.evaluate()
        self.type("+1")
        self.assertEqual(self.model.evaluate().value, 43)

    def test_grouped_result_is_reusable_as_input(self):
        # The buffer must hold "1234567", not "1,234,567".
        self.type("1234567")
        self.model.evaluate()
        self.assertEqual(self.model.expression, "1234567")
        self.type("+1")
        self.assertEqual(self.model.evaluate().value, 1234568)

    def test_live_preview(self):
        self.type("2*3")
        self.assertEqual(self.model.preview_text(), "6")

    def test_preview_hidden_when_identical(self):
        self.type("7")
        self.assertEqual(self.model.preview_text(), "")

    def test_preview_empty_on_error(self):
        self.type("1/0")
        self.assertEqual(self.model.preview_text(), "")

    def test_preview_can_be_disabled(self):
        self.type("2*3")
        self.model.toggle_live_preview()
        self.assertEqual(self.model.preview_text(), "")

    def test_error_is_published_and_recorded(self):
        self.type("1/0")
        self.assertIsNone(self.model.evaluate())
        self.assertIn("ERROR_RAISED", self.events)
        self.assertEqual(self.model.last_error.message, "Division by zero.")

    def test_empty_evaluate_is_a_noop(self):
        self.assertIsNone(self.model.evaluate())

    def test_history_records_results(self):
        for expression in ("1+1", "2*2"):
            self.model.set_expression(expression)
            self.model.evaluate()
        self.assertEqual(len(self.model.history), 2)
        self.assertEqual(self.model.history.last.formatted, "4")

    def test_failed_evaluation_is_not_recorded(self):
        self.model.set_expression("1/0")
        self.model.evaluate()
        self.assertEqual(len(self.model.history), 0)

    def test_recall_entry(self):
        self.model.set_expression("3*3")
        self.model.evaluate()
        entry = self.model.history.last
        self.model.recall_entry(entry)
        self.assertEqual(self.model.expression, "3*3")
        self.model.recall_entry(entry, use_result=True)
        self.assertEqual(self.model.expression, "9")

    def test_clear_history(self):
        self.model.set_expression("1+1")
        self.model.evaluate()
        self.model.clear_history()
        self.assertEqual(len(self.model.history), 0)

    def test_variables_round_trip(self):
        self.model.set_expression("r = 5")
        self.model.evaluate()
        self.model.set_expression("r^2")
        self.assertEqual(self.model.evaluate().value, 25)
        self.assertIn("VARIABLES_CHANGED", self.events)

    def test_cursor_is_clamped(self):
        self.type("abc")
        self.model.set_cursor(99)
        self.assertEqual(self.model.cursor, 3)
        self.model.set_cursor(-5)
        self.assertEqual(self.model.cursor, 0)

    def test_mode_cycling(self):
        self.model.cycle_angle_mode()
        self.assertEqual(self.model.engine.angle_mode, AngleMode.DEGREES)
        self.model.cycle_notation()
        self.assertEqual(self.model.engine.notation, NotationMode.FIXED)
        self.assertIn("MODE_CHANGED", self.events)

    def test_toggles(self):
        self.model.toggle_tape()
        self.assertFalse(self.model.show_tape)
        self.model.toggle_inspector()
        self.assertTrue(self.model.show_inspector)
        self.assertTrue(self.model.engine.collect_trace)

    def test_undo_redo_through_model(self):
        self.type("12")
        self.model.undo()
        self.assertEqual(self.model.expression, "")
        self.model.redo()
        self.assertEqual(self.model.expression, "12")


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.model = CalculatorModel()

    def test_store_and_recall(self):
        self.model.set_expression("42")
        self.model.memory_store()
        self.model.clear()
        self.model.memory_recall()
        self.assertEqual(self.model.expression, "42")

    def test_add_and_subtract(self):
        self.model.set_expression("10")
        self.model.memory_store()
        self.model.set_expression("4")
        self.model.memory_add()
        self.assertEqual(self.model.memory.recall(), 14)
        self.model.memory_subtract()
        self.assertEqual(self.model.memory.recall(), 10)

    def test_clear(self):
        self.model.set_expression("1")
        self.model.memory_store()
        self.model.memory_clear()
        self.assertFalse(self.model.memory.is_set())

    def test_named_slots_are_independent(self):
        bank = MemoryBank()
        bank.store(Decimal(1), "M")
        bank.store(Decimal(2), "M1")
        self.assertEqual(bank.recall("M"), 1)
        self.assertEqual(bank.recall("M1"), 2)
        self.assertEqual(bank.occupied, ["M", "M1"])

    def test_unset_slot_reads_zero(self):
        self.assertEqual(MemoryBank().recall(), 0)

    def test_recall_strips_grouping(self):
        self.model.set_expression("1234567")
        self.model.memory_store()
        self.model.clear()
        self.model.memory_recall()
        self.assertEqual(self.model.expression, "1234567")


class HistoryTests(unittest.TestCase):
    def entry(self, expression: str) -> HistoryEntry:
        return HistoryEntry(expression, expression, Decimal(1))

    def test_ring_buffer_drops_oldest(self):
        history = History(limit=3)
        for index in range(10):
            history.add(self.entry(str(index)))
        self.assertEqual(len(history), 3)
        self.assertEqual(history.entries[0].expression, "7")

    def test_recent_is_newest_first(self):
        history = History()
        for index in range(3):
            history.add(self.entry(str(index)))
        self.assertEqual([e.expression for e in history.recent()], ["2", "1", "0"])
        self.assertEqual([e.expression for e in history.recent(2)], ["2", "1"])

    def test_serialisation_round_trip(self):
        history = History()
        history.add(self.entry("1+1"))
        restored = History()
        restored.load(history.to_list())
        self.assertEqual(restored.last.expression, "1+1")

    def test_corrupt_rows_are_skipped(self):
        history = History()
        history.load([{"nope": 1}, {"expression": "x", "formatted": "x",
                                    "value": "1",
                                    "timestamp": "2024-01-01T00:00:00"}])
        self.assertEqual(len(history), 1)

    def test_text_export(self):
        history = History()
        history.add(self.entry("2+2"))
        self.assertIn("2+2 = 2+2", history.as_text())


class SettingsTests(unittest.TestCase):
    def test_round_trip_through_disk(self):
        model = CalculatorModel()
        model.set_expression("6*7")
        model.evaluate()
        model.memory_store()
        model.cycle_angle_mode()
        model.set_theme("neon")

        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "session.json")
            self.assertTrue(store.save(model.to_settings()))

            restored = CalculatorModel()
            restored.apply_settings(store.load())

        self.assertEqual(restored.theme_name, "neon")
        self.assertEqual(restored.engine.angle_mode, AngleMode.DEGREES)
        self.assertEqual(len(restored.history), 1)
        self.assertEqual(restored.memory.recall(), 42)

    def test_missing_file_yields_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "absent.json")
            self.assertEqual(store.load().theme, "midnight")

    def test_corrupt_file_yields_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{not json at all", encoding="utf-8")
            self.assertEqual(SettingsStore(path).load().precision, 28)

    def test_non_object_json_yields_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "list.json"
            path.write_text("[1, 2, 3]", encoding="utf-8")
            self.assertEqual(SettingsStore(path).load().theme, "midnight")

    def test_unknown_keys_are_ignored(self):
        settings = Settings.from_dict({"theme": "neon", "bogus": 123})
        self.assertEqual(settings.theme, "neon")
        self.assertFalse(hasattr(settings, "bogus"))

    def test_out_of_range_values_are_clamped(self):
        settings = Settings.from_dict({"precision": 9999, "decimals": -5})
        self.assertEqual(settings.precision, 200)
        self.assertEqual(settings.decimals, 0)

    def test_wrong_types_fall_back(self):
        settings = Settings.from_dict(
            {"precision": "abc", "history": "nope", "memory": 5, "theme": 42}
        )
        self.assertEqual(settings.precision, 28)
        self.assertEqual(settings.history, [])
        self.assertEqual(settings.memory, {})
        self.assertEqual(settings.theme, "midnight")

    def test_stale_enum_values_fall_back(self):
        model = CalculatorModel()
        model.apply_settings(Settings.from_dict({"angle_mode": "TURNS"}))
        self.assertEqual(model.engine.angle_mode, AngleMode.RADIANS)

    def test_save_is_atomic_and_leaves_no_temp_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            store = SettingsStore(path)
            store.save(Settings())
            self.assertTrue(path.exists())
            leftovers = [p.name for p in Path(directory).iterdir()]
            self.assertEqual(leftovers, ["session.json"])
            self.assertIsInstance(json.loads(path.read_text()), dict)

    def test_save_failure_is_reported_not_raised(self):
        store = SettingsStore(Path("/nonexistent-root-xyz/session.json"))
        self.assertFalse(store.save(Settings()))


if __name__ == "__main__":
    unittest.main()
