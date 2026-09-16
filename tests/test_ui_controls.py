"""Presentation-only contracts shared by the Streamlit pages."""

from unittest.mock import Mock, patch
import unittest

from commons import ui_controls


class UiControlsTests(unittest.TestCase):
    def test_remove_icon_button_uses_material_label_content_width_and_tooltip(self) -> None:
        with patch.object(ui_controls.st, "button", return_value=True) as button:
            self.assertTrue(
                ui_controls.utility_icon_button(
                    "remove",
                    help="Remove selected signals (2)",
                    key="remove-two",
                )
            )

        button.assert_called_once_with(
            ":material/delete:",
            help="Remove selected signals (2)",
            key="remove-two",
            disabled=False,
            type="tertiary",
            width="content",
        )

    def test_icon_button_rejects_unknown_action_or_blank_tooltip(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown utility action"):
            ui_controls.utility_icon_button("unknown", help="Known", key="x")
        with self.assertRaisesRegex(ValueError, "tooltip"):
            ui_controls.utility_icon_button("remove", help="   ", key="x")

    def test_read_only_dataframe_kwargs_are_stretch_and_index_free(self) -> None:
        self.assertEqual(
            {"width": "stretch", "hide_index": True, "height": 360},
            ui_controls.read_only_dataframe_kwargs(height=360),
        )

    def test_operational_notice_uses_titled_persistent_message(self) -> None:
        warning = Mock()
        with patch.object(ui_controls.st, "warning", warning):
            ui_controls.show_operational_notice(
                "warning",
                "Data quality",
                "History has a gap.",
            )

        warning.assert_called_once_with(
            "**Data quality**\n\nHistory has a gap.",
            icon=":material/warning:",
        )

    def test_transient_success_uses_toast_with_material_icon(self) -> None:
        toast = Mock()
        with patch.object(ui_controls.st, "toast", toast):
            ui_controls.show_transient_success("Saved.")

        toast.assert_called_once_with("Saved.", icon=":material/check_circle:")


if __name__ == "__main__":
    unittest.main()
