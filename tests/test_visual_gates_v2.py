import importlib.util
import unittest
from pathlib import Path


MODULE = Path(__file__).parents[1] / "batch_01" / "visual_gates_v2.py"
spec = importlib.util.spec_from_file_location("visual_gates_v2", MODULE)
gates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gates)


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


if __name__ == "__main__":
    unittest.main()
