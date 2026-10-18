"""Read grouped sheets while preserving condition identity and source rows."""

import re
import unicodedata
from copy import deepcopy

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


def prepare_sheet(df_raw):
    """Recognize sparse category/parent rows above repeated condition headers.

    Accept a sheet read with pandas' default first-row header. Ordinary tables
    pass through unchanged. Hierarchical sheets become numeric columns with
    explicit block metadata, so repeated Distal/Proximal labels stay distinct.
    """
    if 'graphium_blocks' in df_raw.attrs:
        return df_raw
    headers = [None if str(column).startswith('Unnamed:') else _canonical(column)
               for column in df_raw.columns]
    rows = pd.DataFrame([headers] + df_raw.values.tolist())

    def text(value):
        return str(value).strip() if isinstance(value, str) and value.strip() else None

    for header_index in range(1, min(6, len(rows) - 1)):
        values = rows.iloc[header_index + 1:].apply(pd.to_numeric, errors='coerce')
        active = [column for column in rows.columns if values[column].notna().any()]
        conditions = [text(rows.at[header_index, column]) for column in active]
        if not conditions or not all(conditions):
            continue
        identities = [_identity(name) for name in conditions]
        if not 1 < len(set(identities)) < len(identities):
            continue
        # A sparse category row must precede the dense, repeated condition row.
        categories = [text(value) for value in rows.iloc[header_index - 1]]
        if not categories[active[0]] or sum(value is not None for value in categories) < 2:
            continue
        if len({value for value in categories if value is not None}) >= len(active):
            continue
        parents = ([text(value) for value in rows.iloc[header_index - 2]]
                   if header_index >= 2 else [None] * len(rows.columns))

        blocks, columns, condition_names, used_labels = [], {}, {}, set()
        parent, category, current = None, None, None
        valid = True
        for column in active:
            if parents[column]:
                if parents[column] != parent:
                    category = None
                parent = parents[column]
            if categories[column]:
                category = categories[column]
            if category is None:
                valid = False
                break
            path = (parent, category)
            if current is None or path != current:
                label = ' / '.join(part for part in path if part)
                original_label, suffix = label, 2
                while label in used_labels:
                    label = f'{original_label} ({suffix})'
                    suffix += 1
                used_labels.add(label)
                blocks.append(dict(label=label, display_label=category, parent_label=parent,
                                   conditions={}, aligned_conditions={}))
                current = path
            name = text(rows.at[header_index, column])
            name = condition_names.setdefault(_identity(name), name)
            block = blocks[-1]
            if name in block['conditions']:
                valid = False
                break
            numeric = values[column].astype(float)
            block['conditions'][name] = numeric.dropna().tolist()
            block['aligned_conditions'][name] = numeric.tolist()
            columns[f'{block["label"]} / {name}'] = numeric.to_numpy()
        if valid and len(blocks) > 1:
            prepared = pd.DataFrame(columns)
            prepared.attrs['graphium_blocks'] = blocks
            return prepared
    return df_raw


def parse_blocks(df_raw):
    """Return (blocks, sheet_title) from blank-column blocks or time headers.

    Headers such as ``ctrl 24h`` / ``SB4 24h`` / ``Ctrl 48h`` / ``SB4 48h``
    become timepoint categories and condition names. Without a consistent time
    pattern, explicit labels in the sheet or Block N remain the defaults.
    Condition matching uses names, never column position. aligned_conditions
    retain missing rows so paired statistics use the original sample pairing.
    """
    if 'graphium_blocks' in df_raw.attrs:
        return deepcopy(df_raw.attrs['graphium_blocks']), None
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
