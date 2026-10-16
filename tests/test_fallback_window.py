import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ADDON_ROOT = Path(__file__).resolve().parents[1]
WINDOW = ADDON_ROOT / "resources" / "skins" / "default" / "1080i" / "script-nexttrack-nexttrack.xml"


class FallbackWindowTests(unittest.TestCase):
    def setUp(self):
        self.window = ET.parse(WINDOW).getroot()
        self.text = WINDOW.read_text(encoding="utf-8")

    def test_card_sits_top_right_with_square_art(self):
        group = self.window.find("./controls/control")
        self.assertEqual("80", group.findtext("right"))
        self.assertEqual("60", group.findtext("top"))
        self.assertIsNone(group.find("bottom"))
        image = group.find("./control[@type='image']")
        self.assertEqual("230", image.findtext("width"))
        self.assertEqual("230", image.findtext("height"))
        self.assertIn("Window.Property(thumb)", image.findtext("texture"))

    def test_text_lines_are_right_aligned_with_countdown_header(self):
        labels = self.window.findall(".//control[@type='grouplist']/control[@type='label']")
        self.assertEqual(3, len(labels))
        for label in labels:
            self.assertEqual("right", label.findtext("align"))
        header = labels[0].findtext("label")
        self.assertIn("30050", header)
        self.assertIn("Window.Property(remaining)", header)
        self.assertIn("Window.Property(title)", labels[1].findtext("label"))
        self.assertIn("Window.Property(artist)", labels[2].findtext("label"))
        self.assertIn("Window.Property(album)", labels[2].findtext("label"))

    def test_no_references_to_removed_bundled_media(self):
        self.assertNotIn("progress/circle", self.text)
        self.assertNotIn("combined_overlay", self.text)
        self.assertNotIn("diffuse/circle", self.text)
        self.assertFalse((ADDON_ROOT / "resources" / "skins" / "default" / "media").exists())

    def test_overlay_never_takes_focus_or_input(self):
        focusable = {"button", "radiobutton", "togglebutton", "edit", "list", "panel",
                     "wraplist", "fixedlist", "slider", "spincontrol", "spincontrolex",
                     "scrollbar", "textbox"}
        for control in self.window.iter("control"):
            self.assertNotIn(control.get("type"), focusable)
        self.assertIsNone(self.window.find("defaultcontrol"))


if __name__ == "__main__":
    unittest.main()
