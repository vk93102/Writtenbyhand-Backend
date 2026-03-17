from pathlib import Path
import unittest


class TestProjectStructure(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent

    def test_core_directories_exist(self):
        self.assertTrue((self.root / "handtotext_ai").exists())
        self.assertTrue((self.root / "handtotext_core").exists())
        self.assertTrue((self.root / "handtotext_hashtag").exists())

    def test_core_files_exist(self):
        expected_files = [
            "manage.py",
            "render.yaml",
            "requirements.txt",
            "handtotext_ai/settings.py",
            "handtotext_core/api_routes.py",
            "handtotext_core/core_data_models.py",
            "handtotext_core/services/gemini_ai_service.py",
        ]

        for rel_path in expected_files:
            with self.subTest(path=rel_path):
                self.assertTrue((self.root / rel_path).exists())


if __name__ == "__main__":
    unittest.main()
