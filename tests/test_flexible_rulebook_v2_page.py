"""Three-workspace Streamlit surface for user-authored Flexible Rulebook v2."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import inspect
import unittest

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None


@unittest.skipIf(AppTest is None, "Streamlit AppTest runtime is unavailable")
class FlexibleRulebookV2PageTests(unittest.TestCase):
    def test_empty_v2_library_offers_builder_backtest_and_library_without_v1_policy(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}))\n"
            ).run()

        self.assertEqual(app.exception, [])
        self.assertEqual(len(app.radio), 1)
        self.assertEqual(
            app.radio[0].options,
            ["Rulebook Builder", "Rulebook Backtest", "Rulebook Library"],
        )
        self.assertTrue(any("Exploratory — gross" in item.value for item in app.markdown))
        self.assertTrue(any("Create Rulebook" in item.value for item in app.info))

    def test_builder_uses_registry_driven_typed_settings_and_shows_a_summary(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}))\n"
            ).run()
            next(item for item in app.selectbox if item.label == "Indicator").set_value("ema").run()

        self.assertEqual(app.exception, [])
        self.assertTrue(any(item.label == "Fast period" for item in app.number_input))
        self.assertTrue(any(item.label == "Slow period" for item in app.number_input))
        self.assertFalse(any(item.label == "Settings JSON" for item in app.text_area))
        self.assertTrue(any("Rulebook summary" in item.value for item in app.markdown))

    def test_editing_a_saved_ma_single_period_restores_the_typed_settings(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}))\n"
            ).run()
            next(item for item in app.selectbox if item.label == "Indicator").set_value("ema").run()
            next(item for item in app.selectbox if item.label == "MA setup").set_value("Single period").run()
            next(item for item in app.number_input if item.label == "Period").set_value(9).run()
            next(item for item in app.text_input if item.label == "Name").set_value("Early EMA").run()
            next(item for item in app.button if item.label == "Save draft").click().run()
            app.radio[0].set_value("Rulebook Library").run()
            next(item for item in app.button if item.label == "Edit").click().run()

        self.assertEqual(app.exception, [])
        self.assertEqual("Rulebook Builder", app.radio[0].value)
        self.assertEqual(9, next(item for item in app.number_input if item.label == "Period").value)

    def test_published_rulebooks_use_collision_safe_ids_and_keep_evaluation_history_visible(self) -> None:
        from pages import flexible_rulebook

        source = inspect.getsource(flexible_rulebook)
        self.assertNotIn("rulebook_id[5:13]", source)
        self.assertIn("Evaluation history", source)

    def test_trade_rows_convert_raw_database_prices_only_at_the_display_boundary(self) -> None:
        from pages.flexible_rulebook import _trade_rows

        rows = _trade_rows(({
            "entry_price": 12345000,
            "exit_price": 13000500.0,
            "return_pct": 5.310652,
            "exit_reason": "timeout",
        },))

        self.assertEqual(12_345.0, rows[0]["Entry price (k VND)"])
        self.assertEqual(13_000.5, rows[0]["Exit price (k VND)"])
        self.assertEqual(5.31, rows[0]["Return %"])
        self.assertNotIn("entry_price", rows[0])
        self.assertNotIn("exit_price", rows[0])

    def test_cloning_a_published_rulebook_uses_a_pre_widget_callback(self) -> None:
        from datetime import datetime, timezone

        from flexible_rulebook.v2.contracts import PredicateV2, PublishedRulebook, RulebookDefinitionV2
        from flexible_rulebook.v2.storage import write_published_rulebook

        definition = RulebookDefinitionV2(
            horizon="swing",
            entry_operator="all",
            buy_predicates=(PredicateV2(
                role="buy",
                family="rsi",
                family_revision="rsi-wilder-sma-seeded-v1",
                settings={"period": 9},
                operator="upcross",
                condition={"threshold": 52},
            ),),
            max_hold_bars=22,
        )
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            write_published_rulebook(
                root,
                PublishedRulebook.publish(definition, published_at=datetime(2026, 9, 16, tzinfo=timezone.utc)),
            )
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}))\n"
            ).run()
            app.radio[0].set_value("Rulebook Library").run()
            next(item for item in app.button if item.label == "Clone to edit").click().run()

        self.assertEqual(app.exception, [])
        self.assertEqual("Rulebook Builder", app.radio[0].value)



if __name__ == "__main__":
    unittest.main()
