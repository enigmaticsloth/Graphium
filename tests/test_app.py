import io
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def widget(elements, label):
    return next(e for e in elements if e.label == label)


class AppTests(unittest.TestCase):
    def assert_clean(self, app):
        self.assertFalse(list(app.exception), [e.value for e in app.exception])
        self.assertFalse(list(app.error), [e.value for e in app.error])

    def test_axis_inputs_update_preview_validate_and_restore_auto(self):
        app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py')).run(timeout=30)
        with patch('streamlit.pyplot') as preview:
            widget(app.checkbox, 'Use example data').check().run(timeout=30)
            original_limits = preview.call_args.args[0].axes[0].get_ylim()
            self.assertIsNone(widget(app.number_input, 'Y-axis maximum').value)
            widget(app.number_input, 'X-axis maximum').set_value(12.0)
            widget(app.number_input, 'Y-axis maximum').set_value(100.0)
            app.run(timeout=30)
            self.assert_clean(app)
            ax = preview.call_args.args[0].axes[0]
            self.assertEqual(ax.get_xlim()[1], 12)
            self.assertEqual(ax.get_ylim()[1], 100)

            widget(app.number_input, 'Y-axis minimum').set_value(100.0).run(timeout=30)
            self.assertFalse(list(app.exception))
            self.assertIn('Y-axis minimum', app.error[0].value)
            self.assertFalse(list(app.code))
            widget(app.number_input, 'Y-axis minimum').set_value(None)
            widget(app.number_input, 'Y-axis maximum').set_value(None)
            widget(app.number_input, 'X-axis maximum').set_value(None)
            app.run(timeout=30)
            self.assert_clean(app)
            self.assertEqual(preview.call_args.args[0].axes[0].get_ylim(), original_limits)

            widget(app.radio, 'Chart type').set_value('Pie Chart').run(timeout=30)
            self.assert_clean(app)
            self.assertFalse([e for e in app.number_input if '-axis' in e.label])

    def test_templates_manual_label_lifecycle_and_bar_layouts(self):
        app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py')).run(timeout=30)
        widget(app.checkbox, 'Use example data').check().run(timeout=30)
        self.assert_clean(app)
        widget(app.button, 'Add label').click().run(timeout=30)
        widget(app.selectbox, 'Place above').set_value(('48h', 'TGFβ1+DAPT')).run(timeout=30)
        widget(app.text_input, 'Label text').set_value('##').run(timeout=30)
        widget(app.checkbox, 'Hide all statistical stars').check().run(timeout=30)
        for theme in ('Graphite', 'Paper', 'Carbon'):
            widget(app.selectbox, 'Interface template').select(theme).run(timeout=30)
            self.assert_clean(app)
            self.assertEqual(widget(app.text_input, 'Label text').value, '##')
            self.assertEqual(widget(app.selectbox, 'Place above').value, ('48h', 'TGFβ1+DAPT'))
        widget(app.button, 'Add label').click().run(timeout=30)
        self.assertEqual(widget(app.text_input, 'Label text').value, '#')
        widget(app.button, 'Delete label').click().run(timeout=30)
        self.assertEqual(widget(app.text_input, 'Label text').value, '##')
        widget(app.button, 'Delete label').click().run(timeout=30)
        self.assertFalse([e for e in app.text_input if e.label == 'Label text'])
        widget(app.checkbox, 'Grouped bars').uncheck().run(timeout=30)
        widget(app.button, 'Add label').click().run(timeout=30)
        for layout in ('Clustered (legend)', 'Separate bars (label under each)'):
            widget(app.radio, 'Bar layout').set_value(layout).run(timeout=30)
            self.assert_clean(app)
            self.assertEqual(widget(app.text_input, 'Label text').value, '#')

    def test_custom_figure_dimensions_on_all_chart_types(self):
        app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py')).run(timeout=30)
        with patch('streamlit.pyplot') as preview:
            widget(app.checkbox, 'Use example data').check().run(timeout=30)
            for chart in ('Bar Chart', 'Line Chart', 'Box Plot', 'Violin Plot',
                          'Scatter Plot', 'Pie Chart', 'Heatmap'):
                with self.subTest(chart=chart):
                    widget(app.radio, 'Chart type').set_value(chart).run(timeout=30)
                    widget(app.number_input, 'Figure width (in)').set_value(7.25)
                    widget(app.number_input, 'Figure height (in)').set_value(4.25)
                    app.run(timeout=30)
                    self.assert_clean(app)
                    fig = preview.call_args.args[0]
                    self.assertEqual(list(fig.get_size_inches()), [7.25, 4.25])
                    self.assertIsNone(preview.call_args.kwargs['bbox_inches'])

    def test_manual_labels_are_scoped_to_source(self):
        # Exercise source switching without requiring a browser upload.
        app = AppTest.from_string('''
import streamlit as st
from ui_components import manual_label_editor
scope = st.selectbox('Sheet', ['one', 'two'])
manual_label_editor(scope, {(None, 'Ctrl'): 'Ctrl'})
''').run(timeout=30)
        widget(app.button, 'Add label').click().run(timeout=30)
        widget(app.text_input, 'Label text').set_value('†').run(timeout=30)
        widget(app.selectbox, 'Sheet').select('two').run(timeout=30)
        self.assertFalse([e for e in app.text_input if e.label == 'Label text'])
        widget(app.selectbox, 'Sheet').select('one').run(timeout=30)
        self.assertEqual(widget(app.text_input, 'Label text').value, '†')
        self.assert_clean(app)

    def test_hide_selected_comparisons_and_all_stars_keeps_results_and_manual_labels(self):
        from plot_engine import bar_chart

        app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py')).run(timeout=30)
        with patch('streamlit.pyplot') as preview, patch('plot_engine.bar_chart', wraps=bar_chart) as plotted:
            widget(app.checkbox, 'Use example data').check().run(timeout=30)
            widget(app.checkbox, 'Show non-significant (ns) on chart').check().run(timeout=30)
            widget(app.button, 'Add label').click().run(timeout=30)
            self.assert_clean(app)
            original = plotted.call_args.kwargs['sig_annotations']
            self.assertEqual(len(original), 9)
            original_tables = [element.value.to_dict() for element in app.dataframe
                               if 'Comparison' in element.value.columns]
            self.assertEqual(len(original_tables), 3)

            widget(app.multiselect, 'Hide stars for these comparisons').set_value(
                ['Ctrl vs TGFβ1']).run(timeout=30)
            self.assert_clean(app)
            remaining = plotted.call_args.kwargs['sig_annotations']
            self.assertEqual(len(remaining), 6)
            self.assertTrue(all(ann['group_idx'] == 2 for ann in remaining))

            widget(app.checkbox, 'Hide all statistical stars').check().run(timeout=30)
            self.assert_clean(app)
            self.assertIsNone(plotted.call_args.kwargs['sig_annotations'])
            self.assertEqual([text.get_text() for text in preview.call_args.args[0].axes[0].texts], ['#'])
            self.assertEqual([element.value.to_dict() for element in app.dataframe
                              if 'Comparison' in element.value.columns], original_tables)

            widget(app.checkbox, 'Hide all statistical stars').uncheck().run(timeout=30)
            self.assertEqual(len(plotted.call_args.kwargs['sig_annotations']), 6)
            widget(app.multiselect, 'Hide stars for these comparisons').set_value([]).run(timeout=30)
            self.assertEqual(plotted.call_args.kwargs['sig_annotations'], original)
            self.assert_clean(app)

    def test_hide_all_stars_on_flat_bar_box_and_violin(self):
        app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py')).run(timeout=30)
        with patch('streamlit.pyplot') as preview:
            widget(app.checkbox, 'Use example data').check().run(timeout=30)
            widget(app.checkbox, 'Grouped bars').uncheck().run(timeout=30)
            for chart in ('Bar Chart', 'Box Plot', 'Violin Plot'):
                with self.subTest(chart=chart):
                    widget(app.radio, 'Chart type').set_value(chart).run(timeout=30)
                    widget(app.checkbox, 'Show non-significant (ns) on chart').check()
                    widget(app.checkbox, 'Hide all statistical stars').uncheck().run(timeout=30)
                    self.assertTrue(preview.call_args.args[0].axes[0].texts)
                    widget(app.checkbox, 'Hide all statistical stars').check().run(timeout=30)
                    self.assert_clean(app)
                    self.assertFalse(preview.call_args.args[0].axes[0].texts)
                    self.assertTrue(widget(app.checkbox, 'Auto-run statistics').value)
                    self.assertTrue([element for element in app.dataframe
                                     if 'Comparison' in element.value.columns])

    def test_selected_t_tests_and_star_visibility_are_independent(self):
        app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py')).run(timeout=30)
        with patch('streamlit.pyplot') as preview:
            widget(app.checkbox, 'Use example data').check().run(timeout=30)
            widget(app.radio, 'Test method').set_value('t-test').run(timeout=30)
            self.assert_clean(app)
            self.assertFalse([e for e in app.dataframe if 'Comparison' in e.value.columns])
            pairs = ['Ctrl vs TGFβ1', 'TGFβ1 vs TGFβ1+DAPT']
            widget(app.multiselect, 't-test comparisons').set_value(pairs).run(timeout=30)
            self.assert_clean(app)
            tables = [e.value for e in app.dataframe if 'Comparison' in e.value.columns]
            self.assertEqual(len(tables), 3)
            for table in tables:
                self.assertEqual(table['Comparison'].tolist(), pairs)
                self.assertIn('t statistic', table)
                self.assertEqual(table['n (group 1)'].tolist(), [6, 6])
            widget(app.checkbox, 'Hide all statistical stars').check().run(timeout=30)
            self.assertFalse(preview.call_args.args[0].axes[0].texts)
            self.assertEqual([e.value.to_dict() for e in app.dataframe if 'Comparison' in e.value.columns],
                             [table.to_dict() for table in tables])

            for method in ('Student (equal variance)', 'Paired (matched rows)'):
                widget(app.selectbox, 't-test type').select(method).run(timeout=30)
                self.assert_clean(app)
                self.assertFalse(list(app.warning))
            widget(app.multiselect, 't-test comparisons').set_value([]).run(timeout=30)
            self.assertFalse([e for e in app.dataframe if 'Comparison' in e.value.columns])
            self.assert_clean(app)

    def test_paired_t_tests_keep_source_row_alignment_in_grouped_upload(self):
        def uploaded_file(*args, **kwargs):
            upload = io.BytesIO(b'A,B,Spacer,A.1,B.1\n1,2,,2,3\n,100,,,50\n3,4,,6,7\n7,9,,8,10\nGene1,,,Gene2,\n')
            upload.name = 'paired.csv'
            return upload

        with patch('streamlit.file_uploader', side_effect=uploaded_file), patch('streamlit.pyplot'):
            app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py')).run(timeout=30)
            widget(app.radio, 'Test method').set_value('t-test').run(timeout=30)
            widget(app.selectbox, 't-test type').select('Paired (matched rows)')
            widget(app.multiselect, 't-test comparisons').set_value(['A vs B']).run(timeout=30)
            self.assert_clean(app)
            self.assertFalse(list(app.warning))
            tables = [e.value for e in app.dataframe if 'Comparison' in e.value.columns]
            self.assertEqual(len(tables), 2)
            for table in tables:
                self.assertEqual(table['n (group 1)'].tolist(), [3])
                self.assertEqual(table['n (group 2)'].tolist(), [3])
                self.assertEqual(table['t statistic'].tolist(), ['-4.0000'])

    def test_timepoint_names_can_be_edited_without_changing_data_or_comparisons(self):
        def uploaded_file(*args, **kwargs):
            upload = io.BytesIO(b'ctrl 24h,SB4 24h,Spacer,Ctrl 48h,SB4 48h\n'
                                b'27,25,,55,63\n33,33,,58,68\n32,38,,60,79\n30,40,,64,81\n')
            upload.name = 'timepoints.csv'
            return upload

        with patch('streamlit.file_uploader', side_effect=uploaded_file), patch('streamlit.pyplot') as preview:
            app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py')).run(timeout=30)
            self.assert_clean(app)
            ax = preview.call_args.args[0].axes[0]
            self.assertEqual([label.get_text() for label in ax.get_xticklabels()], ['24h', '48h'])
            self.assertEqual([label.get_text() for label in ax.get_legend().get_texts()], ['ctrl', 'SB4'])
            bar_heights = [bar.get_height() for bar in ax.patches]
            widget(app.radio, 'Test method').set_value('t-test').run(timeout=30)
            widget(app.multiselect, 't-test comparisons').set_value(['ctrl vs SB4']).run(timeout=30)
            tables_before = [e.value for e in app.dataframe if 'Comparison' in e.value.columns]
            widget(app.button, 'Add label').click().run(timeout=30)
            widget(app.selectbox, 'Place above').set_value(('48h', 'SB4')).run(timeout=30)
            widget(app.multiselect, 'Hide stars for these comparisons').set_value(['ctrl vs SB4']).run(timeout=30)

            widget(app.text_input, 'Category name: 24h').set_value('24 hours')
            widget(app.text_input, 'Category name: 48h').set_value('48 hours')
            widget(app.text_input, 'Condition name: SB4').set_value('SB')
            app.run(timeout=30)
            self.assert_clean(app)
            ax = preview.call_args.args[0].axes[0]
            self.assertEqual([label.get_text() for label in ax.get_xticklabels()], ['24 hours', '48 hours'])
            self.assertEqual([label.get_text() for label in ax.get_legend().get_texts()], ['ctrl', 'SB'])
            self.assertEqual([bar.get_height() for bar in ax.patches], bar_heights)
            self.assertEqual([text.get_text() for text in ax.texts], ['#'])
            self.assertEqual(widget(app.selectbox, 'Place above').value, ('48h', 'SB4'))
            self.assertEqual(widget(app.multiselect, 't-test comparisons').value, ['ctrl vs SB4'])
            self.assertEqual(widget(app.multiselect, 'Hide stars for these comparisons').value, ['ctrl vs SB4'])
            self.assertEqual([tab.label for tab in app.tabs], ['24 hours', '48 hours'])
            tables_after = [e.value for e in app.dataframe if 'Comparison' in e.value.columns]
            self.assertEqual(len(tables_after), 2)
            for before, after in zip(tables_before, tables_after):
                self.assertEqual(after['Comparison'].tolist(), ['ctrl vs SB'])
                self.assertEqual(before['p (adjusted)'].tolist(), after['p (adjusted)'].tolist())

    def test_display_names_are_scoped_and_restored(self):
        app = AppTest.from_string('''
import streamlit as st
from ui_components import grouped_name_editor
scope = st.selectbox('Sheet', ['one', 'two'])
grouped_name_editor(scope, ['Block 1', 'Block 2'], ['Ctrl', 'SB4'])
''').run(timeout=30)
        widget(app.text_input, 'Category name: Block 1').set_value('24h')
        widget(app.text_input, 'Condition name: SB4').set_value('SB').run(timeout=30)
        widget(app.selectbox, 'Sheet').select('two').run(timeout=30)
        self.assertEqual(widget(app.text_input, 'Category name: Block 1').value, 'Block 1')
        self.assertEqual(widget(app.text_input, 'Condition name: SB4').value, 'SB4')
        widget(app.selectbox, 'Sheet').select('one').run(timeout=30)
        self.assertEqual(widget(app.text_input, 'Category name: Block 1').value, '24h')
        self.assertEqual(widget(app.text_input, 'Condition name: SB4').value, 'SB')
        self.assert_clean(app)


if __name__ == '__main__':
    unittest.main()
