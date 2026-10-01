"""Appearance presets and the session-scoped manual annotation editor."""

import hashlib

import streamlit as st


# Interface copy is English across all appearance presets.
THEMES = {
    'Carbon': dict(background='#080808', sidebar='#101010', panel='#171717',
                   border='#303030', text='#f3f3f3', muted='#a6a6a6', accent='#e0e0e0',
                   description='Black workspace · Grayscale controls keep the focus on your figures'),
    'Graphite': dict(background='#202526', sidebar='#181d1e', panel='#2b3233',
                     border='#455050', text='#edf2f0', muted='#b1bfba', accent='#a8d5c1',
                     description='Graphite workspace · Soft gray surfaces with pale green accents'),
    'Paper': dict(background='#f3f2ee', sidebar='#eae9e3', panel='#ffffff',
                  border='#d3d3ca', text='#222623', muted='#61675e', accent='#36584a',
                  description='Light workspace · Warm white surfaces inspired by print layouts'),
}


def apply_theme():
    with st.sidebar:
        st.markdown('### Appearance')
        name = st.selectbox('Interface template', list(THEMES), key='interface_theme')
        st.caption(THEMES[name]['description'])
        st.divider()
    theme = THEMES[name]
    variables = ';'.join('--g-' + key + ':' + value for key, value in theme.items()
                         if key != 'description')
    scheme = 'light' if name == 'Paper' else 'dark'
    st.markdown('<style>:root {' + variables + '; color-scheme:' + scheme + ';}' + """
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background: var(--g-background); color: var(--g-text);
        }
        [data-testid="stDecoration"] { display: none; }
        [data-testid="stSidebar"] {
            background: var(--g-sidebar); border-right: 1px solid var(--g-border);
        }
        .block-container { padding-top: 3.5rem; padding-bottom: 3rem; }
        h1, h2, h3, h4, p, label, summary, .stMarkdown,
        [data-testid="stWidgetLabel"], [data-testid="stMetricValue"] {
            color: var(--g-text) !important;
        }
        h1 { font-size: 2rem !important; font-weight: 650 !important; letter-spacing: -.06rem; }
        h2, h3 { font-size: 1.1rem !important; font-weight: 600 !important; }
        [data-testid="stCaptionContainer"] p { color: var(--g-muted) !important; }
        [data-testid="stExpander"], [data-testid="stMetric"] {
            background: var(--g-panel); border: 1px solid var(--g-border);
            border-radius: 8px;
        }
        [data-testid="stMetric"] { padding: 12px; }
        [data-testid="stExpander"] summary { font-size: .9rem; }
        [data-baseweb="select"] > div, [data-baseweb="input"],
        [data-baseweb="base-input"], [data-baseweb="textarea"],
        input, textarea, [data-testid="stFileUploaderDropzone"] {
            background: var(--g-panel) !important; color: var(--g-text) !important;
            border-color: var(--g-border) !important;
        }
        [data-baseweb="select"] svg, [data-testid="stSidebar"] svg {
            fill: var(--g-muted);
        }
        [data-testid="stFileUploaderDropzone"] small,
        [data-testid="stFileUploaderDropzone"] span {
            color: var(--g-muted) !important;
        }
        [data-baseweb="tag"] {
            background: var(--g-background) !important; border: 1px solid var(--g-border);
            color: var(--g-text) !important; border-radius: 4px !important;
        }
        [data-baseweb="tag"] span { color: var(--g-text) !important; }
        [data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"], [role="option"] {
            background: var(--g-panel) !important; color: var(--g-text) !important;
        }
        [role="option"][aria-selected="true"], [role="option"]:hover {
            background: var(--g-sidebar) !important;
        }
        [data-testid="stButton"] button, [data-testid="stDownloadButton"] button,
        [data-testid="stFileUploader"] button, [data-testid="stNumberInput"] button {
            background: var(--g-panel); color: var(--g-text); border: 1px solid var(--g-border);
            border-radius: 6px; box-shadow: none;
        }
        button:hover, button:focus-visible { border-color: var(--g-accent) !important; }
        .stRadio [role="radiogroup"] { gap: .3rem 1.1rem; }
        .stRadio label { padding: .25rem 0; background: transparent; border: 0; }
        [data-baseweb="radio"] > div:first-child,
        [data-baseweb="checkbox"] > span:first-child {
            background-color: var(--g-panel) !important; border-color: var(--g-muted) !important;
        }
        [data-baseweb="radio"]:has(input:checked) > div:first-child,
        [data-baseweb="checkbox"]:has(input:checked) > span:first-child {
            background-color: var(--g-accent) !important; border-color: var(--g-accent) !important;
        }
        [data-baseweb="radio"]:not(:has(input:checked)) > div:first-child {
            box-shadow: inset 0 0 0 1px var(--g-muted);
        }
        [data-baseweb="radio"]:not(:has(input:checked)) > div:first-child > div {
            background-color: var(--g-panel) !important;
        }
        [data-baseweb="radio"]:has(input:checked) > div:first-child > div {
            background-color: var(--g-background);
        }
        [data-baseweb="checkbox"]:has(input:checked) svg { fill: var(--g-background); }
        [data-baseweb="slider"] [role="slider"] { background-color: var(--g-accent); }
        [data-testid="stThumbValue"] { color: var(--g-text); }
        [data-testid="stImage"] { background: white; border: 1px solid var(--g-border); border-radius: 4px; }
        .stat-box {
            background: var(--g-panel); border: 1px solid var(--g-border);
            border-left: 3px solid var(--g-accent); border-radius: 6px;
            padding: 14px; margin: 8px 0 16px; color: var(--g-text); font-size: .9rem;
        }
        .stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid var(--g-border); }
        .stTabs [aria-selected="true"] { color: var(--g-accent) !important; }
        hr { border-color: var(--g-border); }
        a { color: var(--g-accent); }
        input:focus, textarea:focus { outline-color: var(--g-accent); }
        ::selection { background: var(--g-accent); color: var(--g-background); }
        @media (max-width: 800px) { .block-container { padding-left: 1rem; padding-right: 1rem; } }
    </style>""", unsafe_allow_html=True)


