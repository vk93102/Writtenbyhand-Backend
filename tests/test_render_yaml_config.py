from pathlib import Path
import unittest


class TestRenderYamlConfig(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.render_yaml = self.root / "render.yaml"

    def test_render_yaml_exists(self):
        self.assertTrue(self.render_yaml.exists())

    def test_render_config_required_fields(self):
        content = self.render_yaml.read_text(encoding="utf-8")
        self.assertIn("services:", content)
        self.assertIn("type: web", content)
        self.assertIn("buildCommand:", content)
        self.assertIn("startCommand:", content)
        self.assertIn("migrate --noinput", content)
        self.assertIn("runserver 0.0.0.0:$PORT", content)


if __name__ == "__main__":
    unittest.main()
