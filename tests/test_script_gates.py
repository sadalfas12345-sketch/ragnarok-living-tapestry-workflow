import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from batch_01.batch_runner import source_files, validate_spec


ROOT = Path(__file__).resolve().parents[1]


class ScriptGateRegressionTests(unittest.TestCase):
    def test_all_authoritative_sources_pass_script_gate(self):
        failures = []
        for path in source_files():
            spec = json.loads(path.read_text(encoding="utf-8-sig"))
            errors = validate_spec(spec)
            if errors:
                failures.append(f"{path.name}: {errors}")
        self.assertEqual(failures, [])

    def test_episode_26_uses_canonical_kiche_spelling(self):
        path = ROOT / "batch_01" / "source" / "26_hero_twins.json"
        spec = json.loads(path.read_text(encoding="utf-8-sig"))
        first = spec["scenes"][0]["caption"]
        self.assertIn("K’iche’", first)
        self.assertNotIn("K'iche'", first)
        self.assertNotIn("Kiche", first)
        self.assertNotIn("â", first)
        self.assertNotIn("�", first)

    def test_episode_26_introduces_death_lords_before_using_names(self):
        path = ROOT / "batch_01" / "source" / "26_hero_twins.json"
        spec = json.loads(path.read_text(encoding="utf-8-sig"))
        first = spec["scenes"][0]["caption"]
        self.assertLess(first.index("Lords of Death"), first.index("One Death"))
        self.assertLess(first.index("Lords of Death"), first.index("Seven Death"))

    def test_episode_26_preserves_causal_death_sequence(self):
        path = ROOT / "batch_01" / "source" / "26_hero_twins.json"
        spec = json.loads(path.read_text(encoding="utf-8-sig"))
        captions = [scene["caption"] for scene in spec["scenes"]]
        joined = " ".join(captions)
        self.assertIn("only through deception", joined)
        self.assertIn("leapt into a fire", joined)
        self.assertIn("returned as traveling performers", joined)
        self.assertNotIn("The Lords killed the twins", joined)


if __name__ == "__main__":
    unittest.main()
