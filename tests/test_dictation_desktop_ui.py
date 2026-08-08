import unittest

from scripts.dictation_desktop_ui import _shorten


class DictationDesktopUiTests(unittest.TestCase):
    def test_device_name_is_cleaned_and_shortened(self):
        self.assertEqual(_shorten("  Микрофон   (H1)  "), "Микрофон (H1)")
        result = _shorten("Очень длинное имя устройства " * 4, limit=30)
        self.assertLessEqual(len(result), 30)
        self.assertTrue(result.endswith("…"))


if __name__ == "__main__":
    unittest.main()
