import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from eth_research.policy import decide

class TestPolicy(unittest.TestCase):
    def test_up(self):
        self.assertEqual(decide((.56,.57,.55),(1.0,1.5,2.1)).direction, 'UP')
    def test_down(self):
        self.assertEqual(decide((.44,.43,.45),(.5,1.,1.5)).direction, 'DOWN')
    def test_no_edge(self):
        self.assertEqual(decide((.49,.50,.51),(1.,1.,1.)).reason, 'INSUFFICIENT_DIRECTIONAL_EDGE')
    def test_spread(self):
        self.assertEqual(decide((.60,.60,.50),(1.,1.,1.)).reason, 'EXPERT_DISAGREEMENT')
    def test_distance(self):
        self.assertEqual(decide((.60,.59,.60),(2.01,2.5,3.)).reason, 'OUT_OF_DISTRIBUTION')
    def test_thresholds(self):
        self.assertEqual(decide((.55,.55,.55),(2.,2.,2.)).direction, 'UP')
        self.assertEqual(decide((.45,.45,.45),(2.,2.,2.)).direction, 'DOWN')
    def test_invalid(self):
        with self.assertRaises(ValueError): decide((float('nan'),.6,.6),(1.,1.,1.))

if __name__=='__main__': unittest.main()
