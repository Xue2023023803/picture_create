"""A single entry point for assets, titles and complete procedure figures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

from . import __version__
from .assets import Artwork, convert_source, export_svg, find_tool
from .config import load_config, snapshot


def preflight(config, assets_only=False):
    from matplotlib.colors import to_rgba
    from .render import check_font
    if config.rows and not assets_only:
        check_font(config.figure.font_family)
        if set(config.figure_formats) - {"svg"}:
            find_tool("inkscape")
    for item in config.stimuli:
        if item.style:
            to_rgba(item.style.cross_color)
        elif item.source.suffix.lower() == ".svg":
            Artwork(item.source, "check-")
        if item.source:
            if item.source.suffix.lower() != ".svg" or set(config.asset_formats) - {"svg"}:
                find_tool("inkscape")
            if item.source.suffix.lower() == ".eps":
                find_tool("gs")


def generate(config, assets_only=False):
    # Complete config and dependency checks before making any output directory.
    preflight(config, assets_only)
    from .render import draw_stimulus, draw_title
    from .compose import compose
    root = config.output_dir
    asset_dir = root / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    assets = {}
    for item in config.stimuli:
        target = asset_dir / item.id
        if item.source:
            svg = convert_source(item.source, target.with_suffix(".svg"))
            for fmt in config.asset_formats:
                if fmt != "svg":
                    export_svg(svg, target.with_suffix(f".{fmt}"), fmt)
        else:
            svg = draw_stimulus(item.style, item.seed, target, config.asset_formats)
        assets[item.id] = svg
    results = []
    if config.rows and not assets_only:
        title_dir = root / "titles"
        title_dir.mkdir(exist_ok=True)
        titles = [draw_title(row.title, title_dir / f"title_{i+1:02d}", config.figure.font_family,
                             config.figure.title_size, config.asset_formats) for i, row in enumerate(config.rows)]
        svg = root / f"procedure_{config.figure.layout}.svg"
        compose(config, assets, titles, svg)
        results.append(svg)
        for fmt in config.figure_formats:
            if fmt != "svg":
                target = svg.with_suffix(f".{fmt}")
                export_svg(svg, target, fmt)
                results.append(target)
    record = snapshot(config)
    record["output_dir"] = str(root)
    for entry in record.get("stimuli", []):
        if "source" in entry:
            entry["source"] = str((config.path.parent / Path(entry["source"]).expanduser()).resolve())
    (root / "config_used.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(assets)} stimulus asset(s): {asset_dir}")
    for path in results:
        print(f"Figure: {path}")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate static dot-stimulus illustrations and procedure figures.")
    parser.add_argument("--version", action="version", version=f"stimulus-figures {__version__}")
    parser.add_argument("--config", type=Path, required=True, help="JSON configuration file")
    parser.add_argument("--output", type=Path, help="Output directory (relative to current working directory)")
    parser.add_argument("--layout", choices=("horizontal", "3d"), help="Override figure layout")
    parser.add_argument("--formats", help="Final figure formats, comma-separated: svg,pdf,png")
    parser.add_argument("--assets-only", action="store_true", help="Generate stimuli without titles or an assembled figure")
    parser.add_argument("--check", action="store_true", help="Validate configuration and required tools without generating artwork")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config, args.output, args.layout,
                             [x.strip() for x in args.formats.split(",")] if args.formats is not None else None)
        if args.check:
            preflight(config, args.assets_only)
            print(f"Configuration OK: {len(config.stimuli)} stimulus asset(s), {len(config.rows)} row(s)")
            print(f"Output: {config.output_dir}")
        else:
            generate(config, args.assets_only)
    except (OSError, ValueError, TypeError, ET.ParseError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0
