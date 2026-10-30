import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trend import trend


class TrendWording(unittest.TestCase):
    def test_a_decrease_reads_down_from_the_larger_to_the_smaller(self):
        self.assertEqual(trend(120, 140, 132, 144), 'down from 140 to 120')

    def test_an_increase_reads_up_from_the_smaller_to_the_larger(self):
        self.assertEqual(trend(150, 132, 124, 140), 'up from 132 to 150')

    def test_a_median_inside_the_spread_is_within_noise(self):
        self.assertEqual(trend(136, 140, 128, 156), 'within noise')


if __name__ == '__main__':
    unittest.main()
