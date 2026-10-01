import unittest

import numpy as np
from scipy import stats

from stat_engine import auto_analyze, benjamini_hochberg, pairwise_t_tests, p_to_stars


class SelectedTTestTests(unittest.TestCase):
    def setUp(self):
        self.data = {'A': [1, 2, 3, 4, 6], 'B': [2, 5, 8, 10], 'C': [8, 9, 10, 11, 12]}

    def test_welch_and_student_match_their_distinct_formulas(self):
        a, b = np.array(self.data['A']), np.array(self.data['B'])
        for method in ('welch', 'student'):
            with self.subTest(method=method):
                result = pairwise_t_tests(self.data, [('A', 'B')], method, 'none')
                row = result.pairwise[0]
                if method == 'welch':
                    v1, v2 = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
                    variance = v1 + v2
                    df = variance ** 2 / (v1 ** 2 / (len(a) - 1) + v2 ** 2 / (len(b) - 1))
                else:
                    df = len(a) + len(b) - 2
                    pooled = ((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / df
                    variance = pooled * (1 / len(a) + 1 / len(b))
                expected_t = (a.mean() - b.mean()) / np.sqrt(variance)
                self.assertAlmostEqual(row.statistic, expected_t)
                self.assertAlmostEqual(row.p_value, 2 * stats.t.sf(abs(expected_t), df))
                self.assertEqual((row.n1, row.n2), (5, 4))
                self.assertTrue(result.pairwise_only)
                self.assertIsNone(result.p_value)

    def test_paired_missing_rows_are_removed_together(self):
        data = {'A': [1, np.nan, 3, 7], 'B': [2, 100, 4, 9]}
        row = pairwise_t_tests(data, [('A', 'B')], 'paired', 'none').pairwise[0]
        self.assertEqual((row.n1, row.n2), (3, 3))
        self.assertAlmostEqual(row.statistic, -4)
        self.assertAlmostEqual(row.p_value, 2 * stats.t.sf(4, 2))
        self.assertAlmostEqual(row.effect_size, -4 / np.sqrt(3))
        self.assertEqual(row.effect_label, "Cohen's dz")

    def test_only_selected_unique_pairs_enter_correction(self):
        result = pairwise_t_tests(self.data, [('A', 'B'), ('B', 'A'), ('A', 'C')],
                                 correction='bonferroni')
        self.assertEqual([(p.group1, p.group2) for p in result.pairwise], [('A', 'B'), ('A', 'C')])
        for row in result.pairwise:
            self.assertAlmostEqual(row.p_adjusted, min(1, row.p_value * 2))
            self.assertEqual(row.stars, p_to_stars(row.p_adjusted))

    def test_fdr_adjustments_are_monotonic_and_use_selected_family(self):
        result = pairwise_t_tests(self.data, [('A', 'B'), ('A', 'C'), ('B', 'C')], correction='fdr')
        ordered = sorted(result.pairwise, key=lambda row: row.p_value)
        expected = np.minimum.accumulate(
            [min(1, row.p_value * 3 / rank) for rank, row in enumerate(ordered, 1)][::-1])[::-1]
        np.testing.assert_allclose([row.p_adjusted for row in ordered], expected)

    def test_automatic_fdr_backpropagates_smaller_adjustments_in_original_order(self):
        # The smallest raw p-value needs the next rank's smaller adjustment.
        np.testing.assert_allclose(benjamini_hochberg([0.04, 0.01, 0.011]),
                                   [0.04, 0.0165, 0.0165])
        self.assertEqual(benjamini_hochberg([]), [])
        self.assertEqual(benjamini_hochberg([0.8]), [0.8])
        result = auto_analyze(self.data, correction='fdr')
        ordered = sorted(result.pairwise, key=lambda row: row.p_value)
        expected = np.minimum.accumulate(
            [min(1, row.p_value * 3 / rank) for rank, row in enumerate(ordered, 1)][::-1])[::-1]
        np.testing.assert_allclose([row.p_adjusted for row in ordered], expected)
        for row in result.pairwise:
            self.assertEqual(row.stars, p_to_stars(row.p_adjusted))

    def test_invalid_pairs_and_insufficient_or_constant_samples(self):
        for comparisons in ([], [('A', 'A')], [('A', 'missing')]):
            with self.subTest(comparisons=comparisons), self.assertRaises(ValueError):
                pairwise_t_tests(self.data, comparisons)
        for data, method in (({'A': [1], 'B': [2, 3]}, 'welch'),
                             ({'A': [1, 2], 'B': [2, 3, 4]}, 'paired'),
                             ({'A': [1, np.nan], 'B': [np.nan, 2]}, 'paired'),
                             ({'A': [1, 1], 'B': [1, 1]}, 'welch')):
            with self.subTest(data=data, method=method), self.assertRaises(ValueError):
                pairwise_t_tests(data, [('A', 'B')], method)


if __name__ == '__main__':
    unittest.main()
