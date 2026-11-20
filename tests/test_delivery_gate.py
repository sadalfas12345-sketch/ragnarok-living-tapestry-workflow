import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from batch_01.delivery_gate import sha256, validate


class DeliveryGateTests(unittest.TestCase):
    def make_bundle(self):
        root = Path(tempfile.mkdtemp())
        (root / "visual_gates_audit").mkdir()
        (root / "final_vertical_1080x1920.mp4").write_bytes(b"render")
        (root / "Captions_final.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
        (root / "qa_report.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
        (root / "visual_gates_audit" / "visual_gates_report.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
        (root / "lifecycle_status.json").write_text(json.dumps({"status": "complete"}), encoding="utf-8")
        return root

    def test_missing_drive_proof_fails_closed(self):
        result = validate(self.make_bundle())
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("Drive URL" in error for error in result["errors"]))

    def test_matching_drive_proof_passes(self):
        root = self.make_bundle()
        video = root / "final_vertical_1080x1920.mp4"
        result = validate(root, "https://drive.google.com/file/d/example/view", video.name, sha256(video))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(json.loads((root / "delivery_manifest.json").read_text())["status"], "PASS")

    def test_stale_hash_fails(self):
        root = self.make_bundle()
        result = validate(root, "https://drive.google.com/file/d/example/view", "final_vertical_1080x1920.mp4", "0" * 64)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("does not match" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
