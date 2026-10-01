import io
import re
import unittest
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from plot_engine import (
    AxisRangeError, apply_axis_limits, bar_chart, box_plot, heatmap,
    fig_to_buf, line_chart, scatter_plot, violin_plot,
)


class AxisRangeTests(unittest.TestCase):
    def tearDown(self):
        plt.close('all')

    def test_ranges_reach_every_supported_chart(self):
        data = {'A': [1, 2, 3, 4], 'B': [3, 4, 6, 7]}
        factories = {
            'bar': lambda **kw: bar_chart({(g, ''): v for g, v in data.items()},
                                          list(data), [''], **kw),
            'box': lambda **kw: box_plot(data, list(data), **kw),
            'violin': lambda **kw: violin_plot(data, list(data), **kw),
            'line': lambda **kw: line_chart({(i, 'A'): [i + 1] for i in range(3)},
                                            [0, 1, 2], ['A'], **kw),
            'scatter': lambda **kw: scatter_plot([0, 1, 2], [1, 3, 5], **kw),
            'heatmap': lambda **kw: heatmap(np.array([[1, 2], [3, 4]]), **kw),
        }
        for name, factory in factories.items():
            with self.subTest(chart=name):
                fig = factory(xlim=(-1, 5), ylim=(-2, 20))
                ax = fig.axes[0]
                self.assertEqual(ax.get_xlim(), (-1, 5))
                self.assertEqual(ax.get_ylim(), (20, -2) if name == 'heatmap' else (-2, 20))
                fig.canvas.draw()
                self.assertEqual(sorted(ax.get_ylim()), [-2, 20])

    def test_partial_ranges_preserve_automatic_bound_and_accept_zero(self):
        fig = scatter_plot([-4, -3, -2], [-8, -6, -4])
        ax = fig.axes[0]
        original_x, original_y = ax.get_xlim(), ax.get_ylim()
        apply_axis_limits(ax, (None, None), None)
        self.assertEqual(ax.get_xlim(), original_x)
        self.assertEqual(ax.get_ylim(), original_y)
        apply_axis_limits(ax, (None, 0), (None, 0))
        self.assertEqual(ax.get_xlim(), (original_x[0], 0))
        self.assertEqual(ax.get_ylim(), (original_y[0], 0))

    def test_fixed_maximum_survives_annotations_and_all_exports(self):
        fig = bar_chart(
            {('A', ''): [8, 9, 10]}, ['A'], [''], show_legend=False,
            xlim=(-1, 2), ylim=(0, 10),
            sig_annotations=[dict(cat='A', group_idx=0, text='***')],
            custom_annotations=[dict(cat='A', text='#', y_offset=10)],
        )
        ax = fig.axes[0]
        self.assertEqual(ax.get_ylim(), (0, 10))
        self.assertTrue(all(text.get_clip_on() for text in ax.texts))
        for fmt in ('png', 'tiff', 'svg', 'pdf'):
            with self.subTest(format=fmt):
                buf = io.BytesIO()
                fig.savefig(buf, format=fmt, bbox_inches='tight')
                self.assertGreater(len(buf.getvalue()), 1000)
                self.assertEqual(ax.get_xlim(), (-1, 2))
                self.assertEqual(ax.get_ylim(), (0, 10))

    def test_manual_minimum_still_allows_annotation_headroom(self):
        fig = bar_chart(
            {('A', ''): [8, 9, 10]}, ['A'], [''], show_legend=False,
            ylim=(-5, None), custom_annotations=[dict(cat='A', text='#')],
        )
        fig.canvas.draw()
        ax = fig.axes[0]
        self.assertEqual(ax.get_ylim()[0], -5)
        self.assertGreater(ax.get_ylim()[1], ax.texts[0].get_position()[1])

    def test_invalid_ranges_are_rejected(self):
        fig, ax = plt.subplots()
        for bounds in ((3, 3), (4, 2), (None, -1), (np.nan, 5), (0, np.inf)):
            with self.subTest(bounds=bounds):
                with self.assertRaisesRegex(AxisRangeError, 'X-axis minimum'):
                    apply_axis_limits(ax, xlim=bounds)
                self.assertEqual(ax.get_xlim(), (0, 1))

    def test_export_canvas_matches_custom_dimensions(self):
        fig = bar_chart({('A', ''): [1, 2, 3]}, ['A'], [''],
                        figsize=(7.25, 4.25), show_legend=False,
                        custom_annotations=[dict(cat='A', text='#')])
        for fmt in ('png', 'tiff'):
            with self.subTest(format=fmt):
                with Image.open(fig_to_buf(fig, fmt=fmt)) as image:
                    self.assertEqual(image.size, (2175, 1275))
        svg = ET.fromstring(fig_to_buf(fig, fmt='svg').getvalue())
        self.assertEqual(svg.attrib['width'], '522pt')
        self.assertEqual(svg.attrib['height'], '306pt')
        pdf = fig_to_buf(fig, fmt='pdf').getvalue()
        media_box = re.search(rb'/MediaBox\s*\[([^]]+)\]', pdf)
        self.assertEqual([float(v) for v in media_box.group(1).split()], [0, 0, 522, 306])


if __name__ == '__main__':
    unittest.main()
