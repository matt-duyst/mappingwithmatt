import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trend import trend, tbt_failure, bytes_failure, requests_failure


class TrendWording(unittest.TestCase):
    def test_a_decrease_reads_down_from_the_larger_to_the_smaller(self):
        self.assertEqual(trend(120, 140, 132, 144), 'down from 140 to 120')

    def test_an_increase_reads_up_from_the_smaller_to_the_larger(self):
        self.assertEqual(trend(150, 132, 124, 140), 'up from 132 to 150')

    def test_a_median_inside_the_spread_is_within_noise(self):
        self.assertEqual(trend(136, 140, 128, 156), 'within noise')


class TbtGate(unittest.TestCase):
    def test_absolute_mode_fails_above_fifty_milliseconds(self):
        self.assertIsNotNone(tbt_failure(51, 10, 'absolute'))
        self.assertIsNone(tbt_failure(50, 10, 'absolute'))

    def test_absolute_mode_ignores_the_baseline_spread(self):
        self.assertIsNotNone(tbt_failure(300, 1000, 'absolute'))

    def test_relative_mode_fails_beyond_a_quarter_over_the_baseline_maximum(self):
        self.assertIsNone(tbt_failure(355, 284, 'relative'))
        self.assertIsNotNone(tbt_failure(356, 284, 'relative'))

    def test_relative_mode_fails_without_a_baseline_spread(self):
        self.assertIsNotNone(tbt_failure(10, None, 'relative'))


class ByteGate(unittest.TestCase):
    def test_the_default_allows_ten_percent(self):
        self.assertIsNone(bytes_failure(110000, 100000))
        self.assertIsNotNone(bytes_failure(110001, 100000))

    def test_an_approved_allowance_of_fifteen_percent(self):
        self.assertIsNone(bytes_failure(115000, 100000, 0.15))
        self.assertIsNotNone(bytes_failure(115001, 100000, 0.15))


class RequestGate(unittest.TestCase):
    def test_the_default_allows_no_added_request_on_a_baseline_of_six(self):
        self.assertIsNone(requests_failure(6, 6))
        self.assertIsNotNone(requests_failure(7, 6))

    def test_an_approved_allowance_of_one_admits_one_more_request(self):
        self.assertIsNone(requests_failure(7, 6, 1))
        self.assertIsNotNone(requests_failure(8, 6, 1))

    def test_the_default_keeps_ten_percent_on_a_large_baseline(self):
        self.assertIsNone(requests_failure(66, 60))
        self.assertIsNotNone(requests_failure(67, 60))


if __name__ == '__main__':
    unittest.main()
