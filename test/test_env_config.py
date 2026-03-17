from pathlib import Path
import unittest


class TestEnvConfig(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.env_path = self.root / ".env"

    def test_env_file_exists(self):
        self.assertTrue(self.env_path.exists(), ".env file should exist")

    def test_django_settings_module_present(self):
        content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("DJANGO_SETTINGS_MODULE=handtotext_ai.settings", content)


if __name__ == "__main__":
    unittest.main()
