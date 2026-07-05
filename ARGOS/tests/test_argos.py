import unittest

from argos.generator import build_graph
from argos.function_api import evaluate_expected_impacts
from argos.reasoning import ArgosAgent, cop_tracks
from argos.schema import ACTION_TYPES, FUNCTIONS, LINK_TYPES, OBJECT_TYPES
from argos.validation import validate_graph


class ArgosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = build_graph()
        cls.agent = ArgosAgent(cls.graph)

    def test_schema_counts(self):
        self.assertEqual(len(OBJECT_TYPES), 18)
        self.assertEqual(len(LINK_TYPES), 24)
        self.assertEqual(len(ACTION_TYPES), 7)
        self.assertEqual(len(FUNCTIONS), 4)

    def test_generator_scale(self):
        stats = self.graph.stats()
        self.assertGreaterEqual(stats["objectCount"], 5000)
        self.assertGreaterEqual(stats["linkCount"], 15000)

    def test_schema_validation(self):
        result = validate_graph(self.graph)
        self.assertTrue(result["ok"])

    def test_agent_answers_with_evidence(self):
        result = self.agent.ask("K-2에 주둔한 대대는?")
        self.assertEqual(result["mode"], "single-hop")
        self.assertTrue(result["evidence"])

    def test_watch_returns_actions(self):
        result = self.agent.watch_event("ThreatEvent", "TEV-0001")
        self.assertTrue(result["impacts"])
        self.assertTrue(result["actions"])

    def test_korean_natural_language_base_status(self):
        result = self.agent.ask("K-2 비행장 상태 알려줘")
        self.assertEqual(result["mode"], "base-status")
        self.assertTrue(result["evidence"])

    def test_korean_decision_support_question(self):
        result = self.agent.ask("TEV-0001 영향과 지휘 결심 권고")
        self.assertIn(result["mode"], {"watch", "decide"})
        self.assertTrue(result.get("actions"))
        self.assertIn("adapter", result)

    def test_cop_tracks_include_nearest_base(self):
        tracks = cop_tracks(self.graph, limit=5)
        self.assertEqual(len(tracks), 5)
        self.assertIn("nearestBase", tracks[0])

    def test_s2_expected_impact_eval(self):
        graph = build_graph(scenario="S2")
        result = evaluate_expected_impacts(graph, limit=5)
        self.assertGreaterEqual(result["recall"], 0.9)
        self.assertGreaterEqual(result["precision"], 0.9)

    def test_aar_sections_and_evidence(self):
        aar = self.agent.generate_aar(hours=12)
        self.assertEqual(set(aar["sections"]), {"overview", "timeline", "planVsActual", "decisionAnalysis", "lessons"})
        self.assertEqual(set(aar["sectionEvidence"]), set(aar["sections"]))
        self.assertTrue(aar["evidence"])


if __name__ == "__main__":
    unittest.main()
