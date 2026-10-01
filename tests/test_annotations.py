import io
import unittest

import matplotlib.pyplot as plt
import numpy as np

from annotation_engine import spaced_symbols
from plot_engine import bar_chart, box_plot, violin_plot


class AnnotationTests(unittest.TestCase):
    def tearDown(self):
        plt.close('all')

    def assert_labels_fit(self, fig):
        fig.canvas.draw()
        ax = fig.axes[0]
        renderer = fig.canvas.get_renderer()
        boxes = [t.get_window_extent(renderer) for t in ax.texts]
        for i, box in enumerate(boxes):
            self.assertLessEqual(box.y1, ax.bbox.ymax + 1)
            for other in boxes[i + 1:]:
                self.assertFalse(box.overlaps(other), 'Annotation text overlaps')

    def test_symbol_spacing_preserves_meaning(self):
        for count in range(1, 5):
            text = spaced_symbols('*' * count, 2)
            self.assertEqual(text.replace('\u2009', ''), '*' * count)
        self.assertEqual(spaced_symbols('p < 0.05'), 'p < 0.05')
        self.assertEqual(spaced_symbols('##', 0), '##')

    def test_horizontal_comparisons_and_manual_label_at_different_scales(self):
        for scale, size in [(1e-6, (3, 3)), (1, (8, 5)), (1e6, (6, 4))]:
            with self.subTest(scale=scale):
                data = {('A', ''): [x * scale for x in [40, 45, 50, 55, 65]]}
                fig = bar_chart(data, ['A'], [''], figsize=size, show_legend=False,
                                sig_annotations=[dict(cat='A', group_idx=0, text=t)
                                                 for t in ['*', '**', '***']],
                                custom_annotations=[dict(cat='A', text='#')])
                self.assertEqual(len(fig.axes[0].texts), 2)
                comparisons = fig.axes[0].texts[0].get_text().split('\u2003\u2003')
                self.assertEqual([text.replace('\u2009', '') for text in comparisons],
                                 ['*', '**', '***'])
                self.assert_labels_fit(fig)
                bottom = min(t.get_position()[1] for t in fig.axes[0].texts)
                self.assertGreater(bottom, 65 * scale)

    def test_automatic_stars_align_across_bars_and_comparisons(self):
        data = {('Ctrl', ''): [59, 90, 70, 60, 77, 85],
                ('Low', ''): [52, 56, 61, 65, 54, 58],
                ('High', ''): [45, 55, 47, 50, 44, 48]}
        fig = bar_chart(
            data, ['Ctrl', 'Low', 'High'], [''], show_legend=False,
            sig_annotations=[dict(cat='Low', group_idx=0, text='*'),
                             dict(cat='High', group_idx=0, text='**'),
                             dict(cat='High', group_idx=0, text='*')],
        )
        ax = fig.axes[0]
        self.assertEqual(len(ax.texts), 2)
        self.assertEqual(ax.texts[0].get_position()[1], ax.texts[1].get_position()[1])
        self.assertGreater(ax.texts[0].get_position()[1], 90)
        self.assertEqual(ax.texts[1].get_text().replace('\u2009', ''), '**\u2003\u2003*')
        self.assert_labels_fit(fig)

    def test_bracket_clears_tall_intermediate_bar(self):
        data = {('A', ''): [1, 2, 3], ('B', ''): [80, 90, 100], ('C', ''): [2, 3, 4]}
        fig = bar_chart(data, list('ABC'), [''], show_legend=False,
                        sig_annotations=[dict(cat1='A', cat2='C', text='***')],
                        custom_annotations=[dict(cat='B', text='#')])
        ax = fig.axes[0]
        bracket = [line for line in ax.lines if len(line.get_xdata()) == 4][0]
        self.assertGreater(min(bracket.get_ydata()), 100)
        self.assert_labels_fit(fig)

    def test_dense_grouped_comparisons_remain_in_one_horizontal_row(self):
        categories, groups = ['A', 'B', 'C'], ['Ctrl', 'Low', 'High']
        data = {(cat, group): [1, 2, 3] for cat in categories for group in groups}
        annotations = [dict(cat=cat, group_idx=gi, text=stars)
                       for cat in categories
                       for gi, stars in [(1, '**'), (2, '***'), (2, '**')]]
        fig = bar_chart(data, categories, groups, figsize=(6, 4),
                        sig_annotations=annotations)
        self.assertEqual(len({text.get_position()[1] for text in fig.axes[0].texts}), 1)
        self.assert_labels_fit(fig)

    def test_manual_labels_on_all_supported_plot_types(self):
        data = {'Ctrl': [1, 2, 3, 4], 'Drug': [3, 4, 6, 7]}
        for plot in (box_plot, violin_plot):
            with self.subTest(plot=plot.__name__):
                fig = plot(data, list(data),
                           sig_annotations=[dict(g1='Ctrl', g2='Drug', text='**')],
                           custom_annotations=[dict(group='Drug', text='#', y_offset=6)])
                self.assert_labels_fit(fig)
                self.assertIn('#', [t.get_text() for t in fig.axes[0].texts])

    def test_exports_and_sd_error_bar_clearance(self):
        values = [0, 10]
        fig = bar_chart({('A', ''): values}, ['A'], [''], show_points=False,
                        error_type='SD', show_legend=False,
                        custom_annotations=[dict(cat='A', text='#')])
        self.assertGreater(fig.axes[0].texts[0].get_position()[1],
                           np.mean(values) + np.std(values, ddof=1))
        for fmt in ('png', 'tiff', 'svg', 'pdf'):
            with self.subTest(format=fmt):
                buf = io.BytesIO()
                fig.savefig(buf, format=fmt, dpi=300, bbox_inches='tight')
                self.assertGreater(len(buf.getvalue()), 1000)
        self.assert_labels_fit(fig)


if __name__ == '__main__':
    unittest.main()