def axis_range_editor(chart_type):
    """Return optional numeric bounds; empty inputs keep automatic limits."""
    with st.expander('Axis range', expanded=True):
        st.caption('Leave a field empty for automatic scaling.')
        if chart_type in ('Bar Chart', 'Box Plot', 'Violin Plot'):
            st.caption('X limits use plotted category positions; Y limits use data values.')
        elif chart_type == 'Heatmap':
            st.caption('Limits use column and row positions, starting at 0.')
        bounds = {}
        for axis in ('X', 'Y'):
            left, right = st.columns(2)
            with left:
                lower = st.number_input(
                    f'{axis}-axis minimum', value=None, step=1.0, format='%g',
                    placeholder='Auto', key=f'axis_{chart_type}_{axis}_min')
            with right:
                upper = st.number_input(
                    f'{axis}-axis maximum', value=None, step=1.0, format='%g',
                    placeholder='Auto', key=f'axis_{chart_type}_{axis}_max')
            bounds[axis.lower() + 'lim'] = (lower, upper)
    return bounds


def figure_size_editor(chart_type):
    defaults = {
        'Bar Chart': (8.0, 5.0), 'Box Plot': (8.0, 5.0),
        'Violin Plot': (8.0, 5.0), 'Line Chart': (6.0, 4.5),
        'Scatter Plot': (6.0, 5.0), 'Pie Chart': (6.0, 6.0),
        'Heatmap': (8.0, 6.0),
    }
    with st.expander('Figure size', expanded=True):
        left, right = st.columns(2)
        with left:
            width = st.number_input(
                'Figure width (in)', min_value=1.0, value=defaults[chart_type][0],
                step=0.1, key=f'figure_{chart_type}_width')
        with right:
            height = st.number_input(
                'Figure height (in)', min_value=1.0, value=defaults[chart_type][1],
                step=0.1, key=f'figure_{chart_type}_height')
        st.caption(f'PNG / TIFF at 300 DPI: {round(width * 300)} × {round(height * 300)} px. '
                   'The preview scales to fit your screen.')
    return width, height


