import unittest

from workflow_viz.production_graph import build_production_graph, mermaid_workflow


class WorkflowVisualizationTests(unittest.TestCase):
    def test_mermaid_contains_hard_gates_and_retries(self):
        diagram = mermaid_workflow()
        self.assertIn("Timing + visual", diagram)
        self.assertIn("Adversarial +", diagram)
        self.assertIn("retry: visual/timing failure", diagram)
        self.assertIn("Drive verified", diagram)

    def test_fallback_map_is_side_effect_free(self):
        graph = build_production_graph(use_langgraph=False)
        self.assertEqual(graph["stages"][0][0], "source")
        self.assertIn(("qa", "render", "retry: visual/timing failure"), graph["edges"])


if __name__ == "__main__":
    unittest.main()
