from pathlib import Path
import unittest


class TestReadmeProjectLinks(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.readme = self.root / "README.md"

    def test_required_links_present(self):
        content = self.readme.read_text(encoding="utf-8")
        self.assertIn("https://github.com/vk93102/HandtotextAI-Frontend", content)
        self.assertIn("https://github.com/vk93102/HandtotextAI-Backend", content)
        self.assertIn("https://drive.google.com/file/d/1wkw9F5njJeNiZ_bltCMBCbArgOQmcg1q/view?usp=sharing", content)


if __name__ == "__main__":
    unittest.main()
