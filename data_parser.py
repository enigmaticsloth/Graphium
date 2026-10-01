"""Read grouped sheets while preserving condition identity and source rows."""

import re
import unicodedata

import pandas as pd


_TIME_SUFFIX = re.compile(
    r'^(?P<condition>.+?)[\s_-]+(?P<value>\d+(?:\.\d+)?)\s*'
    r'(?P<unit>hours?|hrs?|h|days?|d|minutes?|mins?|min)\s*$', re.IGNORECASE)


def _canonical(name):
    name = str(name).strip()
    base, dot, suffix = name.rpartition('.')
    return base if dot and suffix.isdigit() else name


def _time_header(name):
    match = _TIME_SUFFIX.fullmatch(_canonical(name))
    if match is None:
        return None
    unit = match['unit'].lower()
    unit = 'h' if unit.startswith('h') else 'd' if unit.startswith('d') else 'min'
    return match['condition'].strip(), match['value'] + unit


def _identity(name):
    return unicodedata.normalize('NFKC', name).casefold()


def parse_blocks(df_raw):
    """Return (blocks, sheet_title) from blank-column blocks or time headers.

    Headers such as ``ctrl 24h`` / ``SB4 24h`` / ``Ctrl 48h`` / ``SB4 48h``
    become timepoint categories and condition names. Without a consistent time
    pattern, explicit labels in the sheet or Block N remain the defaults.
    Condition matching uses names, never column position. aligned_conditions
    retain missing rows so paired statistics use the original sample pairing.
    """
    column_groups, current = [], []
    for column in df_raw.columns:
        if df_raw[column].isna().all():
            if current:
                column_groups.append(current)
                current = []
        else:
            current.append(column)
    if current:
        column_groups.append(current)

    time_headers = {column: _time_header(column)
                    for columns in column_groups for column in columns}
    infer_times = bool(time_headers) and all(time_headers.values())
    if infer_times:
        times = {value[1] for value in time_headers.values()}
        infer_times = len(times) > 1
    if infer_times and len(column_groups) == 1:
        # Also recognize timepoint headers without blank separator columns.
        by_time = {}
        for column in column_groups[0]:
            by_time.setdefault(time_headers[column][1], []).append(column)
        column_groups = list(by_time.values())
    if infer_times:
        infer_times = all(
            len({time_headers[column][1] for column in columns}) == 1
            and len({_identity(time_headers[column][0]) for column in columns}) == len(columns)
            for columns in column_groups)

    blocks, condition_names = [], {}
    for columns in column_groups:
        label = None
        conditions, aligned_conditions = {}, {}
        for column in columns:
            raw_name = time_headers[column][0] if infer_times else _canonical(column)
            name = condition_names.setdefault(_identity(raw_name), raw_name)
            numeric = pd.to_numeric(df_raw[column], errors='coerce').astype(float)
            conditions[name] = numeric.dropna().tolist()
            aligned_conditions[name] = numeric.tolist()
            if label is None:
                for value in df_raw[column][numeric.isna()].dropna():
                    if str(value).strip():
                        label = str(value).strip()
                        break
        if label is None and infer_times:
            label = time_headers[columns[0]][1]
        blocks.append({'label': label, 'conditions': conditions,
                       'aligned_conditions': aligned_conditions})

    sheet_title = None
    if len(blocks) == 1 and blocks[0]['label']:
        sheet_title = blocks[0]['label']
        blocks[0]['label'] = None
    return blocks, sheet_title
