import unittest
from golf_agents.strokes_gained import DrGolfBayes

class TestDrGolfBayes(unittest.TestCase):
    def setUp(self):
        self.agent = DrGolfBayes()

    def test_calculate_sg_baseline(self):
        sg = self.agent.calculate_sg_baseline(1)
        self.assertIsNotNone(sg)
        self.assertAlmostEqual(sg['sg_total'], 2.8, places=2)

    def test_estimate_course_fit(self):
        fit = self.agent.estimate_course_fit(1, 'augusta')
        self.assertIsInstance(fit, float)
        self.assertGreaterEqual(fit, 0)
        self.assertLessEqual(fit, 100)

    def test_adjust_for_field_strength(self):
        adj = self.agent.adjust_for_field_strength(2.8, 28.4)
        self.assertAlmostEqual(adj, 2.7, places=2)
        adj_weak = self.agent.adjust_for_field_strength(2.8, 70)
        self.assertAlmostEqual(adj_weak, 2.9, places=2)

if __name__ == "__main__":
    unittest.main()
