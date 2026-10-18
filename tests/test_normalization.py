import io
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from data_transform import normalize_to_control, NormalizationError
from plot_engine import bar_chart, box_plot, violin_plot, calc_stats
from stat_engine import auto_analyze, pairwise_t_tests


def widget(elements, label):
    return next(element for element in elements if element.label == label)


class NormalizationTests(unittest.TestCase):
    def test_control_mean_is_one_with_variation_missing_rows_and_input_preserved(self):
        groups = {'Ctrl': [0.01, np.nan, 0.03], 'Treatment': [0.04, 0.06, 0.08]}
        normalized = normalize_to_control(groups, 'Ctrl')
        np.testing.assert_allclose(normalized['Ctrl'], [0.5, np.nan, 1.5])
        np.testing.assert_allclose(normalized['Treatment'], [2, 3, 4])
        self.assertAlmostEqual(np.nanmean(normalized['Ctrl']), 1)
        self.assertAlmostEqual(calc_stats(normalized['Ctrl'], 'SD')[1], np.sqrt(0.5))
        self.assertAlmostEqual(calc_stats(normalized['Ctrl'], 'SEM')[1], 0.5)
        np.testing.assert_allclose(groups['Ctrl'], [0.01, np.nan, 0.03])
        self.assertEqual(groups['Treatment'], [0.04, 0.06, 0.08])

    def test_invalid_control_is_rejected(self):
        for groups in ({'Treatment': [1, 2]}, {'Ctrl': []}, {'Ctrl': [np.nan]},
                       {'Ctrl': [0, 0]}, {'Ctrl': [-1, 1]},
                       {'Ctrl': [1, np.inf]}, {'Ctrl': [1, -np.inf]}):
            with self.subTest(groups=groups), self.assertRaises(NormalizationError):
                normalize_to_control(groups, 'Ctrl')

    def test_invalid_dimensions_and_nonfinite_output_are_rejected(self):
        for groups in ({'Ctrl': [[1, 2]]}, {'Ctrl': [1, 2], 'Treatment': [np.inf]},
                       {'Ctrl': [1e-320], 'Treatment': [1e300]}):
            with self.subTest(groups=groups), self.assertRaises(NormalizationError):
                normalize_to_control(groups, 'Ctrl')

    def test_paired_statistics_keep_complete_source_rows_after_normalizing(self):
        groups = {'Ctrl': [1, np.nan, 3, 7], 'Treatment': [2, 100, 4, 9]}
        result = pairwise_t_tests(normalize_to_control(groups, 'Ctrl'),
                                  [('Ctrl', 'Treatment')], 'paired', 'none')
        self.assertEqual(result.pairwise[0].n1, 3)
        self.assertEqual(result.pairwise[0].n2, 3)
        self.assertAlmostEqual(result.pairwise[0].statistic, -4)


