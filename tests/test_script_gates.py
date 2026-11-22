import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from batch_01.batch_runner import add_character_intro, effective_scene_caption, source_files, validate_spec


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

    def test_existing_source_intro_is_not_duplicated_by_pipeline(self):
        path = ROOT / "batch_01" / "source" / "26_hero_twins.json"
        spec = json.loads(path.read_text(encoding="utf-8-sig"))
        source_caption = spec["scenes"][0]["caption"]
        effective = effective_scene_caption(spec, 0, source_caption, [])
        self.assertEqual(effective.lower().count("k’iche’ maya tradition"), 1)
        self.assertNotIn("In K’iche’ Maya tradition, In K’iche’ Maya tradition", effective)

    def test_episode_27_existing_akan_source_intro_is_not_duplicated(self):
        path = ROOT / "batch_01" / "source" / "27_anansi.json"
        spec = json.loads(path.read_text(encoding="utf-8-sig"))
        effective = effective_scene_caption(spec, 0, spec["scenes"][0]["caption"], [])
        self.assertEqual(effective.lower().count("akan"), 1)
        self.assertNotIn("In Akan / Ghana tradition", effective)

    def test_first_use_minotaur_gets_short_non_spoiler_intro(self):
        effective = add_character_intro("He plans to confront the Minotaur. Few expect him to emerge.", [])
        self.assertEqual(effective, "He plans to confront the Minotaur, a bull-headed monster. Few expect him to emerge.")

    def test_first_use_intro_is_not_repeated(self):
        first = add_character_intro("He plans to confront the Minotaur.", [])
        second = add_character_intro("Theseus meets the Minotaur.", [first])
        self.assertEqual(second, "Theseus meets the Minotaur.")

    def test_minotaur_is_covered_by_the_validation_gate(self):
        path = ROOT / "batch_01" / "source" / "32_ariadne_thread.json"
        spec = json.loads(path.read_text(encoding="utf-8-sig"))
        self.assertEqual(validate_spec(spec), [])


if __name__ == "__main__":
    unittest.main()
