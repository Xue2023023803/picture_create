"""Configuration loading and validation, with no rendering side effects."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import copy
import hashlib
import json
import math
from pathlib import Path
import re


@dataclass(frozen=True)
class StimulusStyle:
    mode: int = 2
    dot_mode: str = "connected"
    n_dots: int = 16
    n_pairs: int = 4
    dot_radius: float = 14
    dot_color: str = "white"
    min_gap: float = 4
    pair_distance_factor: float = 4
    link_width: float = 6
    inner_size: float = 380
    inner_margin: float = 10
    patch_size: float = 90
    patch_gap: float = 30
    outer_pad: float = 20
    patch_side: str = "random"
    patch_pattern: int = 3
    patch_diagonal: str = "main"
    background_gray: float = 0.7
    cross_color: str = "#c70000"
    cross_width: float = 6
    border_width: float = 0

    @property
    def canvas_size(self):
        # Reserve the same space for a patch even in modes 2 and 3.
        return self.inner_size + 2 * (self.patch_gap + self.patch_size + self.outer_pad)


@dataclass(frozen=True)
class FigureStyle:
    layout: str = "horizontal"
    frame_size: float = 220
    frame_gap: float = 18
    row_gap: float = 80
    margin: float = 48
    title_size: float = 28
    label_size: float = 18
    font_family: str = "DejaVu Sans"
    panel_opacity: float = 0.75
    step_x: float = 0.85
    step_y: float = 0.22
    yaw: float = 30
    skew: float = 12


@dataclass(frozen=True)
class Stimulus:
    id: str
    seed: int
    style: StimulusStyle | None = None
    source: Path | None = None


@dataclass(frozen=True)
class Row:
    title: str
    stimuli: tuple[str, ...]
    axis_on_top: bool = False


@dataclass
class Config:
    path: Path
    output_dir: Path
    stimuli: list[Stimulus]
    rows: list[Row]
    figure: FigureStyle
    times_ms: list[float]
    physical_series: list[float]
    series_label: str
    series_highlight: float | None
    series_linked: bool
    asset_formats: list[str]
    figure_formats: list[str]
    raw: dict


def object_only(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def known_keys(value, allowed, label):
    object_only(value, label)
    unknown = set(value) - set(allowed)
    if unknown:
        raise ValueError(f"Unknown {label} option(s): {', '.join(sorted(unknown))}")


def number(value, label, minimum=0, positive=False, integer=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < minimum
            or (positive and value <= 0) or (integer and not isinstance(value, int))):
        raise ValueError(f"Invalid {label}: {value!r}")


def style_from(values):
    known_keys(values, {f.name for f in fields(StimulusStyle)}, "stimulus")
    s = StimulusStyle(**values)
    for name in ("mode", "n_dots", "n_pairs", "patch_pattern"):
        number(getattr(s, name), name, integer=True)
    if s.mode not in (1, 2, 3) or s.patch_pattern not in range(4):
        raise ValueError("mode must be 1/2/3; patch_pattern must be 0/1/2/3")
    for name, choices in {
        "dot_mode": ("isolated", "connected"), "dot_color": ("black", "white"),
        "patch_side": ("left", "right", "random"), "patch_diagonal": ("main", "anti"),
    }.items():
        if getattr(s, name) not in choices:
            raise ValueError(f"{name} must be one of {choices}")
    for name in ("dot_radius", "inner_size", "patch_size", "pair_distance_factor", "link_width"):
        number(getattr(s, name), name, positive=True)
    for name in ("min_gap", "inner_margin", "patch_gap", "outer_pad", "cross_width", "border_width", "background_gray"):
        number(getattr(s, name), name)
    if s.background_gray > 1:
        raise ValueError("background_gray must be between 0 and 1")
    if not isinstance(s.cross_color, str) or not s.cross_color:
        raise ValueError("cross_color must be a color string")
    if s.patch_size > s.canvas_size - 2 * s.outer_pad:
        raise ValueError("patch_size does not fit the canvas")
    if s.mode != 3:
        side = s.inner_size - 2 * s.inner_margin
        if side <= 2 * s.dot_radius:
            raise ValueError("Dots do not fit inside inner_size / inner_margin")
        count = s.n_dots if s.dot_mode == "isolated" else 2 * s.n_pairs
        if count * math.pi * s.dot_radius ** 2 > side ** 2:
            raise ValueError("Dot area exceeds available area; reduce count/radius or enlarge inner_size")
        if s.dot_mode == "connected" and s.n_pairs:
            distance = s.pair_distance_factor * s.dot_radius
            if distance < 2 * s.dot_radius + s.min_gap:
                raise ValueError("Connected dots overlap or violate min_gap")
            if distance > math.sqrt(2) * (side - 2 * s.dot_radius):
                raise ValueError("Connected pair is too long to fit inside the inner box")
    return s


def formats(value, label, allowed):
    if not isinstance(value, list) or not value or any(not isinstance(x, str) or x not in allowed for x in value):
        raise ValueError(f"{label} must be a nonempty list drawn from {sorted(allowed)}")
    return list(dict.fromkeys(value))


def stable_seed(seed, name):
    digest = hashlib.sha256(f"{seed}:{name}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def load_config(path, output_dir=None, layout=None, figure_formats=None):
    path = Path(path).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    known_keys(raw, {"version", "seed", "output_dir", "stimulus_defaults", "stimuli", "rows", "figure",
                     "times_ms", "physical_series", "series_label", "series_highlight", "series_linked", "asset_formats", "figure_formats"}, "config")
    if raw.get("version", 1) != 1:
        raise ValueError("Only config version 1 is supported")
    master_seed = raw.get("seed", 1)
    number(master_seed, "seed", integer=True)
    output_value = output_dir if output_dir is not None else raw.get("output_dir", "output")
    if not isinstance(output_value, (str, Path)) or not str(output_value).strip():
        raise ValueError("output_dir must be a nonempty path")
    output = Path(output_value).expanduser()
    # CLI paths are relative to cwd; paths in a JSON file are relative to that file.
    output = output.resolve() if output_dir is not None else (path.parent / output).resolve()
    defaults = raw.get("stimulus_defaults", {})
    style_from(defaults)
    entries = raw.get("stimuli", [])
    if not isinstance(entries, list) or not entries:
        raise ValueError("stimuli must be a nonempty list")
    stimuli = []
    ids = set()
    for entry in entries:
        known_keys(entry, {"id", "seed", "count", "source"} | {f.name for f in fields(StimulusStyle)}, "stimuli entry")
        name = entry.get("id", "")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", name):
            raise ValueError("Stimulus id must start with a letter and use only letters, digits, _ or -")
        count = entry.get("count", 1)
        number(count, "count", positive=True, integer=True)
        seed = entry.get("seed", master_seed)
        number(seed, "seed", integer=True)
        overrides = {k: v for k, v in entry.items() if k not in {"id", "seed", "count", "source"}}
        source = None
        if "source" in entry:
            if overrides or count != 1:
                raise ValueError("External source cannot be combined with drawing options or count > 1")
            if not isinstance(entry["source"], str) or not entry["source"].strip():
                raise ValueError("source must be a nonempty path")
            source = (path.parent / Path(entry["source"]).expanduser()).resolve()
            if not source.is_file() or source.suffix.lower() not in {".svg", ".eps", ".pdf"}:
                raise ValueError(f"Missing or unsupported source (SVG/EPS/PDF required): {source}")
            if source.is_relative_to(output):
                raise ValueError("Keep source artwork outside output_dir to prevent overwriting inputs")
        style = None if source else style_from({**defaults, **overrides})
        for i in range(count):
            item_id = name if count == 1 else f"{name}_{i + 1:02d}"
            if item_id.casefold() in ids:
                raise ValueError(f"Duplicate stimulus id: {item_id}")
            ids.add(item_id.casefold())
            stimuli.append(Stimulus(item_id, stable_seed(seed, item_id), style, source))
    ids = {s.id for s in stimuli}
    rows = []
    row_values = raw.get("rows", [])
    if not isinstance(row_values, list):
        raise ValueError("rows must be a list")
    for entry in row_values:
        known_keys(entry, {"title", "stimuli", "axis_on_top"}, "row")
        names = entry.get("stimuli")
        if not isinstance(names, list) or not names or any(not isinstance(n, str) or n not in ids for n in names):
            raise ValueError("Each row needs a nonempty stimuli list referencing existing ids")
        title = entry.get("title", "")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Each row needs a nonempty title")
        top = entry.get("axis_on_top", False)
        if not isinstance(top, bool):
            raise ValueError("axis_on_top must be true or false")
        rows.append(Row(title, tuple(names), top))
    if rows and any(len(r.stimuli) != len(rows[0].stimuli) for r in rows):
        raise ValueError("All rows must have the same number of frames")
    times = raw.get("times_ms", [])
    if not isinstance(times, list):
        raise ValueError("times_ms must be a list")
    for t in times:
        number(t, "times_ms")
    if rows and (len(times) != len(rows[0].stimuli) + 1 or any(b <= a for a, b in zip(times, times[1:]))):
        raise ValueError("times_ms must be strictly increasing with one more entry than frames per row")
    values = raw.get("figure", {})
    known_keys(values, {f.name for f in fields(FigureStyle)}, "figure")
    figure = FigureStyle(**{**values, **({"layout": layout} if layout else {})})
    if figure.layout not in {"horizontal", "3d"}:
        raise ValueError("figure.layout must be horizontal or 3d")
    for name in ("frame_size", "title_size", "label_size", "step_x"):
        number(getattr(figure, name), name, positive=True)
    for name in ("frame_gap", "row_gap", "margin", "step_y", "panel_opacity", "yaw", "skew"):
        number(getattr(figure, name), name)
    if figure.panel_opacity > 1 or figure.yaw >= 80 or figure.skew >= 45:
        raise ValueError("panel_opacity must be <= 1, yaw < 80 and skew < 45")
    if not isinstance(figure.font_family, str) or not figure.font_family.strip():
        raise ValueError("font_family must be a nonempty string")
    series = raw.get("physical_series", [])
    if not isinstance(series, list):
        raise ValueError("physical_series must be a list")
    for n in series:
        number(n, "physical_series")
    if series and len(rows) < 2:
        raise ValueError("physical_series needs at least two rows")
    highlight = raw.get("series_highlight")
    if highlight is not None:
        number(highlight, "series_highlight")
        if highlight not in series:
            raise ValueError("series_highlight must occur in physical_series")
    label = raw.get("series_label", "Physical numerosity series")
    if not isinstance(label, str):
        raise ValueError("series_label must be text")
    linked = raw.get("series_linked", False)
    if not isinstance(linked, bool):
        raise ValueError("series_linked must be true or false")
    if linked and (highlight is None or not series or series.index(highlight) == len(series) - 1):
        raise ValueError("series_linked requires series_highlight before the last series value")
    return Config(path, output, stimuli, rows, figure, times, series, label, highlight, linked,
                  formats(raw.get("asset_formats", ["svg", "eps"]), "asset_formats", {"svg", "eps", "pdf", "png"}),
                  formats(figure_formats if figure_formats is not None else raw.get("figure_formats", ["svg"]), "figure_formats", {"svg", "pdf", "png"}), raw)


def snapshot(config):
    """A small record for reusing the selected drawing settings, not a trial database."""
    return {**copy.deepcopy(config.raw), "figure": asdict(config.figure), "asset_formats": config.asset_formats,
            "figure_formats": config.figure_formats}
