import unittest

import numpy as np
import pandas as pd

from data_parser import parse_blocks


class BlockParserTests(unittest.TestCase):
    def test_time_headers_become_categories_and_conditions_by_name(self):
        raw = pd.DataFrame({'ctrl 24h': [1, 2, 3], 'SB4 24h': [4, 5, 6],
                            'Spacer': [None] * 3,
                            'SB4 48h': [7, 8, 9], 'Ctrl 48h': [10, 11, 12]})
        original = raw.copy(deep=True)
        blocks, title = parse_blocks(raw)
        self.assertIsNone(title)
        self.assertEqual([block['label'] for block in blocks], ['24h', '48h'])
        self.assertEqual(list(blocks[0]['conditions']), ['ctrl', 'SB4'])
        self.assertEqual(blocks[1]['conditions']['ctrl'], [10, 11, 12])
        self.assertEqual(blocks[1]['conditions']['SB4'], [7, 8, 9])
        pd.testing.assert_frame_equal(raw, original)

    def test_interleaved_time_headers_without_spacers(self):
        raw = pd.DataFrame({'ctrl 24 hours': [1, 2], 'Ctrl 48h': [3, 4],
                            'SB4_24HR': [5, 6], 'SB4-48 h': [7, 8]})
        blocks, _ = parse_blocks(raw)
        self.assertEqual([block['label'] for block in blocks], ['24h', '48h'])
        self.assertEqual(blocks[0]['conditions']['SB4'], [5, 6])
        self.assertEqual(blocks[1]['conditions']['ctrl'], [3, 4])

    def test_explicit_labels_and_missing_source_rows_are_preserved(self):
        raw = pd.DataFrame({'Ctrl': [1, None, 3, 'Gene A'], 'Drug': [2, 100, 4, None],
                            'Spacer': [None] * 4,
                            'Drug.1': [7, 8, 9, 'Gene B'], 'Ctrl.1': [10, 11, 12, None]})
        blocks, _ = parse_blocks(raw)
        self.assertEqual([block['label'] for block in blocks], ['Gene A', 'Gene B'])
        self.assertEqual(blocks[0]['conditions']['Ctrl'], [1, 3])
        np.testing.assert_allclose(blocks[0]['aligned_conditions']['Ctrl'], [1, np.nan, 3, np.nan])
        self.assertEqual(blocks[1]['conditions']['Ctrl'], [10, 11, 12])

    def test_unrelated_conditions_are_not_reassigned_by_position(self):
        raw = pd.DataFrame({'Ctrl': [1, 2], 'Drug': [3, 4], 'Spacer': [None] * 2,
                            'Other': [5, 6], 'Drug.1': [7, 8]})
        blocks, _ = parse_blocks(raw)
        self.assertEqual(blocks[1]['conditions'], {'Other': [5, 6], 'Drug': [7, 8]})
        self.assertTrue(all(block['label'] is None for block in blocks))

    def test_regular_numeric_headers_are_not_timepoints(self):
        blocks, _ = parse_blocks(pd.DataFrame({'ctrl 24': [1, 2], 'SB4 48': [3, 4]}))
        self.assertEqual(len(blocks), 1)
        self.assertEqual(list(blocks[0]['conditions']), ['ctrl 24', 'SB4 48'])

    def test_single_explicit_block_keeps_sheet_title(self):
        blocks, title = parse_blocks(pd.DataFrame({'Ctrl': [1, 2, 'Gene A'], 'Drug': [3, 4, None]}))
        self.assertEqual(title, 'Gene A')
        self.assertIsNone(blocks[0]['label'])


if __name__ == '__main__':
    unittest.main()