class NormalizationAppTests(unittest.TestCase):
    def upload(self, content):
        def uploaded_file(*args, **kwargs):
            upload = io.BytesIO(content.encode())
            upload.name = 'observations.csv'
            return upload
        return patch('streamlit.file_uploader', side_effect=uploaded_file)

    def app(self):
        return AppTest.from_file(str(Path(__file__).parents[1] / 'app.py')).run(timeout=30)

    def assert_clean(self, app):
        self.assertFalse(list(app.exception), [element.value for element in app.exception])
        self.assertFalse(list(app.error), [element.value for element in app.error])

    def test_flat_chart_normalizes_plots_stats_and_exports_and_restores_raw(self):
        content = 'Treatment,Ctrl\n0.02,0.01\n0.06,0.02\n0.10,0.03\n0.08,\n'
        with self.upload(content), patch('streamlit.pyplot') as preview, \
                patch('plot_engine.bar_chart', wraps=bar_chart) as plotted, \
                patch('stat_engine.pairwise_t_tests', wraps=pairwise_t_tests) as analyzed, \
                patch('streamlit.download_button') as download:
            app = self.app()
            widget(app.radio, 'Test method').set_value('t-test').run(timeout=30)
            widget(app.selectbox, 't-test type').select('Paired (matched rows)')
            widget(app.multiselect, 't-test comparisons').set_value(['Treatment vs Ctrl']).run(timeout=30)
            raw_table = next(element.value for element in app.dataframe
                             if 'Comparison' in element.value.columns)
            widget(app.radio, 'Data scale').set_value('Fold change (control = 1.0)').run(timeout=30)
            self.assert_clean(app)
            self.assertEqual(widget(app.selectbox, 'Control group').value, 'Ctrl')
            data = plotted.call_args.args[0]
            np.testing.assert_allclose(data[('Ctrl', '')], [0.5, 1, 1.5])
            np.testing.assert_allclose(data[('Treatment', '')], [1, 3, 5, 4])
            np.testing.assert_allclose(analyzed.call_args.args[0]['Ctrl'], [0.5, 1, 1.5, np.nan])
            self.assertEqual(preview.call_args.args[0].axes[0].get_ylabel(), 'Fold change (control = 1.0)')
            pd.testing.assert_frame_equal(app.sidebar.dataframe[0].value,
                                          pd.read_csv(io.StringIO(content)))
            table = next(element.value for element in app.dataframe if 'Comparison' in element.value.columns)
            self.assertEqual(table['n (group 1)'].tolist(), [3])
            self.assertEqual(table['p (adjusted)'].tolist(), raw_table['p (adjusted)'].tolist())
            svg = next(call.kwargs['data'] for call in download.call_args_list[-4:]
                       if call.kwargs['mime'] == 'image/svg+xml')
            self.assertIn(b'Fold change (control = 1.0)', svg)

            widget(app.selectbox, 'Control group').select('Treatment').run(timeout=30)
            self.assert_clean(app)
            self.assertAlmostEqual(np.mean(plotted.call_args.args[0][('Treatment', '')]), 1)

            widget(app.radio, 'Data scale').set_value('Raw data').run(timeout=30)
            self.assert_clean(app)
            np.testing.assert_allclose(plotted.call_args.args[0][('Ctrl', '')], [0.01, 0.02, 0.03])
            self.assertEqual(preview.call_args.args[0].axes[0].get_ylabel(), 'Value')

    def test_grouped_categories_use_own_controls_by_name_even_when_control_hidden(self):
        content = ('Ctrl 24h,Drug 24h,Drug 48h,Ctrl 48h\n'
                   '1,2,12,2\n2,4,20,4\n3,6,28,6\n')
        with self.upload(content), patch('streamlit.pyplot'), \
                patch('plot_engine.bar_chart', wraps=bar_chart) as plotted, \
                patch('stat_engine.auto_analyze', wraps=auto_analyze) as analyzed:
            app = self.app()
            widget(app.radio, 'Data scale').set_value('Fold change (control = 1.0)').run(timeout=30)
            self.assert_clean(app)
            data = plotted.call_args.args[0]
            np.testing.assert_allclose(data[('24h', 'Ctrl')], [0.5, 1, 1.5])
            np.testing.assert_allclose(data[('48h', 'Ctrl')], [0.5, 1, 1.5])
            np.testing.assert_allclose(data[('24h', 'Drug')], [1, 2, 3])
            np.testing.assert_allclose(data[('48h', 'Drug')], [3, 5, 7])
            for call in analyzed.call_args_list[-2:]:
                np.testing.assert_allclose(call.args[0]['Ctrl'], [0.5, 1, 1.5])
            widget(app.multiselect, 'Conditions (bars within each category)').set_value(['Drug']).run(timeout=30)
            widget(app.text_input, 'Condition name: Ctrl').set_value('Vehicle').run(timeout=30)
            self.assert_clean(app)
            self.assertEqual(widget(app.selectbox, 'Control group').value, 'Ctrl')
            data = plotted.call_args.args[0]
            self.assertNotIn(('24h', 'Ctrl'), data)
            np.testing.assert_allclose(data[('24h', 'Drug')], [1, 2, 3])
            np.testing.assert_allclose(data[('48h', 'Drug')], [3, 5, 7])
            widget(app.selectbox, 'Control group').select('Drug').run(timeout=30)
            widget(app.text_input, 'Condition name: Drug').set_value('Treatment').run(timeout=30)
            self.assert_clean(app)
            self.assertEqual(widget(app.selectbox, 'Control group').value, 'Drug')
            self.assertAlmostEqual(np.mean(plotted.call_args.args[0][('24h', 'Drug')]), 1)

    def test_box_and_violin_receive_normalized_observations_with_hidden_control(self):
        with self.upload('Ctrl,Drug\n1,4\n2,6\n3,8\n'), patch('streamlit.pyplot'), \
                patch('plot_engine.box_plot', wraps=box_plot) as box, \
                patch('plot_engine.violin_plot', wraps=violin_plot) as violin:
            app = self.app()
            for chart, plotted in (('Box Plot', box), ('Violin Plot', violin)):
                with self.subTest(chart=chart):
                    widget(app.radio, 'Chart type').set_value(chart).run(timeout=30)
                    widget(app.radio, 'Data scale').set_value('Fold change (control = 1.0)').run(timeout=30)
                    widget(app.multiselect, 'Value columns').set_value(['Drug']).run(timeout=30)
                    self.assert_clean(app)
                    self.assertEqual(list(plotted.call_args.args[0]), ['Drug'])
                    np.testing.assert_allclose(plotted.call_args.args[0]['Drug'], [2, 3, 4])

    def test_invalid_controls_show_actionable_error_and_no_stale_figure(self):
        for content, message in (
                ('Ctrl,Drug\n0,4\n0,6\n0,8\n', 'non-zero mean'),
                ('Ctrl 24h,Drug 24h,Other 48h,Drug 48h\n1,4,2,8\n2,6,3,10\n3,8,4,12\n',
                 '48h: Control group "Ctrl" is missing')):
            with self.subTest(message=message), self.upload(content), patch('streamlit.pyplot') as preview:
                app = self.app()
                preview.reset_mock()
                widget(app.radio, 'Data scale').set_value('Fold change (control = 1.0)').run(timeout=30)
                self.assertFalse(list(app.exception))
                self.assertIn(message, app.error[0].value)
                self.assertFalse(list(app.code))
                preview.assert_not_called()
                widget(app.radio, 'Data scale').set_value('Raw data').run(timeout=30)
                self.assert_clean(app)
                self.assertTrue(preview.called)


if __name__ == '__main__':
    unittest.main()
