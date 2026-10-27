"""Compose vector panels into horizontal or oblique procedure illustrations."""
from __future__ import annotations

import math
from xml.etree import ElementTree as ET

from .assets import Artwork, SVG, element


def text(parent, label, x, y, size, family, anchor="middle", bold=False):
    node = element(parent, "text", x=x, y=y, font_size=size, font_family=family,
                   text_anchor=anchor, fill="#111111", font_weight="bold" if bold else "normal")
    node.text = str(label)
    return node


def line(parent, x1, y1, x2, y2, arrow=False):
    attrs = dict(x1=x1, y1=y1, x2=x2, y2=y2, stroke="#111111", stroke_width=2)
    if arrow:
        attrs["marker_end"] = "url(#timeline-arrow)"
    return element(parent, "line", **attrs)


def compose(config, assets, titles, target):
    s = config.figure
    n = len(config.rows[0].stimuli)
    f, gap, margin = s.frame_size, s.frame_gap, s.margin
    oblique = s.layout == "3d"
    dx = (f + gap) * s.step_x if oblique else f + gap
    dy = (f + gap) * s.step_y if oblique else 0
    span = max((n - 1) * dx + f, n * dx)
    content_width = max(span + f * 0.6, len(config.physical_series) * s.label_size * 3)
    page_width = 2 * margin + content_width
    x0 = margin + (content_width - span - f * 0.5) / 2
    svg = ET.Element(f"{{{SVG}}}svg", {"version": "1.1", "role": "img"})
    element(svg, "title").text = "Stimulus presentation schematic"
    element(svg, "desc").text = "Static illustration. Frame widths are schematic; time labels do not control presentation."
    defs = element(svg, "defs")
    marker = element(defs, "marker", id="timeline-arrow", markerWidth=10, markerHeight=8,
                     refX=9, refY=4, orient="auto", markerUnits="strokeWidth")
    element(marker, "path", d="M0,0 L10,4 L0,8 Z", fill="#111111")
    artwork = {}
    for i, (name, path) in enumerate(assets.items()):
        art = Artwork(path, f"asset-{i}-")
        art.define(defs, f"asset-{i}")
        artwork[name] = (art, f"asset-{i}")
    title_art = []
    for i, path in enumerate(titles):
        art = Artwork(path, f"title-{i}-")
        art.define(defs, f"title-{i}")
        title_art.append(art)
    background = element(svg, "rect", width=page_width, height=1, fill="white")
    body = element(svg, "g", id="procedure")
    cursor = margin
    axes = []
    series_y = None
    for row_index, row in enumerate(config.rows):
        group = element(body, "g", id=f"row-{row_index + 1}")
        title_height = max(36, s.title_size * 1.45 * len(row.title.splitlines()))
        title_art[row_index].place(group, f"title-{row_index}", margin, cursor, content_width, title_height)
        top = cursor + title_height + (70 if oblique else 28)
        axis_top = row.axis_on_top and not oblique
        if axis_top:
            axis_y = top + s.label_size + 16
            frame_y = axis_y + 32
        else:
            frame_y = top + (0 if oblique else s.label_size + 12)
            axis_y = frame_y + f + (65 if oblique else 26)
        for i, name in enumerate(row.stimuli):
            x, y = x0 + i * dx, frame_y + i * dy
            panel = element(group, "g", id=f"panel-{row_index + 1}-{i + 1}")
            if oblique:
                sx = math.cos(math.radians(s.yaw))
                skew = -math.tan(math.radians(s.skew))
                panel.set("transform", f"translate({x + f/2} {y + f/2}) matrix({sx} {skew} 0 1 0 0) translate({-f/2} {-f/2})")
                panel.set("opacity", str(s.panel_opacity))
            else:
                panel.set("transform", f"translate({x} {y})")
            art, ref = artwork[name]
            art.place(panel, ref, 0, 0, f, f)
            label_y = y + f + s.label_size + 12 if axis_top else y - (f * math.tan(math.radians(s.skew))/2 + 12 if oblique else 12)
            text(group, f"Frame {i + 1}", x + f/2, label_y, s.label_size, s.font_family)
        start_x = x0 - gap/2
        end_x, end_y = start_x + n * dx, axis_y + n * dy
        axes.append((start_x, axis_y, end_x, end_y))
        line(group, start_x, axis_y, end_x + f * 0.4, end_y + (f * 0.4 * dy/dx), arrow=True)
        for i, ms in enumerate(config.times_ms):
            x, y = start_x + i * dx, axis_y + i * dy
            length = math.hypot(dx, dy)
            vx, vy = -dy/length, dx/length
            line(group, x - vx * 8, y - vy * 8, x + vx * 8, y + vy * 8)
            offset = -(s.label_size + 5) if axis_top else s.label_size + 18
            node = text(group, f"{ms:g} ms", x, y + offset, s.label_size, s.font_family)
            if oblique:
                angle = math.degrees(math.atan2(dy, dx))
                node.set("transform", f"rotate({angle} {x} {y + offset})")
        cursor = max(frame_y + (n - 1) * dy + f + (s.label_size + 12 if axis_top else 0),
                     end_y + f * 0.4 * dy/dx + 2 * s.label_size + 20) + s.row_gap
        if row_index == 0 and config.physical_series:
            series_y = cursor
            cursor += 2 * s.label_size + 76 + s.row_gap
    page_height = cursor - s.row_gap + margin
    min_x = 0
    if series_y is not None:
        left, right = draw_series(body, config, margin, series_y, content_width, axes)
        min_x = min(0, left - margin)
        page_width = max(page_width, right + margin) - min_x
    svg.set("width", f"{page_width:.2f}")
    svg.set("height", f"{page_height:.2f}")
    svg.set("viewBox", f"{min_x:.2f} 0 {page_width:.2f} {page_height:.2f}")
    background.set("x", str(min_x))
    background.set("width", str(page_width))
    background.set("height", f"{page_height:.2f}")
    ET.ElementTree(svg).write(target, encoding="utf-8", xml_declaration=True)


