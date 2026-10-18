import io
import unittest
from pathlib import Path
from unittest.mock import patch

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from streamlit.testing.v1 import AppTest

from data_parser import prepare_sheet, parse_blocks
from plot_engine import bar_chart, fig_to_buf


HIERARCHICAL_CSV = '''Epithelial,,,,,,Mesenchymal,,,,,
Distal,,,Proximal,,,Distal,,,Proximal,,
Ctrl,TGFβ,T+D,Ctrl,TGFβ,T+D,Ctrl,TGFβ,T+D,Ctrl,TGFβ,T+D
10,3,7,20,4,12,30,5,20,40,6,25
12,4,8,22,5,14,32,6,22,42,7,27
14,5,9,24,6,16,34,7,24,44,8,29
'''


def widget(elements, label):
    return next(element for element in elements if element.label == label)


class HierarchicalSheetTests(unittest.TestCase):
    def test_three_header_rows_preserve_categories_conditions_and_numeric_observations(self):
        raw = pd.read_csv(io.StringIO(HIERARCHICAL_CSV))
        original = raw.copy(deep=True)
        prepared = prepare_sheet(raw)
        blocks, title = parse_blocks(prepared)
        self.assertIsNone(title)
        self.assertEqual([block['label'] for block in blocks],
                         ['Epithelial / Distal', 'Epithelial / Proximal',
                          'Mesenchymal / Distal', 'Mesenchymal / Proximal'])
        self.assertEqual([block['display_label'] for block in blocks], ['Distal', 'Proximal'] * 2)
        self.assertEqual([block['parent_label'] for block in blocks],
                         ['Epithelial'] * 2 + ['Mesenchymal'] * 2)
        self.assertEqual(list(blocks[-1]['conditions']), ['Ctrl', 'TGFβ', 'T+D'])
        self.assertEqual(blocks[-1]['conditions']['T+D'], [25, 27, 29])
        self.assertEqual(prepared.shape, (3, 12))
        self.assertTrue(all(pd.api.types.is_numeric_dtype(dtype) for dtype in prepared.dtypes))
        pd.testing.assert_frame_equal(raw, original)

    def test_two_header_rows_preserve_missing_source_rows_and_zeros(self):
        raw = pd.read_csv(io.StringIO('Distal,,Proximal,\nCtrl,Drug,Ctrl,Drug\n'
                                     '1,0,4,8\n,2,,10\n3,4,6,12\n'))
        blocks, _ = parse_blocks(prepare_sheet(raw))
        self.assertEqual([block['label'] for block in blocks], ['Distal', 'Proximal'])
        self.assertTrue(all(block['parent_label'] is None for block in blocks))
        np.testing.assert_allclose(blocks[0]['aligned_conditions']['Ctrl'], [1, np.nan, 3])
        self.assertEqual(blocks[0]['conditions']['Drug'], [0, 2, 4])

    def test_ordinary_tables_pass_through_without_inventing_header_levels(self):
        for raw in (pd.DataFrame({'Ctrl': [1, 2], 'Drug': [3, 4]}),
                    pd.DataFrame({'Ctrl': [1, 2, 'Gene A'], 'Drug': [3, 4, None]})):
            self.assertIs(prepare_sheet(raw), raw)

    def test_duplicate_top_headers_remain_distinct_but_have_clean_display_names(self):
        raw = pd.read_csv(io.StringIO(HIERARCHICAL_CSV.split('\n', 1)[1]))
        blocks, _ = parse_blocks(prepare_sheet(raw))
        self.assertEqual([block['display_label'] for block in blocks], ['Distal', 'Proximal'] * 2)
        self.assertEqual([block['label'] for block in blocks],
                         ['Distal', 'Proximal', 'Distal (2)', 'Proximal (2)'])
        self.assertEqual(blocks[2]['conditions']['Ctrl'], [30, 32, 34])


