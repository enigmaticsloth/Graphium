"""Place figure annotations with physical spacing and measured collision checks."""

import numpy as np
from matplotlib.transforms import Bbox


def spaced_symbols(text, spacing=1):
    """Space repeated symbols without changing their count or ordinary text."""
    text = str(text)
    if len(text) > 1 and len(set(text)) == 1 and text[0] in '*#†‡':
        return ('\u2009' * int(spacing)).join(text)
    return text


def _label_text(ann, spacing):
    return '\u2003\u2003'.join(spaced_symbols(part, spacing)
                             for part in ann.get('text_parts', [ann['text']]))


def _row_fontsize(ax, entries, renderer, fontsize, spacing, padding):
    """Fit one row of automatic labels without moving them off their bars."""
    labels = []
    for ann in entries:
        if not ann.get('horizontal_row'):
            continue
        x = ax.transData.transform((ann['x'], ann['y']))[0]
        if not ax.bbox.xmin <= x <= ax.bbox.xmax:
            continue
        probe = ax.text(ann['x'], ann['y'], _label_text(ann, spacing),
                        fontsize=fontsize, fontweight='bold', parse_math=False)
        width = probe.get_window_extent(renderer).width
        probe.remove()
        labels.append((x, width))
    labels.sort()
    scale = 1.0
    for x, width in labels:
        if width:
            scale = min(scale, 2 * min(x - ax.bbox.xmin, ax.bbox.xmax - x) / width)
    for (x1, w1), (x2, w2) in zip(labels, labels[1:]):
        if w1 + w2:
            scale = min(scale, 2 * (x2 - x1 - padding - 1) / (w1 + w2))
    return max(1, fontsize * scale)


def draw_annotations(ax, annotations, fontsize=13, gap_points=8,
                     symbol_spacing=1, stack_gap_points=6, expand_ylim=True,
                     clip_on=False):
    """Draw labels/brackets above data, then expand the axis to fit them.

    Entries contain x, y (top of data/error bar), and text. Optional x1/x2
    define a bracket; x_offset/y_offset are in points, independent of data
    scale. Optional fontsize overrides the common annotation font size.
    Call after tight_layout so physical spacing uses the final axes size.
    A fixed Y maximum disables expansion and clips labels to the axes.
    """
    entries = [a for a in annotations if str(a.get('text', '')).strip()
               and np.isfinite(a['x']) and np.isfinite(a['y'])]
    if not entries:
        return []

    fig = ax.figure
    # Bracket lines must not trigger Matplotlib's own autoscaling mid-layout.
    ax.set_ylim(ax.get_ylim())
    artists = []
    # Axis expansion changes the data units per point, so reflow with the
    # new scale. The measured gaps remain the same in every export format.
    for _ in range(16):
        for artist in artists:
            artist.remove()
        artists = []
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        lo, hi = ax.get_ylim()
        pixels_per_point = fig.dpi / 72
        units_per_pixel = (hi - lo) / ax.bbox.height
        units_per_point = units_per_pixel * pixels_per_point
        occupied = []
        row_fontsize = _row_fontsize(
            ax, entries, renderer, fontsize, symbol_spacing,
            stack_gap_points * pixels_per_point)

        for ann in entries:
            bracket = 'x1' in ann and 'x2' in ann
            size = row_fontsize if ann.get('horizontal_row') else ann.get('fontsize', fontsize)
            x_pixels = ax.transData.transform((ann['x'], ann['y']))[0]
            x_pixels += ann.get('x_offset', 0) * pixels_per_point
            x = ax.transData.inverted().transform((x_pixels, ax.bbox.ymin))[0]
            bottom = ann['y'] + (gap_points + ann.get('y_offset', 0)) * units_per_point
            bracket_height = 4 * units_per_point if bracket else 0
            text_gap = 3 * units_per_point if bracket else 0
            text = ax.text(
                x, bottom + bracket_height + text_gap,
                _label_text(ann, symbol_spacing),
                ha='center', va='bottom', fontsize=size, fontweight='bold',
                color='black', clip_on=clip_on or not expand_ylim, zorder=10,
                parse_math=False,
            )

            def bounds():
                box = text.get_window_extent(renderer)
                if bracket:
                    p1 = ax.transData.transform((ann['x1'], bottom))
                    p2 = ax.transData.transform((ann['x2'], bottom + bracket_height))
                    bracket_box = Bbox.from_extents(
                        min(p1[0], p2[0]), p1[1], max(p1[0], p2[0]), p2[1])
                    box = Bbox.union([box, bracket_box])
                return box

            box = bounds()
            padding = stack_gap_points * pixels_per_point
            # Moving above one label can encounter another. Iterate until
            # this entire label/bracket has a clear horizontal lane.
            while True:
                collisions = [b for b, horizontal_row in occupied
                              if not (ann.get('horizontal_row') and horizontal_row)
                              and box.x0 < b.x1 + padding and box.x1 > b.x0 - padding
                              and box.y0 < b.y1 + padding and box.y1 > b.y0 - padding]
                if not collisions:
                    break
                shift = (max(b.y1 for b in collisions) + padding + 0.1 - box.y0) * units_per_pixel
                bottom += shift
                text.set_y(bottom + bracket_height + text_gap)
                box = bounds()

            if bracket:
                line, = ax.plot(
                    [ann['x1'], ann['x1'], ann['x2'], ann['x2']],
                    [bottom, bottom + bracket_height, bottom + bracket_height, bottom],
                    color='black', lw=1.2, clip_on=clip_on or not expand_ylim, zorder=9)
                artists.append(line)
            artists.append(text)
            occupied.append((box, ann.get('horizontal_row', False)))

        top = max(b.y1 for b, _ in occupied)
        headroom = 8 * pixels_per_point
        overflow = top + headroom - ax.bbox.ymax
        if not expand_ylim or overflow <= 0.5:
            break
        ax.set_ylim(lo, hi + overflow * units_per_pixel * 1.1)

    return artists