def draw_series(parent, config, x, y, width, axes):
    parent = element(parent, "g", id="physical-series")
    s = config.figure
    weights = [max(1, len(f"{value:g}") / 2) for value in config.physical_series]
    unit = width / sum(weights)
    if config.series_linked:
        anchor = config.physical_series.index(config.series_highlight)
        distance = axes[0][2] - axes[0][0]
        unit = distance / (sum(weights[anchor:-1]) + (weights[-1] - weights[anchor]) / 2)
        x = axes[0][0] - unit * (sum(weights[:anchor]) + weights[anchor] / 2)
        width = sum(weights) * unit
    left = x
    text(parent, config.series_label, x + width/2, y + s.label_size, s.label_size * 1.2, s.font_family, bold=True)
    top, height = y + 2 * s.label_size + 16, 44
    highlighted = False
    for value, weight in zip(config.physical_series, weights):
        w = unit * weight
        highlight = value == config.series_highlight and not highlighted
        element(parent, "rect", x=x, y=top, width=w, height=height,
                fill="#d6d6d6" if highlight else "white", stroke="#111111", stroke_width=1.5)
        text(parent, f"{value:g}", x + w/2, top + height/2 + s.label_size * 0.35,
             s.label_size, s.font_family, bold=highlight)
        highlighted = highlighted or highlight
        x += w
    if config.series_linked:
        scale = 0.25 if s.layout == "3d" else 0.5
        anchor_x = axes[0][0]
        line(parent, anchor_x, top, anchor_x, top + scale * (axes[0][1] - top), arrow=True)
        line(parent, anchor_x, top + height, anchor_x,
             top + height + scale * (axes[1][1] - top - height), arrow=True)
    return left, x
