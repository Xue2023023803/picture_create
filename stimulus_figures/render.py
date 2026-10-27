"""Draw reusable vector assets with the original stimulus geometry."""
from __future__ import annotations

import math
from pathlib import Path
import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors, font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Polygon, Rectangle

from .config import StimulusStyle


def points_for(style: StimulusStyle, seed: int):
    rng = random.Random(seed)
    side = style.canvas_size
    offset = (side - style.inner_size) / 2
    lo = offset + style.inner_margin + style.dot_radius
    hi = side - lo
    points, links = [], []
    if style.mode == 3:
        return points, links, style.patch_side
    minimum = 2 * style.dot_radius + style.min_gap
    count = style.n_dots if style.dot_mode == "isolated" else style.n_pairs

    def clear(p):
        return all(math.dist(p, q) >= minimum for q in points)

    for _ in range(8000):
        if (len(points) if style.dot_mode == "isolated" else len(links)) == count:
            break
        a = (rng.uniform(lo, hi), rng.uniform(lo, hi))
        if not clear(a):
            continue
        if style.dot_mode == "isolated":
            points.append(a)
            continue
        theta = rng.uniform(0, 2 * math.pi)
        distance = style.pair_distance_factor * style.dot_radius
        b = (a[0] + distance * math.cos(theta), a[1] + distance * math.sin(theta))
        if lo <= b[0] <= hi and lo <= b[1] <= hi and clear(b):
            points.extend((a, b))
            links.append((a, b))
    if (len(points) if style.dot_mode == "isolated" else len(links)) != count:
        raise ValueError("Unable to place all dots after 8000 attempts; reduce count/radius or enlarge inner_size")
    patch_side = rng.choice(("left", "right")) if style.patch_side == "random" else style.patch_side
    return points, links, patch_side


def clip_halfplane(polygon, a, b, c):
    result = []
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        fs = a * start[0] + b * start[1] + c
        fe = a * end[0] + b * end[1] + c
        if (fs <= 0) != (fe <= 0):
            t = fs / (fs - fe)
            result.append((start[0] + t * (end[0] - start[0]), start[1] + t * (end[1] - start[1])))
        if fe <= 0:
            result.append(end)
    return result


def cross_polygons(side, width):
    square = [(0, 0), (side, 0), (side, side), (0, side)]
    c = width / math.sqrt(2)
    main = clip_halfplane(clip_halfplane(square, -1, 1, -c), 1, -1, -c)
    anti = clip_halfplane(clip_halfplane(square, 1, 1, -side - c), -1, -1, side - c)
    return main, anti


def draw_stimulus(style, seed, target, formats):
    target = Path(target)
    colors.to_rgba(style.cross_color)  # Fail before opening a figure.
    points, links, patch_side = points_for(style, seed)
    side = style.canvas_size
    offset = (side - style.inner_size) / 2
    with matplotlib.rc_context({"svg.hashsalt": str(seed), "svg.fonttype": "path", "pdf.fonttype": 42, "ps.fonttype": 42}):
        fig = plt.figure(figsize=(side / 100, side / 100), dpi=100)
        try:
            ax = fig.add_axes([0, 0, 1, 1], xlim=(0, side), ylim=(0, side), aspect="equal")
            ax.axis("off")
            gray = style.background_gray
            ax.add_patch(Rectangle((0, 0), side, side, facecolor=(gray, gray, gray), edgecolor="none"))
            if style.cross_width:
                for polygon in cross_polygons(side, style.cross_width):
                    ax.add_patch(Polygon(polygon, facecolor=style.cross_color, edgecolor="none", zorder=2))
            if style.mode == 1:
                pairs = (("red", "lime"), ("red", "yellow"), ("blue", "lime"), ("blue", "yellow"))
                a, b = pairs[style.patch_pattern]
                grid = ((b, a), (a, b)) if style.patch_diagonal == "main" else ((a, b), (b, a))
                px = offset - style.patch_gap - style.patch_size if patch_side == "left" else offset + style.inner_size + style.patch_gap
                py = (side - style.patch_size) / 2
                cell = style.patch_size / 2
                for r in range(2):
                    for c in range(2):
                        ax.add_patch(Rectangle((px + c * cell, py + (1 - r) * cell), cell, cell,
                                               facecolor=grid[r][c], edgecolor="none", zorder=3))
            if style.border_width:
                inset = style.border_width * 100 / 72 / 2
                ax.add_patch(Rectangle((inset, inset), side - 2 * inset, side - 2 * inset,
                                       fill=False, edgecolor="black", linewidth=style.border_width, zorder=4))
            for a, b in links:
                ax.add_line(Line2D((a[0], b[0]), (a[1], b[1]), color=style.dot_color,
                                   linewidth=style.link_width, solid_capstyle="round", zorder=5))
            for p in points:
                ax.add_patch(Circle(p, style.dot_radius, facecolor=style.dot_color, edgecolor="none", zorder=6))
            for fmt in dict.fromkeys(["svg", *formats]):
                fig.savefig(target.with_suffix(f".{fmt}"), format=fmt, dpi=150,
                            metadata={"Date": None} if fmt == "svg" else None)
        finally:
            plt.close(fig)
    return target.with_suffix(".svg")


def check_font(name):
    try:
        font_manager.findfont(font_manager.FontProperties(family=name), fallback_to_default=False)
    except ValueError as exc:
        raise ValueError(f"Font {name!r} is unavailable; select an installed font in figure.font_family") from exc


def draw_title(title, target, family, size, formats):
    """Measure the text itself, so transparent axes do not add empty margins."""
    check_font(family)
    with matplotlib.rc_context({"svg.fonttype": "path", "svg.hashsalt": "title", "pdf.fonttype": 42, "ps.fonttype": 42}):
        fig = plt.figure(figsize=(12, 2), dpi=100)
        try:
            text = fig.text(0, 0, title, fontsize=size, family=family, weight="bold", va="bottom", linespacing=1.35)
            fig.canvas.draw()
            bbox = text.get_window_extent(fig.canvas.get_renderer()).transformed(fig.dpi_scale_trans.inverted())
            for fmt in dict.fromkeys(["svg", *formats]):
                fig.savefig(Path(target).with_suffix(f".{fmt}"), format=fmt, bbox_inches=bbox.padded(0.04),
                            transparent=True, dpi=150, metadata={"Date": None} if fmt == "svg" else None)
        finally:
            plt.close(fig)
    return Path(target).with_suffix(".svg")