class XAxisGroupPlotTests(unittest.TestCase):
    def tearDown(self):
        plt.close('all')

    def chart(self, **options):
        categories, groups = ['E-D', 'E-P', 'M-D', 'M-P'], ['Ctrl', 'TGFβ', 'T+D']
        return bar_chart(
            {(category, group): [1 + gi, 2 + gi, 3 + gi]
             for category in categories for gi, group in enumerate(groups)}, categories, groups,
            category_labels=dict(zip(categories, ['Distal', 'Proximal'] * 2)),
            category_groups=dict(zip(categories, ['Epithelium'] * 2 + ['Mesenchyme'] * 2)),
            **options)

    def test_group_labels_center_over_their_categories_and_fit_fixed_canvas(self):
        fig = self.chart(figsize=(7.25, 4.25), group_label_fontsize=16,
                         sig_annotations=[dict(cat='M-D', group_idx=1, text='*')],
                         custom_annotations=[dict(cat='E-P', group_idx=2, text='#')])
        fig.canvas.draw()
        ax = fig.axes[0]
        renderer = fig.canvas.get_renderer()
        labels = [text for text in ax.texts if text.get_gid() == 'x-axis-group-label']
        self.assertEqual([text.get_text() for text in labels], ['Epithelium', 'Mesenchyme'])
        self.assertEqual([text.get_text() for text in ax.get_xticklabels()], ['Distal', 'Proximal'] * 2)
        ticks = ax.get_xticks()
        self.assertAlmostEqual(labels[0].get_position()[0], (ticks[0] + ticks[1]) / 2)
        self.assertAlmostEqual(labels[1].get_position()[0], (ticks[2] + ticks[3]) / 2)
        self.assertGreater(ticks[2] - ticks[1], ticks[1] - ticks[0])
        tick_bottom = min(text.get_window_extent(renderer).y0 for text in ax.get_xticklabels())
        for text in labels:
            box = text.get_window_extent(renderer)
            self.assertGreater(box.y0, 0)
            self.assertLess(box.y1, tick_bottom)
        for text in ax.texts:
            box = text.get_window_extent(renderer)
            self.assertGreaterEqual(box.y0, 0)
            self.assertLessEqual(box.y1, fig.bbox.ymax)
        for fmt in ('png', 'tiff'):
            with Image.open(fig_to_buf(fig, fmt=fmt)) as output:
                self.assertEqual(output.size, (2175, 1275))
        svg = fig_to_buf(fig, fmt='svg').getvalue()
        self.assertIn(b'Epithelium', svg)
        self.assertIn(b'Mesenchyme', svg)
        self.assertGreater(len(fig_to_buf(fig, fmt='pdf').getvalue()), 1000)

    def test_lines_can_be_hidden_and_nonadjacent_equal_groups_stay_separate(self):
        fig = bar_chart({(category, ''): [1, 2, 3] for category in 'ABC'}, list('ABC'), [''],
                        category_groups={'A': 'Tissue', 'B': '', 'C': 'Tissue'},
                        group_label_lines=False, show_legend=False)
        ax = fig.axes[0]
        self.assertEqual(len([text for text in ax.texts if text.get_gid() == 'x-axis-group-label']), 2)
        self.assertFalse([line for line in ax.lines if line.get_gid() == 'x-axis-group-line'])


class XAxisGroupAppTests(unittest.TestCase):
    def assert_clean(self, app):
        self.assertFalse(list(app.exception), [element.value for element in app.exception])
        self.assertFalse(list(app.error), [element.value for element in app.error])

    def test_hierarchical_upload_shows_four_categories_and_editable_lower_groups(self):
        def uploaded_file(*args, **kwargs):
            upload = io.BytesIO(HIERARCHICAL_CSV.encode())
            upload.name = 'three_headers.csv'
            return upload

        with patch('streamlit.file_uploader', side_effect=uploaded_file), \
                patch('streamlit.pyplot') as preview, patch('plot_engine.bar_chart', wraps=bar_chart) as plotted:
            app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py')).run(timeout=30)
            self.assert_clean(app)
            self.assertTrue(widget(app.checkbox, 'Grouped bars').value)
            self.assertTrue(widget(app.checkbox, 'Show group labels below x-axis').value)
            self.assertFalse(app.sidebar.dataframe[0].value.attrs)
            ax = preview.call_args.args[0].axes[0]
            self.assertEqual(len(ax.patches), 12)
            self.assertEqual([text.get_text() for text in ax.get_xticklabels()], ['Distal', 'Proximal'] * 2)
            self.assertEqual([text.get_text() for text in ax.texts
                              if text.get_gid() == 'x-axis-group-label'], ['Epithelial', 'Mesenchymal'])
            heights = [bar.get_height() for bar in ax.patches]
            self.assertEqual(len([element for element in app.dataframe if 'Comparison' in element.value]), 4)
            for category in ('Distal', 'Proximal'):
                label = f'Group below {category} (Epithelial / {category})'
                widget(app.text_input, label).set_value('Epithelium')
            app.run(timeout=30)
            self.assert_clean(app)
            self.assertEqual(plotted.call_args.kwargs['category_groups']['Epithelial / Distal'], 'Epithelium')
            self.assertEqual([bar.get_height() for bar in preview.call_args.args[0].axes[0].patches], heights)
            widget(app.checkbox, 'Show group labels below x-axis').uncheck().run(timeout=30)
            self.assert_clean(app)
            self.assertFalse([text for text in preview.call_args.args[0].axes[0].texts
                              if text.get_gid() == 'x-axis-group-label'])


if __name__ == '__main__':
    unittest.main()