def grouped_name_editor(scope, categories, conditions):
    """Store display names independently of the identifiers used for data."""
    names = st.session_state.setdefault('grouped_display_names', {}).setdefault(
        scope, {'categories': {}, 'conditions': {}})
    st.markdown('**Edit display names**')
    st.caption('Set the category names on the x-axis and the condition names in the legend.')
    for kind, items, label in (('categories', categories, 'Category name'),
                               ('conditions', conditions, 'Condition name')):
        for item in items:
            key = hashlib.sha256(repr((scope, kind, item)).encode()).hexdigest()[:20]
            value = st.text_input(f'{label}: {item}',
                                  value=names[kind].get(item, str(item)), key='name_' + key)
            names[kind][item] = value.strip() or str(item)
    return names['categories'], names['conditions']


def remembered_multiselect(label, options, scope, name, default=None, format_func=str, **kwargs):
    """Keep logical selections when their display names or source change."""
    selections = st.session_state.setdefault('named_selections', {}).setdefault(scope, {})
    current = [value for value in selections.get(name, default or []) if value in options]
    selected = st.multiselect(label, options, default=current, format_func=format_func,
                             key=f'{scope}_{name}', **kwargs)
    selections[name] = selected
    return selected


def _add_label(scope, target):
    state = st.session_state['manual_labels'][scope]
    label_id = state['next_id']
    state['next_id'] += 1
    state['labels'][label_id] = dict(target=target, text='#', enabled=True,
                                   x_offset=0, y_offset=0, fontsize=14)
    st.session_state[scope + '_active'] = label_id


def _delete_label(scope, label_id):
    labels = st.session_state['manual_labels'][scope]['labels']
    del labels[label_id]
    if labels:
        st.session_state[scope + '_active'] = next(iter(labels))
    else:
        st.session_state.pop(scope + '_active', None)


def manual_label_editor(scope, targets):
    """targets maps stable (category, group) tuples to readable names."""
    scopes = st.session_state.setdefault('manual_labels', {})
    state = scopes.setdefault(scope, {'next_id': 1, 'labels': {}})
    labels = state['labels']
    with st.expander('Manual labels (#, †, text)', expanded=False):
        st.caption('Add your own symbol above a bar or group. Labels are kept for this file and sheet during this session.')
        if not targets:
            st.info('Select data columns to add a label.')
            return []
        st.button('Add label', key=scope + '_add', on_click=_add_label,
                  args=(scope, next(iter(targets))))
        if labels:
            label_id = st.selectbox(
                'Edit label', list(labels), key=scope + '_active',
                format_func=lambda i: f'Label {i}')
            row = labels[label_id]
            prefix = f'{scope}_{label_id}_'
            options = list(targets)
            if row['target'] not in targets:
                options.append(row['target'])
            row['target'] = st.selectbox('Place above', options,
                                         index=options.index(row['target']), key=prefix + 'target',
                                         format_func=lambda t: targets.get(t, 'Hidden group (not plotted)'))
            row['text'] = st.text_input('Label text', value=row['text'], key=prefix + 'text',
                                       help='Examples: #, ##, †, a, or custom text.')
            row['enabled'] = st.checkbox('Show this label', value=row['enabled'], key=prefix + 'enabled')
            row['fontsize'] = st.slider('Label size (pt)', 8, 32, row['fontsize'], key=prefix + 'size')
            row['y_offset'] = st.slider('Extra height (pt)', 0, 120, row['y_offset'], key=prefix + 'height')
            row['x_offset'] = st.slider('Horizontal offset (pt)', -60, 60, row['x_offset'], key=prefix + 'offset')
            st.button('Delete label', key=prefix + 'delete', on_click=_delete_label, args=(scope, label_id))
    return [dict(row) for row in labels.values()
            if row['enabled'] and row['text'].strip() and row['target'] in targets]
