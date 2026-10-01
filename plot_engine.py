"""
Graphium — Plot Engine
7 chart types with smart annotations, auto-ylim, smart legend.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import matplotlib.colors as mcolors
import seaborn as sns
from io import BytesIO
from scipy import stats as sp_stats
from annotation_engine import draw_annotations

# ── Style ────────────────────────────────────────────────────
STYLE = {
    'font.family': 'DejaVu Sans',
    'font.size': 12,
    'axes.linewidth': 1.5,
    'xtick.major.width': 1.5,
    'ytick.major.width': 1.5,
    'xtick.major.size': 6,
    'ytick.major.size': 6,
    'axes.spines.top': False,
    'axes.spines.right': False,
}
plt.rcParams.update(STYLE)

# ── Palettes ─────────────────────────────────────────────────
PALETTES = {
    'Grayscale': ['#333333', '#777777', '#AAAAAA', '#D5D5D5', '#F0F0F0'],
    'Nature': ['#E64B35', '#4DBBD5', '#00A087', '#3C5488', '#F39B7F', '#8491B4'],
    'Viridis': list(sns.color_palette('viridis', 8).as_hex()),
    'Paired': list(sns.color_palette('Paired', 12).as_hex()),
    'Pastel': ['#AEC6CF', '#FFB347', '#B39EB5', '#FF6961', '#77DD77', '#FDFD96'],
    'Bold': ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b'],
}

def get_palette(name, n):
    pal = PALETTES.get(name, PALETTES['Grayscale'])
    while len(pal) < n:
        pal = pal + pal
    return pal[:n]


# ── Helpers ──────────────────────────────────────────────────

class AxisRangeError(ValueError):
    """An invalid manual range, with its unfinished figure for cleanup."""

    def __init__(self, message, figure):
        super().__init__(message)
        self.figure = figure


def apply_axis_limits(ax, xlim=None, ylim=None):
    """Apply partial (minimum, maximum) bounds, preserving axis direction."""
    for name, limits, getter, setter in (
        ('X', xlim, ax.get_xlim, ax.set_xlim),
        ('Y', ylim, ax.get_ylim, ax.set_ylim),
    ):
        if limits is None or all(value is None for value in limits):
            continue
        current = getter()
        low, high = sorted(current)
        low = low if limits[0] is None else limits[0]
        high = high if limits[1] is None else limits[1]
        if not np.isfinite([low, high]).all() or low >= high:
            raise AxisRangeError(
                f'{name}-axis minimum must be smaller than its maximum, '
                'and both must be finite numbers. Set both limits if the '
                'automatic bound falls outside your chosen range.', ax.figure)
        setter((high, low) if current[0] > current[1] else (low, high))


def _automatic_ymax(ylim):
    return ylim is None or ylim[1] is None


def _manual_limits(xlim, ylim):
    return any(value is not None for limits in (xlim, ylim)
               if limits is not None for value in limits)


def calc_stats(values, error_type='SEM'):
    arr = np.array([v for v in values if v is not None and not np.isnan(v)], dtype=float)
    if len(arr) == 0:
        return 0, 0, arr
    error = (arr.std(ddof=1) if error_type == 'SD' else sp_stats.sem(arr)) if len(arr) > 1 else 0
    return arr.mean(), error, arr


def smart_legend_loc(ax, data_positions):
    """Find the quadrant with fewest data points for legend placement."""
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    xmid = (xlim[0] + xlim[1]) / 2
    ymid = (ylim[0] + ylim[1]) / 2
    quads = {
        'upper left':  lambda x, y: x < xmid and y > ymid,
        'upper right': lambda x, y: x > xmid and y > ymid,
        'lower right': lambda x, y: x > xmid and y < ymid,
        'lower left':  lambda x, y: x < xmid and y < ymid,
    }
    counts = {loc: sum(1 for x, y in data_positions if fn(x, y))
              for loc, fn in quads.items()}
    return min(counts, key=counts.get)


def place_legend_outside(ax, legend_els, fontsize=9):
    """Place legend outside the axes (right side) to avoid any overlap."""
    ax.legend(handles=legend_els, frameon=False, fontsize=fontsize,
              loc='upper left', bbox_to_anchor=(1.02, 1.0),
              borderaxespad=0)


def auto_ylim(ax, tops, margin=0.12):
    if not tops:
        return
    lo, hi = ax.get_ylim()
    needed = max(tops)
    new_hi = needed + (needed - lo) * margin
    if new_hi > hi:
        ax.set_ylim(lo, new_hi)


def fig_to_buf(fig, fmt='png', dpi=300):
    buf = BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches=None, facecolor='white')
    buf.seek(0)
    plt.close(fig)
    return buf


def add_above_bar_stars(ax, x, mean, sem, raw, text, fontsize=12):
    """Place star text above a bar, returns y_top for ylim calc."""
    y_top = max(mean + sem, raw.max()) if len(raw) > 0 else mean + sem
    y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
    offset = y_range * 0.03
    ax.text(x, y_top + offset, text, ha='center', va='bottom',
            fontsize=fontsize, fontweight='bold')
    return y_top + offset + y_range * 0.05


# ═════════════════════════════════════════════════════════════
#  1. LINE CHART
# ═════════════════════════════════════════════════════════════

def line_chart(data_dict, timepoints, groups, ylabel='Value',
               xlabel='Time', colors=None, palette='Grayscale',
               show_points=True, error_type='SEM',
               sig_map=None, figsize=(6, 4.5),
               xticks=None, xlim=None, ylim=None):
    """
    data_dict: {(timepoint, group): [values]}
    sig_map: {timepoint: {(g1, g2): '***'}} or {timepoint: '*'} for above-point
    """
    if colors is None:
        colors = get_palette(palette, len(groups))
    markers = ['o', 's', '^', 'D', 'v', 'p'][:len(groups)]

    fig, ax = plt.subplots(figsize=figsize)
    all_pos = []
    ann_tops = []

    for gi, group in enumerate(groups):
        means, errs = [], []
        for tp in timepoints:
            m, s, raw = calc_stats(data_dict.get((tp, group), []))
            means.append(m)
            errs.append(s)
            if show_points and len(raw) > 0:
                jitter = np.random.uniform(-0.15, 0.15, size=len(raw))
                ax.scatter([tp]*len(raw) + jitter, raw,
                           color=colors[gi], alpha=0.35, s=30,
                           edgecolors='none', zorder=3)
                all_pos.extend([(tp, r) for r in raw])

        fc = 'white' if gi == 0 and len(groups) == 2 else colors[gi]
        ax.errorbar(timepoints, means, yerr=errs,
                    fmt='-', marker=markers[gi], markersize=8,
                    color=colors[gi], markerfacecolor=fc,
                    markeredgecolor=colors[gi], markeredgewidth=1.5,
                    linewidth=2, capsize=4, capthick=1.5,
                    label=group, zorder=5)
        all_pos.extend([(tp, m+s) for tp, m, s in zip(timepoints, means, errs)])

    # Significance
    if sig_map:
        for tp, info in sig_map.items():
            if isinstance(info, str):
                # Simple: star above highest point at this timepoint
                max_y = max(calc_stats(data_dict.get((tp, g), [0]))[0] +
                            calc_stats(data_dict.get((tp, g), [0]))[1]
                            for g in groups)
                ax.text(tp, max_y + 0.15, info, ha='center', va='bottom',
                        fontsize=14, fontweight='bold')
                ann_tops.append(max_y + 0.5)

    ax.set_xlabel(xlabel, fontsize=14, fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=14, fontweight='bold')
    if xticks:
        ax.set_xticks(xticks)
    ax.set_ylim(bottom=0)
    auto_ylim(ax, ann_tops)
    apply_axis_limits(ax, xlim, ylim)
    if _manual_limits(xlim, ylim):
        for text in ax.texts:
            text.set_clip_on(True)
    ax.legend(frameon=False, fontsize=10, loc=smart_legend_loc(ax, all_pos))
    fig.tight_layout()
    return fig


# ═════════════════════════════════════════════════════════════
#  2. BAR CHART (simple + grouped)
# ═════════════════════════════════════════════════════════════

def bar_chart(data_dict, categories, groups, ylabel='Value',
              colors=None, palette='Grayscale',
              bar_width=0.8, group_gap=0.0,
              show_points=True, error_type='SEM',
              italic_labels=True, point_size=25,
              xtick_fontsize=11, xtick_bold=False,
              ytick_fontsize=11, ytick_bold=False,
              show_legend=True, legend_loc='auto',
              sig_annotations=None, figsize=(8, 5),
              custom_annotations=None, annotation_fontsize=13,
              annotation_gap=8, symbol_spacing=1, xlim=None, ylim=None,
              category_labels=None, group_labels=None):
    """
    data_dict: {(category, group): [values]}
    sig_annotations: [{'cat', 'group_idx', 'text'}] for above-bar
                  or [{'cat', 'g1', 'g2', 'text'}] for bracket
    """
    if colors is None:
        colors = get_palette(palette, len(groups))

    n_groups = len(groups)
    total_bw = bar_width * n_groups + group_gap * (n_groups - 1)

    fig, ax = plt.subplots(figsize=figsize)
    all_pos = []
    rng = np.random.default_rng(42)

    for ci, cat in enumerate(categories):
        base_x = ci * (total_bw + 0.6)
        for gi, group in enumerate(groups):
            x = base_x + gi * (bar_width + group_gap)
            vals = data_dict.get((cat, group), [])
            if not vals:
                continue
            m, s, raw = calc_stats(vals, error_type)

            ax.bar(x, m, width=bar_width, color=colors[gi],
                   edgecolor='black', linewidth=1.0, zorder=2)
            ax.errorbar(x, m, yerr=s, fmt='none', color='black',
                        capsize=3, capthick=1.2, linewidth=1.2, zorder=4)

            if show_points and len(raw) > 0:
                jit = rng.uniform(-bar_width*0.25, bar_width*0.25, size=len(raw))
                ax.scatter([x]*len(raw)+jit, raw, s=point_size, zorder=5,
                           edgecolors='black', linewidths=1.0,
                           facecolors='white', alpha=0.85)
                all_pos.extend([(x, r) for r in raw])
            all_pos.append((x, m + s))

    # X labels
    centers = [ci * (total_bw + 0.6) + (n_groups - 1) * (bar_width + group_gap) / 2
               for ci in range(len(categories))]
    ax.set_xticks(centers)
    ax.set_xticklabels([(category_labels or {}).get(cat, cat) for cat in categories], fontsize=xtick_fontsize,
                       fontstyle='italic' if italic_labels else 'normal',
                       fontweight='bold' if xtick_bold else 'normal')
    ax.tick_params(axis='y', labelsize=ytick_fontsize)
    if ytick_bold:
        for lbl in ax.get_yticklabels():
            lbl.set_fontweight('bold')
    ax.set_ylabel(ylabel, fontsize=14, fontweight='bold')
    ax.set_ylim(bottom=0)

    # Normalize all labels to the same measured layout engine.
    annotations = []

    def bar_x(cat, gi):
        return categories.index(cat) * (total_bw + 0.6) + gi * (bar_width + group_gap)

    def bar_top(cat, gi):
        mean, sem, raw = calc_stats(data_dict.get((cat, groups[gi]), []), error_type)
        return max(mean + sem, raw.max()) if len(raw) else mean + sem

    for ann in sig_annotations or []:
        if 'cat1' in ann and 'cat2' in ann:
            gi = ann.get('group_idx', 0)
            ci1, ci2 = categories.index(ann['cat1']), categories.index(ann['cat2'])
            x1, x2 = bar_x(ann['cat1'], gi), bar_x(ann['cat2'], gi)
            top = max(bar_top(categories[ci], gi)
                      for ci in range(min(ci1, ci2), max(ci1, ci2) + 1))
            annotations.append(dict(x=(x1+x2)/2, x1=x1, x2=x2, y=top, text=ann['text']))
        elif 'group_idx' in ann:
            gi = ann['group_idx']
            annotations.append(dict(x=bar_x(ann['cat'], gi), y=bar_top(ann['cat'], gi),
                                    text=ann['text']))
        else:
            g1, g2 = ann['g1'], ann['g2']
            x1, x2 = bar_x(ann['cat'], g1), bar_x(ann['cat'], g2)
            top = max(bar_top(ann['cat'], gi) for gi in range(min(g1, g2), max(g1, g2) + 1))
            annotations.append(dict(x=(x1+x2)/2, x1=x1, x2=x2, y=top, text=ann['text']))

    # Above-bar comparisons share one horizontal row. Keep each comparison's
    # star count separate when several comparisons target the same bar.
    above_bar = [ann for ann in annotations if 'x1' not in ann]
    if above_bar:
        row_top = max(bar_top(cat, gi)
                      for cat in categories for gi in range(n_groups)
                      if len(data_dict.get((cat, groups[gi]), [])))
        by_x = {}
        for ann in above_bar:
            row = by_x.setdefault(ann['x'], dict(ann, y=row_top, text_parts=[], horizontal_row=True))
            row['text_parts'].append(ann['text'])
        annotations = list(by_x.values()) + [ann for ann in annotations if 'x1' in ann]

    for ann in custom_annotations or []:
        cat, gi = ann['cat'], ann.get('group_idx', 0)
        if cat in categories and 0 <= gi < n_groups:
            annotations.append(dict(ann, x=bar_x(cat, gi), y=bar_top(cat, gi)))

    # Legend — 'auto' mirrors the old behavior (outside if annotations, else inside)
    if show_legend:
        legend_els = [Patch(facecolor=colors[gi], edgecolor='black',
                            label=(group_labels or {}).get(groups[gi], groups[gi]))
                      for gi in range(n_groups)]
        if legend_loc == 'outside' or (legend_loc == 'auto' and annotations):
            place_legend_outside(ax, legend_els, fontsize=9)
        else:
            ax.legend(handles=legend_els, frameon=False, fontsize=9,
                      loc=smart_legend_loc(ax, all_pos))

    apply_axis_limits(ax, xlim, ylim)
    fig.tight_layout()
    draw_annotations(ax, annotations, fontsize=annotation_fontsize,
                     gap_points=annotation_gap, symbol_spacing=symbol_spacing,
                     expand_ylim=_automatic_ymax(ylim), clip_on=_manual_limits(xlim, ylim))
    return fig


# ═════════════════════════════════════════════════════════════
#  3. PIE CHART
# ═════════════════════════════════════════════════════════════

def pie_chart(labels, values, colors=None, palette='Pastel',
              explode_idx=None, donut=False, figsize=(6, 6)):
    if colors is None:
        colors = get_palette(palette, len(labels))
    explode = [0.05 if explode_idx and i in explode_idx else 0
               for i in range(len(labels))]

    fig, ax = plt.subplots(figsize=figsize)
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=colors, explode=explode,
        autopct='%1.1f%%', startangle=90,
        textprops={'fontsize': 12}
    )
    for t in autotexts:
        t.set_fontweight('bold')

    if donut:
        centre = plt.Circle((0, 0), 0.60, fc='white')
        ax.add_artist(centre)

    ax.set_aspect('equal')
    fig.tight_layout()
    return fig


# ═════════════════════════════════════════════════════════════
#  4. BOX PLOT
# ═════════════════════════════════════════════════════════════

def box_plot(data_dict, groups, ylabel='Value',
             colors=None, palette='Grayscale',
             show_points=True, notched=False,
             xtick_fontsize=12, xtick_bold=False,
             ytick_fontsize=11, ytick_bold=False,
             legend_loc='auto',
             sig_annotations=None, figsize=(6, 5),
                custom_annotations=None, annotation_fontsize=13,
                annotation_gap=8, symbol_spacing=1, xlim=None, ylim=None):
    """data_dict: {group_name: [values]}"""
    if colors is None:
        colors = get_palette(palette, len(groups))

    fig, ax = plt.subplots(figsize=figsize)
    all_pos = []
    rng = np.random.default_rng(42)

    bp = ax.boxplot(
        [data_dict[g] for g in groups],
        positions=range(len(groups)),
        widths=0.6, patch_artist=True,
        notch=notched,
        boxprops=dict(linewidth=1.5),
        medianprops=dict(color='black', linewidth=2),
        whiskerprops=dict(linewidth=1.5),
        capprops=dict(linewidth=1.5),
        showfliers=not show_points,
    )

    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)

    if show_points:
        for gi, g in enumerate(groups):
            raw = np.array(data_dict[g], dtype=float)
            jit = rng.uniform(-0.12, 0.12, size=len(raw))
            ax.scatter([gi]*len(raw)+jit, raw, s=30, zorder=5,
                       edgecolors='black', linewidths=0.8,
                       facecolors='white', alpha=0.8)
            all_pos.extend([(gi, r) for r in raw])

    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(groups, fontsize=xtick_fontsize,
                       fontweight='bold' if xtick_bold else 'normal')
    ax.tick_params(axis='y', labelsize=ytick_fontsize)
    if ytick_bold:
        for lbl in ax.get_yticklabels():
            lbl.set_fontweight('bold')
    ax.set_ylabel(ylabel, fontsize=14, fontweight='bold')

    annotations = []
    for ann in sig_annotations or []:
        g1 = groups.index(ann['g1']) if isinstance(ann['g1'], str) else ann['g1']
        g2 = groups.index(ann['g2']) if isinstance(ann['g2'], str) else ann['g2']
        top = max(max(data_dict[groups[gi]]) for gi in range(min(g1, g2), max(g1, g2)+1)
                  if len(data_dict[groups[gi]]))
        annotations.append(dict(x=(g1+g2)/2, x1=g1, x2=g2, y=top, text=ann['text']))
    for ann in custom_annotations or []:
        if ann['group'] in groups and len(data_dict[ann['group']]):
            annotations.append(dict(ann, x=groups.index(ann['group']),
                                    y=max(data_dict[ann['group']])))

    # Legend
    legend_els = [Patch(facecolor=colors[gi], edgecolor='black', label=groups[gi])
                  for gi in range(len(groups))]
    if legend_loc == 'outside' or (legend_loc == 'auto' and annotations):
        place_legend_outside(ax, legend_els, fontsize=9)
    else:
        ax.legend(handles=legend_els, frameon=False, fontsize=9,
                  loc=smart_legend_loc(ax, all_pos))
    apply_axis_limits(ax, xlim, ylim)
    fig.tight_layout()
    draw_annotations(ax, annotations, fontsize=annotation_fontsize,
                     gap_points=annotation_gap, symbol_spacing=symbol_spacing,
                     expand_ylim=_automatic_ymax(ylim), clip_on=_manual_limits(xlim, ylim))
    return fig


# ═════════════════════════════════════════════════════════════
#  5. VIOLIN PLOT
# ═════════════════════════════════════════════════════════════

def violin_plot(data_dict, groups, ylabel='Value',
                colors=None, palette='Grayscale',
                show_points=True, inner='box',
                xtick_fontsize=12, xtick_bold=False,
                ytick_fontsize=11, ytick_bold=False,
                legend_loc='auto',
                sig_annotations=None, figsize=(6, 5),
                custom_annotations=None, annotation_fontsize=13,
                annotation_gap=8, symbol_spacing=1, xlim=None, ylim=None):
    """data_dict: {group_name: [values]}"""
    if colors is None:
        colors = get_palette(palette, len(groups))

    fig, ax = plt.subplots(figsize=figsize)
    all_pos = []
    rng = np.random.default_rng(42)

    parts = ax.violinplot(
        [data_dict[g] for g in groups],
        positions=range(len(groups)),
        showmeans=False, showmedians=True, showextrema=False
    )

    for i, pc in enumerate(parts['bodies']):
        pc.set_facecolor(colors[i])
        pc.set_edgecolor('black')
        pc.set_linewidth(1.2)
        pc.set_alpha(0.7)
    parts['cmedians'].set_color('black')
    parts['cmedians'].set_linewidth(2)

    if show_points:
        for gi, g in enumerate(groups):
            raw = np.array(data_dict[g], dtype=float)
            jit = rng.uniform(-0.08, 0.08, size=len(raw))
            ax.scatter([gi]*len(raw)+jit, raw, s=25, zorder=5,
                       edgecolors='black', linewidths=0.8,
                       facecolors='white', alpha=0.8)
            all_pos.extend([(gi, r) for r in raw])

    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(groups, fontsize=xtick_fontsize,
                       fontweight='bold' if xtick_bold else 'normal')
    ax.tick_params(axis='y', labelsize=ytick_fontsize)
    if ytick_bold:
        for lbl in ax.get_yticklabels():
            lbl.set_fontweight('bold')
    ax.set_ylabel(ylabel, fontsize=14, fontweight='bold')

    annotations = []
    for ann in sig_annotations or []:
        g1 = groups.index(ann['g1']) if isinstance(ann['g1'], str) else ann['g1']
        g2 = groups.index(ann['g2']) if isinstance(ann['g2'], str) else ann['g2']
        top = max(max(data_dict[groups[gi]]) for gi in range(min(g1, g2), max(g1, g2)+1)
                  if len(data_dict[groups[gi]]))
        annotations.append(dict(x=(g1+g2)/2, x1=g1, x2=g2, y=top, text=ann['text']))
    for ann in custom_annotations or []:
        if ann['group'] in groups and len(data_dict[ann['group']]):
            annotations.append(dict(ann, x=groups.index(ann['group']),
                                    y=max(data_dict[ann['group']])))

    # Legend
    legend_els = [Patch(facecolor=colors[gi], edgecolor='black', label=groups[gi])
                  for gi in range(len(groups))]
    if legend_loc == 'outside' or (legend_loc == 'auto' and annotations):
        place_legend_outside(ax, legend_els, fontsize=9)
    else:
        ax.legend(handles=legend_els, frameon=False, fontsize=9,
                  loc=smart_legend_loc(ax, all_pos))
    apply_axis_limits(ax, xlim, ylim)
    fig.tight_layout()
    draw_annotations(ax, annotations, fontsize=annotation_fontsize,
                     gap_points=annotation_gap, symbol_spacing=symbol_spacing,
                     expand_ylim=_automatic_ymax(ylim), clip_on=_manual_limits(xlim, ylim))
    return fig


# ═════════════════════════════════════════════════════════════
#  6. SCATTER PLOT
# ═════════════════════════════════════════════════════════════

def scatter_plot(x, y, groups_label=None, group_ids=None,
                 xlabel='X', ylabel='Y',
                 colors=None, palette='Bold',
                 show_regression=True, show_corr=True,
                 figsize=(6, 5), xlim=None, ylim=None):
    """
    x, y: arrays of numbers
    group_ids: optional array of group labels per point
    """
    fig, ax = plt.subplots(figsize=figsize)
    x = np.array(x, dtype=float)
    y = np.array(y, dtype=float)

    if group_ids is not None:
        unique_groups = sorted(set(group_ids))
        cols = get_palette(palette, len(unique_groups))
        for gi, g in enumerate(unique_groups):
            mask = np.array(group_ids) == g
            ax.scatter(x[mask], y[mask], c=cols[gi], s=40,
                       edgecolors='black', linewidths=0.5, label=g, alpha=0.8)
        ax.legend(frameon=False, fontsize=10)
    else:
        ax.scatter(x, y, c=get_palette(palette, 1)[0], s=40,
                   edgecolors='black', linewidths=0.5, alpha=0.8)

    if show_regression:
        mask = ~(np.isnan(x) | np.isnan(y))
        if mask.sum() > 2:
            slope, intercept, r, p, se = sp_stats.linregress(x[mask], y[mask])
            xr = np.linspace(x[mask].min(), x[mask].max(), 100)
            ax.plot(xr, slope * xr + intercept, 'k--', linewidth=1.5, alpha=0.6)

            if show_corr:
                ax.text(0.05, 0.95,
                        f'r = {r:.3f}\np = {p:.4f}',
                        transform=ax.transAxes, fontsize=10,
                        va='top', ha='left',
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    ax.set_xlabel(xlabel, fontsize=14, fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=14, fontweight='bold')
    apply_axis_limits(ax, xlim, ylim)
    fig.tight_layout()
    return fig


# ═════════════════════════════════════════════════════════════
#  7. HEATMAP
# ═════════════════════════════════════════════════════════════

def heatmap(data, row_labels=None, col_labels=None,
            cmap='RdBu_r', annotate=True, z_score=False,
            cluster_rows=False, cluster_cols=False,
            figsize=(8, 6), xlim=None, ylim=None):
    """
    data: 2D numpy array or pandas DataFrame
    """
    import pandas as pd

    if isinstance(data, pd.DataFrame):
        if row_labels is None:
            row_labels = data.index.tolist()
        if col_labels is None:
            col_labels = data.columns.tolist()
        data = data.values.astype(float)

    if z_score:
        # Row-wise z-score
        row_means = data.mean(axis=1, keepdims=True)
        row_stds = data.std(axis=1, keepdims=True)
        row_stds[row_stds == 0] = 1
        data = (data - row_means) / row_stds

    if cluster_rows or cluster_cols:
        from scipy.cluster.hierarchy import linkage, dendrogram, leaves_list
        if cluster_rows and data.shape[0] > 2:
            Z = linkage(data, method='ward')
            order = leaves_list(Z)
            data = data[order]
            if row_labels:
                row_labels = [row_labels[i] for i in order]
        if cluster_cols and data.shape[1] > 2:
            Z = linkage(data.T, method='ward')
            order = leaves_list(Z)
            data = data[:, order]
            if col_labels:
                col_labels = [col_labels[i] for i in order]

    fig, ax = plt.subplots(figsize=figsize)
    im = ax.imshow(data, cmap=cmap, aspect='auto')
    fig.colorbar(im, ax=ax, shrink=0.8)

    if annotate and data.size < 200:
        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                val = data[i, j]
                color = 'white' if abs(val) > (data.max() - data.min()) * 0.6 else 'black'
                ax.text(j, i, f'{val:.1f}', ha='center', va='center',
                        fontsize=8, color=color)

    if row_labels:
        ax.set_yticks(range(len(row_labels)))
        ax.set_yticklabels(row_labels, fontsize=10)
    if col_labels:
        ax.set_xticks(range(len(col_labels)))
        ax.set_xticklabels(col_labels, fontsize=10, rotation=45, ha='right')

    apply_axis_limits(ax, xlim, ylim)
    if _manual_limits(xlim, ylim):
        for text in ax.texts:
            text.set_clip_on(True)
    fig.tight_layout()
    return fig
