from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RequirementsContractTests(unittest.TestCase):
    def test_requirements_include_local_adapter_runtime_dependencies(self) -> None:
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

        for dependency in ("scipy", "tqdm", "GitPython"):
            with self.subTest(dependency=dependency):
                self.assertIn(dependency, requirements)

    def test_readme_installs_requirements_file_for_venv_setup(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("# Create the project virtual environment", readme)
        self.assertIn("python -m venv .venv", readme)
        self.assertIn("# Install dependencies into the venv with pip", readme)
        self.assertIn(".venv/bin/python -m pip install -r requirements.txt", readme)
        self.assertIn("# Create the project virtual environment with uv", readme)
        self.assertIn("uv venv .venv", readme)
        self.assertIn("# Install dependencies into the venv with uv", readme)
        self.assertIn("uv pip install --python .venv/bin/python -r requirements.txt", readme)


if __name__ == "__main__":
    unittest.main()
