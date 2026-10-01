"""
Graphium — Web Application (Streamlit)
Publication-quality statistical figure engine.
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
import sys, os
import hashlib

sys.path.insert(0, os.path.dirname(__file__))
from ui_components import (apply_theme, manual_label_editor, axis_range_editor, figure_size_editor,
                           grouped_name_editor, remembered_multiselect)
from data_parser import parse_blocks
from stat_engine import auto_analyze, pairwise_t_tests, p_to_stars, SIG_THRESHOLDS
from plot_engine import (
    line_chart, bar_chart, pie_chart, box_plot,
    violin_plot, scatter_plot, heatmap,
    fig_to_buf, PALETTES, get_palette, calc_stats, AxisRangeError
)


# ── Page Config ──────────────────────────────────────────────
st.set_page_config(
    page_title='Graphium',
    page_icon='✒️',
    layout='wide',
    initial_sidebar_state='expanded'
)

# ── Appearance and header ────────────────────────────────────
apply_theme()
st.title('Graphium')
st.caption('Publication figures · Statistical analysis · Your data, clearly.')

# ── Sidebar: Data Import ─────────────────────────────────────
with st.sidebar:
    st.header('Data')
    uploaded = st.file_uploader('Upload Excel or CSV', type=['xlsx', 'xls', 'csv', 'tsv'])

    use_demo = st.checkbox('Use example data', value=False, disabled=uploaded is not None)

    if uploaded:
        if uploaded.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded)
            sheet_names = ['Sheet1']
            sheets = {'Sheet1': df_raw}
        elif uploaded.name.endswith('.tsv'):
            df_raw = pd.read_csv(uploaded, sep='\t')
            sheet_names = ['Sheet1']
            sheets = {'Sheet1': df_raw}
        else:
            xls = pd.ExcelFile(uploaded)
            sheet_names = xls.sheet_names
            sheets = {s: xls.parse(s) for s in sheet_names}

        selected_sheet = st.selectbox('Sheet', sheet_names)
        df_raw = sheets[selected_sheet].copy()

        # Clean: drop fully empty rows/cols, coerce numeric columns
        df = df_raw.dropna(how='all').dropna(axis=1, how='all')
        for col in df.columns:
            converted = pd.to_numeric(df[col], errors='coerce')
            # If >50% of non-null values are numeric, treat as numeric column
            if converted.notna().sum() > df[col].notna().sum() * 0.5:
                df[col] = converted

        st.dataframe(df.head(10), use_container_width=True, height=200)
        st.caption(f'{df.shape[0]} rows × {df.shape[1]} cols')
    elif use_demo:
        # Synthetic observations for comparing templates without an upload.
        demo = {}
        values = [
            [[9, 10, 8, 10, 9, 10], [9, 9, 9, 8, 10, 9], [9, 10, 9, 10, 9, 10]],
            [[14, 17, 19, 19, 22, 27], [13, 14, 14, 15, 16, 16], [14, 16, 17, 17, 19, 17]],
            [[28, 41, 45, 54, 55, 58], [24, 28, 28, 31, 33, 34], [39, 51, 51, 55, 57, 51]],
        ]
        for i, (label, block) in enumerate(zip(['0h', '24h', '48h'], values)):
            if i:
                demo[f'Spacer {i}'] = [None] * 7
            for j, (condition, observations) in enumerate(zip(['Ctrl', 'TGFβ1', 'TGFβ1+DAPT'], block)):
                name = condition if i == 0 else f'{condition}.{i}'
                demo[name] = observations + [label if j == 0 else None]
        df_raw = pd.DataFrame(demo)
        df = df_raw.dropna(how='all').dropna(axis=1, how='all').apply(pd.to_numeric, errors='coerce').dropna(how='all')
        selected_sheet = 'Example'
        st.caption('Synthetic example · 3 timepoints, 3 conditions')
        st.dataframe(df.head(6), use_container_width=True, height=200)
    else:
        df = None
        df_raw = None
        st.info('Upload a file to get started.')

# ── Main Area ────────────────────────────────────────────────
if df is not None:
    # ── Chart type selection ─────────────────────────────
    chart_type = st.radio(
        'Chart type',
        ['Bar Chart', 'Line Chart', 'Box Plot', 'Violin Plot',
         'Scatter Plot', 'Pie Chart', 'Heatmap'],
        horizontal=True, label_visibility='collapsed'
    )

    col_left, col_right = st.columns([2.5, 1], gap="large")

    with col_right:
        st.subheader('Figure settings')

        # ── Column assignment ────────────────────────────
        all_cols = df.columns.tolist()
        axis_options = axis_range_editor(chart_type) if chart_type != 'Pie Chart' else {}
        fig_w, fig_h = figure_size_editor(chart_type)

        if chart_type in ['Bar Chart', 'Box Plot', 'Violin Plot']:
            source_id = hashlib.sha256(uploaded.getvalue()).hexdigest() if uploaded else 'example'
            name_scope = hashlib.sha256(repr((source_id, selected_sheet)).encode()).hexdigest()[:16]
            category_names, condition_names = {}, {}
            with st.expander('Data & layout', expanded=True):
                # Detect block structure from raw sheet (before dropna)
                blocks, sheet_title = parse_blocks(df_raw)
                block_labels = [b['label'] or f'Block {i+1}' for i, b in enumerate(blocks)]
                multi_block = len(blocks) > 1 and chart_type == 'Bar Chart'

                use_grouped = False
                if multi_block:
                    st.markdown(f'**{len(blocks)} data blocks detected**')
                    use_grouped = st.checkbox('Grouped bars', value=True)

                if use_grouped:
                    # Union of canonical condition names, preserving first-seen order
                    all_conditions = []
                    for b in blocks:
                        for c in b['conditions']:
                            if c not in all_conditions:
                                all_conditions.append(c)

                    category_names, condition_names = grouped_name_editor(
                        name_scope, block_labels, all_conditions)
                    selected_genes = remembered_multiselect(
                        'Categories (x-axis)', block_labels, name_scope, 'categories',
                        default=block_labels, format_func=lambda name: category_names.get(name, name))
                    selected_conditions = remembered_multiselect(
                        'Conditions (bars within each category)',
                        all_conditions, name_scope, 'conditions',
                        default=all_conditions, format_func=lambda name: condition_names.get(name, name))
                    value_cols = []  # not used in grouped mode
                else:
                    st.markdown('**Data columns** (select value columns)')
                    value_cols = st.multiselect('Value columns', all_cols,
                                                 default=all_cols[:min(3, len(all_cols))])
                    selected_genes = None
                    selected_conditions = None

                # Bar layout (flat bar chart only — grouped mode always has its own layout)
                if chart_type == 'Bar Chart' and not use_grouped:
                    bar_layout = st.radio(
                        'Bar layout',
                        ['Separate bars (label under each)', 'Clustered (legend)'],
                        horizontal=False,
                    )
                else:
                    bar_layout = 'Separate bars (label under each)'

            pair_source = selected_conditions if use_grouped else value_cols
            pair_options = {f'{first} vs {second}': (first, second)
                            for i, first in enumerate(pair_source)
                            for second in pair_source[i + 1:]}
            scope = hashlib.sha256(repr((source_id, selected_sheet, chart_type, use_grouped)).encode()).hexdigest()[:16]
            def pair_display_name(pair):
                first, second = pair_options[pair]
                return f'{condition_names.get(first, first)} vs {condition_names.get(second, second)}'

            with st.expander('Statistics', expanded=True):
                run_stats = st.checkbox('Auto-run statistics', value=True)
                stats_method = st.radio('Test method', ['Automatic', 't-test'], horizontal=True)
                ttest_type, ttest_pairs = 'welch', []
                if stats_method == 't-test':
                    ttest_types = {'Welch (unpaired)': 'welch',
                                   'Student (equal variance)': 'student',
                                   'Paired (matched rows)': 'paired'}
                    ttest_type = ttest_types[st.selectbox('t-test type', list(ttest_types))]
                    chosen_pairs = remembered_multiselect(
                        't-test comparisons', list(pair_options), scope, 'ttest_pairs',
                        format_func=pair_display_name)
                    ttest_pairs = [pair_options[label] for label in chosen_pairs]
                    if not ttest_pairs:
                        st.info('Choose the group pairs to compare.')
                    if ttest_type == 'paired':
                        st.caption('Use matching subjects or samples in the same source row. '
                                   'Rows missing either value are excluded as a pair.')
                    if use_grouped:
                        st.caption('Selected conditions are compared separately within each category.')
                correction = st.selectbox('Multiple comparison correction',
                                           ['fdr', 'bonferroni', 'none'], index=0)

            with st.expander('Statistical stars', expanded=True):
                hide_all_stars = st.checkbox('Hide all statistical stars', value=False,
                    help='Hide automatic stars, ns labels, and comparison brackets.')
                st.caption('Hiding stars changes the figure only. Statistical results remain available below.')
                hidden_pairs = remembered_multiselect(
                    'Hide stars for these comparisons', list(pair_options), scope, 'hidden_pairs',
                    format_func=pair_display_name,
                    disabled=hide_all_stars,
                    help='Select comparisons to hide. Remove a selection to show it again.')
                anno_style = st.radio('Annotation style', ['above_bar', 'bracket'], horizontal=True)
                show_ns = st.checkbox('Show non-significant (ns) on chart', value=False)

            with st.expander('Appearance'):
                # ── Style ────────────────────────────────────
                palette = st.selectbox('Color palette', list(PALETTES.keys()), index=0)
                custom_colors_str = st.text_input('Custom colors (hex, comma-separated)', '')
                custom_colors = [c.strip() for c in custom_colors_str.split(',') if c.strip()] if custom_colors_str else None

                show_points = st.checkbox('Show individual data points', value=True)
                if chart_type == 'Bar Chart':
                    error_type = st.radio('Error bars', ['SEM', 'SD'], horizontal=True)
                bar_gap = st.slider('Bar gap', 0.0, 0.5, 0.0, 0.05) if chart_type == 'Bar Chart' else 0.0

            with st.expander('Axis labels & legend'):
                xtick_fontsize = st.slider('X-axis label size', 6, 24,
                                            11 if chart_type == 'Bar Chart' else 12, 1)
                xtick_bold = st.checkbox('Bold x-axis labels', value=False)
                ytick_fontsize = st.slider('Y-axis number size', 6, 24, 11, 1)
                ytick_bold = st.checkbox('Bold y-axis numbers', value=False)
                legend_pos = st.radio('Legend position', ['Auto', 'Inside', 'Outside'],
                                       horizontal=True, index=0)
                legend_loc = legend_pos.lower()

                ylabel = st.text_input('Y-axis label', 'Value')

            with st.expander('Annotation spacing'):
                annotation_fontsize = st.slider('Automatic label size (pt)', 8, 28, 13)
                annotation_gap = st.slider('Gap above data (pt)', 2, 30, 8)
                symbol_spacing = st.slider('Symbol spacing', 0, 3, 1,
                                           help='Adds space between repeated symbols, such as ** or ###.')

            targets = ({(gene, cond): f'{category_names.get(gene, gene)} / {condition_names.get(cond, cond)}'
                        for gene in selected_genes for cond in selected_conditions}
                       if use_grouped else {(None, g): str(g) for g in value_cols})
            manual_labels = manual_label_editor(scope, targets)
            custom_annotations = []
            for label in manual_labels:
                cat, group = label.pop('target')
                if chart_type == 'Bar Chart':
                    if use_grouped:
                        label.update(cat=cat, group_idx=selected_conditions.index(group))
                    elif bar_layout.startswith('Separate'):
                        label.update(cat=group, group_idx=0)
                    else:
                        label.update(cat='', group_idx=value_cols.index(group))
                else:
                    label['group'] = group
                custom_annotations.append(label)
            annotation_options = dict(custom_annotations=custom_annotations,
                                      annotation_fontsize=annotation_fontsize,
                                      annotation_gap=annotation_gap,
                                      symbol_spacing=symbol_spacing)
            if chart_type == 'Bar Chart':
                annotation_options['error_type'] = error_type

        elif chart_type == 'Line Chart':
            st.markdown('**Column assignment**')
            x_col_opts = ['(use row index)'] + all_cols
            x_col = st.selectbox('X (timepoints)', x_col_opts)
            value_cols = st.multiselect('Y columns (groups)', all_cols,
                                         default=all_cols[:min(2, len(all_cols))])
            palette = st.selectbox('Color palette', list(PALETTES.keys()), index=0)
            custom_colors_str = st.text_input('Custom colors (hex, comma-separated)', '')
            custom_colors = [c.strip() for c in custom_colors_str.split(',') if c.strip()] if custom_colors_str else None
            show_points = st.checkbox('Show individual data points', value=True)
            xlabel = st.text_input('X-axis label', 'Time')
            ylabel = st.text_input('Y-axis label', 'Value')
            run_stats = False

        elif chart_type == 'Scatter Plot':
            x_col = st.selectbox('X column', all_cols, index=0)
            y_col = st.selectbox('Y column', all_cols, index=min(1, len(all_cols)-1))
            group_col = st.selectbox('Group column (optional)', ['None'] + all_cols)
            palette = st.selectbox('Color palette', list(PALETTES.keys()), index=5)
            show_reg = st.checkbox('Show regression line', value=True)
            show_corr = st.checkbox('Show correlation', value=True)
            xlabel = st.text_input('X-axis label', x_col)
            ylabel = st.text_input('Y-axis label', y_col)
            run_stats = False

        elif chart_type == 'Pie Chart':
            label_col = st.selectbox('Labels column', all_cols, index=0)
            value_col = st.selectbox('Values column', all_cols, index=min(1, len(all_cols)-1))
            palette = st.selectbox('Color palette', list(PALETTES.keys()), index=4)
            donut = st.checkbox('Donut style', value=False)
            run_stats = False

        elif chart_type == 'Heatmap':
            st.markdown('**Options**')
            z_score = st.checkbox('Z-score normalization (row-wise)', value=False)
            cmap = st.selectbox('Color map', ['RdBu_r', 'viridis', 'coolwarm', 'YlOrRd', 'Blues'])
            annotate = st.checkbox('Show values', value=True)
            cluster_rows = st.checkbox('Cluster rows', value=False)
            cluster_cols = st.checkbox('Cluster columns', value=False)
            run_stats = False

    # ── Generate Chart ───────────────────────────────────
    with col_left:
        st.subheader('Figure preview')

        try:
            fig = None
            stat_result = None

            # ── BAR / BOX / VIOLIN ──────────────────────
            def _analyze_groups(groups_data):
                if stats_method == 't-test':
                    return (pairwise_t_tests(groups_data, ttest_pairs, ttest_type, correction)
                            if ttest_pairs else None)
                return auto_analyze(groups_data, correction=correction)

            # Helper: check if a pairwise result should be shown
            def _pw_selected(pw):
                if hide_all_stars:
                    return False
                if pw.stars == 'ns' and not show_ns:
                    return False
                pair_fwd = f'{pw.group1} vs {pw.group2}'
                pair_rev = f'{pw.group2} vs {pw.group1}'
                return pair_fwd not in hidden_pairs and pair_rev not in hidden_pairs

            # ── GROUPED BAR (multi-gene) ─────────────────
            if chart_type == 'Bar Chart' and use_grouped and selected_genes and selected_conditions:
                categories = list(selected_genes)
                groups = list(selected_conditions)
                n_groups = len(groups)

                label_to_block = {(b['label'] or f'Block {i+1}'): b
                                  for i, b in enumerate(blocks)}

                bar_data = {}
                for gene in categories:
                    block = label_to_block[gene]
                    for cond in groups:
                        bar_data[(gene, cond)] = list(block['conditions'].get(cond, []))

                # Per-gene pairwise stats
                sig_ann = []
                per_gene_results = {}
                if run_stats and n_groups >= 2:
                    for gene in categories:
                        block = label_to_block[gene]
                        source = block['aligned_conditions'] if stats_method == 't-test' else block['conditions']
                        gdata = {c: list(source.get(c, []))
                                 for c in groups}
                        if stats_method == 'Automatic':
                            gdata = {c: v for c, v in gdata.items() if len(v) >= 2}
                        if len(gdata) < 2:
                            continue
                        try:
                            res = _analyze_groups(gdata)
                            if res is None:
                                continue
                            per_gene_results[gene] = res
                            for pw in res.pairwise:
                                if not _pw_selected(pw):
                                    continue
                                if pw.group1 not in groups or pw.group2 not in groups:
                                    continue
                                if anno_style == 'above_bar':
                                    gi = groups.index(pw.group2)
                                    sig_ann.append({'cat': gene, 'group_idx': gi, 'text': pw.stars})
                                else:
                                    g1i = groups.index(pw.group1)
                                    g2i = groups.index(pw.group2)
                                    sig_ann.append({'cat': gene, 'g1': g1i, 'g2': g2i, 'text': pw.stars})
                        except Exception as stat_err:
                            st.warning(f'⚠️ Stats error for {gene}: {stat_err}')

                colors = custom_colors if custom_colors and len(custom_colors) >= n_groups else None

                fig = bar_chart(
                    bar_data, categories, groups, ylabel=ylabel,
                    colors=colors, palette=palette,
                    bar_width=0.8, group_gap=bar_gap,
                    show_points=show_points,
                    sig_annotations=sig_ann if sig_ann else None,
                    italic_labels=True,
                    category_labels=category_names, group_labels=condition_names,
                    xtick_fontsize=xtick_fontsize, xtick_bold=xtick_bold,
                    ytick_fontsize=ytick_fontsize, ytick_bold=ytick_bold,
                    legend_loc=legend_loc,
                    figsize=(fig_w, fig_h), **annotation_options, **axis_options,
                )
                # Keep stat_result reference so the side panel can show per-gene tables
                stat_result = per_gene_results if per_gene_results else None

            # ── FLAT BAR / BOX / VIOLIN ─────────────────
            elif chart_type in ['Bar Chart', 'Box Plot', 'Violin Plot'] and value_cols:
                groups = value_cols
                n_groups = len(groups)

                # Build data dict — force numeric, drop any remaining strings
                data = {}
                groups_for_stats = {}
                for g in groups:
                    numeric_series = pd.to_numeric(df[g], errors='coerce')
                    vals = numeric_series.dropna().astype(float).tolist()
                    data[g] = vals
                    groups_for_stats[g] = numeric_series.astype(float).tolist() if stats_method == 't-test' else vals

                colors = custom_colors if custom_colors and len(custom_colors) >= n_groups else None

                # Auto-stats
                if run_stats and n_groups >= 2:
                    try:
                        stat_result = _analyze_groups(groups_for_stats)
                    except Exception as stat_err:
                        st.warning(f'⚠️ Stats error: {stat_err}')
                        stat_result = None

                if chart_type == 'Bar Chart':
                    separate = bar_layout.startswith('Separate')

                    if separate:
                        # Each column = its own category; single unnamed group
                        bar_data = {(col, ''): data[col] for col in groups}
                        categories = list(groups)
                        plot_groups = ['']
                        sig_ann = []
                        if stat_result and stat_result.pairwise:
                            for pw in stat_result.pairwise:
                                if not _pw_selected(pw):
                                    continue
                                if anno_style == 'above_bar':
                                    sig_ann.append({'cat': pw.group2, 'group_idx': 0, 'text': pw.stars})
                                else:
                                    sig_ann.append({'cat1': pw.group1, 'cat2': pw.group2, 'text': pw.stars})

                        fig = bar_chart(
                            bar_data, categories, plot_groups, ylabel=ylabel,
                            colors=colors, palette=palette,
                            bar_width=0.8, group_gap=bar_gap,
                            show_points=show_points,
                            sig_annotations=sig_ann if sig_ann else None,
                            italic_labels=False,
                            xtick_fontsize=xtick_fontsize, xtick_bold=xtick_bold,
                            ytick_fontsize=ytick_fontsize, ytick_bold=ytick_bold,
                            legend_loc=legend_loc,
                            show_legend=False,
                            figsize=(fig_w, fig_h), **annotation_options, **axis_options,
                        )
                    else:
                        # Clustered: all bars within single empty category, legend shows group names
                        bar_data = {('', g): data[g] for g in groups}
                        sig_ann = []
                        if stat_result and stat_result.pairwise:
                            for pw in stat_result.pairwise:
                                if _pw_selected(pw):
                                    if anno_style == 'above_bar':
                                        gi = groups.index(pw.group2)
                                        sig_ann.append({'cat': '', 'group_idx': gi, 'text': pw.stars})
                                    else:
                                        g1i = groups.index(pw.group1)
                                        g2i = groups.index(pw.group2)
                                        sig_ann.append({'cat': '', 'g1': g1i, 'g2': g2i, 'text': pw.stars})

                        fig = bar_chart(
                            bar_data, [''], groups, ylabel=ylabel,
                            colors=colors, palette=palette,
                            bar_width=0.8, group_gap=bar_gap,
                            show_points=show_points,
                            sig_annotations=sig_ann if sig_ann else None,
                            italic_labels=False,
                            xtick_fontsize=xtick_fontsize, xtick_bold=xtick_bold,
                            ytick_fontsize=ytick_fontsize, ytick_bold=ytick_bold,
                            legend_loc=legend_loc,
                            figsize=(fig_w, fig_h), **annotation_options, **axis_options,
                        )

                elif chart_type == 'Box Plot':
                    sig_ann = []
                    if stat_result and stat_result.pairwise:
                        for pw in stat_result.pairwise:
                            if _pw_selected(pw):
                                sig_ann.append({'g1': pw.group1, 'g2': pw.group2, 'text': pw.stars})
                    fig = box_plot(
                        data, groups, ylabel=ylabel,
                        colors=colors, palette=palette,
                        show_points=show_points,
                        sig_annotations=sig_ann if sig_ann else None,
                        xtick_fontsize=xtick_fontsize, xtick_bold=xtick_bold,
                        ytick_fontsize=ytick_fontsize, ytick_bold=ytick_bold,
                        legend_loc=legend_loc,
                        figsize=(fig_w, fig_h), **annotation_options, **axis_options,
                    )

                elif chart_type == 'Violin Plot':
                    sig_ann = []
                    if stat_result and stat_result.pairwise:
                        for pw in stat_result.pairwise:
                            if _pw_selected(pw):
                                sig_ann.append({'g1': pw.group1, 'g2': pw.group2, 'text': pw.stars})
                    fig = violin_plot(
                        data, groups, ylabel=ylabel,
                        colors=colors, palette=palette,
                        show_points=show_points,
                        sig_annotations=sig_ann if sig_ann else None,
                        xtick_fontsize=xtick_fontsize, xtick_bold=xtick_bold,
                        ytick_fontsize=ytick_fontsize, ytick_bold=ytick_bold,
                        legend_loc=legend_loc,
                        figsize=(fig_w, fig_h), **annotation_options, **axis_options,
                    )

            # ── LINE CHART ──────────────────────────────
            elif chart_type == 'Line Chart' and value_cols:
                groups = value_cols
                colors = custom_colors if custom_colors and len(custom_colors) >= len(groups) else None

                if x_col == '(use row index)':
                    timepoints = list(range(len(df)))
                else:
                    timepoints = df[x_col].dropna().tolist()

                data_dict = {}
                for g in groups:
                    for i, tp in enumerate(timepoints):
                        val = df[g].iloc[i] if i < len(df) else None
                        if val is not None and not pd.isna(val):
                            data_dict.setdefault((tp, g), []).append(float(val))

                fig = line_chart(
                    data_dict, sorted(set(timepoints)), groups,
                    ylabel=ylabel, xlabel=xlabel,
                    colors=colors, palette=palette,
                    show_points=show_points,
                    figsize=(fig_w, fig_h),
                    **axis_options,
                )

            # ── SCATTER ─────────────────────────────────
            elif chart_type == 'Scatter Plot':
                x_data = df[x_col].dropna().astype(float).values
                y_data = df[y_col].dropna().astype(float).values
                min_len = min(len(x_data), len(y_data))
                x_data, y_data = x_data[:min_len], y_data[:min_len]

                gids = None
                if group_col != 'None':
                    gids = df[group_col].iloc[:min_len].tolist()

                fig = scatter_plot(
                    x_data, y_data, group_ids=gids,
                    xlabel=xlabel, ylabel=ylabel,
                    palette=palette,
                    show_regression=show_reg, show_corr=show_corr,
                    figsize=(fig_w, fig_h),
                    **axis_options,
                )

            # ── PIE ─────────────────────────────────────
            elif chart_type == 'Pie Chart':
                labels = df[label_col].dropna().tolist()
                vals = df[value_col].dropna().astype(float).tolist()
                min_len = min(len(labels), len(vals))
                fig = pie_chart(labels[:min_len], vals[:min_len],
                                palette=palette, donut=donut, figsize=(fig_w, fig_h))

            # ── HEATMAP ─────────────────────────────────
            elif chart_type == 'Heatmap':
                numeric_df = df.select_dtypes(include=[np.number])
                if not numeric_df.empty:
                    fig = heatmap(
                        numeric_df, cmap=cmap, annotate=annotate,
                        z_score=z_score,
                        cluster_rows=cluster_rows, cluster_cols=cluster_cols,
                        figsize=(fig_w, fig_h),
                        **axis_options,
                    )

            # ── Display ─────────────────────────────────
            if fig:
                # Save figure bytes BEFORE st.pyplot closes it
                export_bufs = {}
                for fmt in ['png', 'tiff', 'svg', 'pdf']:
                    buf = BytesIO()
                    fig.savefig(buf, format=fmt, dpi=300, bbox_inches=None,
                                facecolor='white')
                    buf.seek(0)
                    export_bufs[fmt] = buf.getvalue()

                st.pyplot(fig, use_container_width=True, bbox_inches=None)
                plt.close(fig)

                st.caption('Export · PNG / TIFF at 300 DPI · SVG / PDF as vectors')
                ecols = st.columns(4)
                for i, (fmt, label, mime) in enumerate([
                    ('png',  'PNG',  'image/png'),
                    ('tiff', 'TIFF', 'image/tiff'),
                    ('svg',  'SVG',  'image/svg+xml'),
                    ('pdf',  'PDF',  'application/pdf'),
                ]):
                    with ecols[i]:
                        st.download_button(
                            f'{label}',
                            data=export_bufs[fmt],
                            file_name=f'graphium_figure.{fmt}',
                            mime=mime
                        )

            else:
                st.warning('Select data columns to generate a chart.')

            # ── Stats Results ────────────────────────────
            def _render_stat_result(sr):
                css_class = 'info' if sr.is_parametric else 'warning'
                rationale = sr.rationale
                for original, display in condition_names.items():
                    rationale = rationale.replace(f"'{original}'", f"'{display}'")
                st.markdown(
                    f'<div class="stat-box {css_class}">🔍 <b>{sr.test_name}</b><br>{rationale}</div>',
                    unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                if sr.pairwise_only:
                    c1.metric('Comparisons', len(sr.pairwise))
                    c2.metric('Correction', sr.correction_method)
                else:
                    c1.metric('Test statistic', f'{sr.statistic:.4f}')
                    c2.metric('p-value', f'{sr.p_value:.6f}')
                c3.metric('Method', 'Parametric' if sr.is_parametric else 'Non-parametric')

                if sr.normality_results:
                    with st.expander('🔬 Normality tests'):
                        for g, (w, p) in sr.normality_results.items():
                            status = '✅ Normal' if p > 0.05 else '⚠️ Non-normal'
                            st.text(f'{condition_names.get(g, g)}: W={w:.4f}, p={p:.4f}  {status}')

                if sr.pairwise:
                    title = 'Pairwise t-tests' if sr.pairwise_only else 'Post-hoc comparisons'
                    st.markdown(f'**{title}** ({sr.correction_method})')
                    pw_data = []
                    for pw in sr.pairwise:
                        row = {
                            'Comparison': f'{condition_names.get(pw.group1, pw.group1)} vs {condition_names.get(pw.group2, pw.group2)}',
                            'p (raw)': f'{pw.p_value:.6f}',
                            'p (adjusted)': f'{pw.p_adjusted:.6f}',
                            'Significance': pw.stars,
                            pw.effect_label: f'{pw.effect_size:.3f}' if np.isfinite(pw.effect_size) else '—',
                        }
                        if sr.pairwise_only:
                            row.update({'t statistic': f'{pw.statistic:.4f}',
                                        'n (group 1)': pw.n1, 'n (group 2)': pw.n2})
                        pw_data.append(row)
                    st.dataframe(pd.DataFrame(pw_data), use_container_width=True, hide_index=True)

            if stat_result:
                st.markdown('---')
                st.subheader('Statistics')

                # Grouped mode: dict of {gene: StatResult} → render per-gene tabs
                if isinstance(stat_result, dict):
                    gene_names = list(stat_result.keys())
                    tabs = st.tabs([category_names.get(gene, gene) for gene in gene_names])
                    for tab, gene in zip(tabs, gene_names):
                        with tab:
                            _render_stat_result(stat_result[gene])
                else:
                    _render_stat_result(stat_result)

        except AxisRangeError as e:
            plt.close(e.figure)
            st.error(str(e))
        except Exception as e:
            st.error(f'Error: {e}')
            import traceback
            st.code(traceback.format_exc())

else:
    # ── Welcome screen ───────────────────────────────────
    st.markdown("""
    ### Getting Started

    1. **Upload** an Excel (.xlsx) or CSV file using the sidebar
    2. **Select** a chart type above
    3. **Assign** your data columns in the settings panel
    4. **Graphium** auto-detects the correct statistical test and annotates your figure

    ---

    **Supported chart types:** Bar, Line, Box, Violin, Scatter, Pie, Heatmap

    **Statistics engine:** Auto-selects parametric/non-parametric tests based on
    normality testing (Shapiro-Wilk), with Bonferroni or FDR correction.
    """)
