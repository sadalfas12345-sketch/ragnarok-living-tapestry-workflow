import importlib.util
import json
import unittest
from pathlib import Path


MODULE = Path(__file__).parents[1] / "batch_01" / "visual_gates_v2.py"
spec = importlib.util.spec_from_file_location("visual_gates_v2", MODULE)
gates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gates)
LEXICON = json.loads((MODULE.parent / "character_intro_lexicon.json").read_text(encoding="utf-8"))


class VisualGateUnitTests(unittest.TestCase):
    def test_mean_abs_diff_detects_change(self):
        self.assertEqual(gates.mean_abs_diff(bytes([4, 4]), bytes([4, 4])), 0)
        self.assertEqual(gates.mean_abs_diff(bytes([0, 10]), bytes([10, 0])), 10)

    def test_srt_parser_reads_multiline_caption(self):
        path = Path(__file__).with_name("_gate_test.srt")
        path.write_text("1\n00:00:01,000 --> 00:00:02,250\nWhat if ten suns\nrose at once?\n", encoding="utf-8")
        try:
            captions = gates.parse_srt(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(len(captions), 1)
        self.assertAlmostEqual(captions[0]["start"], 1.0)
        self.assertAlmostEqual(captions[0]["end"], 2.25)
        self.assertIn("What if ten suns", captions[0]["text"])

    def test_feedback_policy_is_episode_agnostic(self):
        self.assertEqual(gates.POLICY["scenes"]["required_visual_beats"], 3)
        self.assertEqual(gates.POLICY["camera"]["default_direction"], "right")
        self.assertTrue(gates.POLICY["audio"]["narration_is_master_clock"])

    def test_artwork_gate_forbids_portrait_fallback(self):
        self.assertTrue(gates.POLICY["artwork"]["require_horizontal_panorama"])
        self.assertFalse(gates.POLICY["artwork"]["allow_legacy_portrait_fallback"])
        self.assertGreaterEqual(gates.POLICY["artwork"]["minimum_width_pixels"], 2500)

    def test_artwork_gate_requires_dense_period_aligned_tableaux(self):
        artwork = gates.POLICY["artwork"]
        self.assertEqual(artwork["density_direction"], "dense_narrative_tableau")
        self.assertIn("meaningful foreground, midground, and background activity", artwork["density_requirements"])
        self.assertIn("culture- and period-aligned clothing, architecture, objects, and materials", artwork["density_requirements"])
        self.assertIn("three copies of the same pose", artwork["density_avoid"])

    def test_provenance_gate_is_source_specific(self):
        self.assertEqual(gates.expected_provenance("Ancient Mesopotamia"), "mesopotamian mythology")
        self.assertEqual(gates.expected_provenance("Ancient Egypt"), "egyptian mythology")
        self.assertIn("mythology", gates.POLICY["provenance"]["recognized_markers"])

    def test_caption_gate_rejects_mojibake(self):
        forbidden = gates.POLICY["rendered_caption_text"]["forbidden_sequences"]
        self.assertIn("Ã¢", forbidden)

    def test_character_intros_are_short_and_spoiler_free(self):
        policy = gates.POLICY["character_intros"]
        self.assertTrue(policy["spoiler_free"])
        forbidden = tuple(policy["forbidden_outcome_terms"])
        for intro in LEXICON.values():
            self.assertLessEqual(len(str(intro).split()), policy["max_inserted_words"])
            self.assertFalse(any(term.lower() in str(intro).lower().split() for term in forbidden))

    def test_prose_gate_requires_smoothing(self):
        self.assertTrue(gates.POLICY["prose"]["smooth_character_intro_joins"])
        self.assertTrue(gates.POLICY["prose"]["reject_awkward_intro_joins"])


if __name__ == "__main__":
    unittest.main()
