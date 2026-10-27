"""Regression checks for portability, deterministic drawing and SVG assembly."""
import contextlib
import io
import json
import math
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from stimulus_figures.assets import Artwork, SVG
from stimulus_figures.cli import generate, main
from stimulus_figures.config import load_config, stable_seed, style_from
from stimulus_figures.render import draw_stimulus, points_for

ROOT = Path(__file__).resolve().parents[1]


class FigureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def config(self, **updates):
        data = {"output_dir": "out", "asset_formats": ["svg"], "stimuli": [{"id": "dots"}]}
        data.update(updates)
        path = self.root / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_paths_and_expanded_names(self):
        config = load_config(self.config(stimuli=[{"id": "dots", "count": 2}]))
        self.assertEqual(config.output_dir, self.root / "out")
        self.assertEqual([s.id for s in config.stimuli], ["dots_01", "dots_02"])
        self.assertFalse(config.output_dir.exists())
        self.assertEqual(config.stimuli[1].seed, stable_seed(1, "dots_02"))

    def test_invalid_configuration_creates_no_output(self):
        cases = [
            {"stimuli": [{"id": "../escape"}]},
            {"stimuli": [{"id": "x"}, {"id": "X"}]},
            {"stimuli": [{"id": "dots", "n_pairs": -1}]},
            {"stimuli": [{"id": "dots", "dot_mode": "isolated", "n_dots": 512}]},
            {"stimuli": [{"id": "dots", "dot_radiuss": 5}]},
            {"rows": [{"title": "Test", "stimuli": ["unknown"]}], "times_ms": [0, 300]},
            {"rows": [{"title": "Test", "stimuli": ["dots"]}], "times_ms": [300, 0]},
            {"rows": [{"title": "Test", "stimuli": ["dots"]}], "times_ms": [0]},
            {"figure": {"step_x": 0}},
            {"figure_formats": []},
            {"series_linked": True},
        ]
        for values in cases:
            with self.subTest(values=values), self.assertRaises(ValueError):
                load_config(self.config(**values))
            self.assertFalse((self.root / "out").exists())

    def test_dots_match_requested_counts_bounds_and_gap(self):
        for kind, expected in (("isolated", 16), ("connected", 8)):
            style = style_from({"dot_mode": kind})
            points, links, _ = points_for(style, 10)
            self.assertEqual(len(points), expected)
            self.assertEqual(len(links), 4 if kind == "connected" else 0)
            lower = (style.canvas_size - style.inner_size) / 2 + style.inner_margin + style.dot_radius
            for p in points:
                self.assertTrue(all(lower <= x <= style.canvas_size - lower for x in p))
            for i, p in enumerate(points):
                for q in points[i+1:]:
                    self.assertGreaterEqual(math.dist(p, q), 2 * style.dot_radius + style.min_gap - 1e-9)

    def test_all_modes_have_same_canvas_and_svg_is_repeatable(self):
        boxes = []
        for mode in (1, 2, 3):
            style = style_from({"mode": mode})
            path = draw_stimulus(style, 1, self.root / f"mode{mode}", ["svg"])
            first = path.read_bytes()
            draw_stimulus(style, 1, self.root / f"mode{mode}", ["svg"])
            self.assertEqual(path.read_bytes(), first)
            boxes.append(ET.parse(path).getroot().get("viewBox"))
        self.assertEqual(len(set(boxes)), 1)

    def test_both_procedure_layouts_have_valid_unique_references(self):
        for layout in ("horizontal", "3d"):
            config = load_config(ROOT / "examples/demo.json", self.root / layout, layout)
            config.asset_formats = ["svg"]
            with contextlib.redirect_stdout(io.StringIO()):
                results = generate(config)
            root = ET.parse(results[0]).getroot()
            ids = [e.get("id") for e in root.iter() if e.get("id")]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(sum(i.startswith("panel-") for i in ids), 12)
            bar = next(e for e in root.iter() if e.get("id") == "physical-series")
            highlight = next(e for e in bar if e.get("fill") == "#d6d6d6")
            first_row = next(e for e in root.iter() if e.get("id") == "row-1")
            timeline = next(e for e in first_row if e.tag == f"{{{SVG}}}line")
            self.assertAlmostEqual(float(highlight.get("x")) + float(highlight.get("width"))/2,
                                   float(timeline.get("x1")))
            for e in root.iter():
                for key, value in e.attrib.items():
                    if key.endswith("href") and value.startswith("#"):
                        self.assertIn(value[1:], ids)
                    for ref in re.findall(r"url\(#([^)]*)\)", value):
                        self.assertIn(ref, ids)
            self.assertTrue((config.output_dir / "config_used.json").is_file())
            self.assertEqual(len(list((config.output_dir / "titles").glob("*.svg"))), 2)

    def test_missing_export_tool_does_not_create_output(self):
        config = load_config(ROOT / "examples/demo.json", self.root / "out", figure_formats=["pdf"])
        with patch("stimulus_figures.cli.find_tool", side_effect=ValueError("Missing inkscape")):
            with self.assertRaisesRegex(ValueError, "Missing inkscape"):
                generate(config)
        self.assertFalse(config.output_dir.exists())

    def test_native_svg_needs_no_external_tools_and_check_writes_no_artwork(self):
        config = self.config(rows=[{"title": "Test", "stimuli": ["dots"]}], times_ms=[0, 300])
        with patch("stimulus_figures.cli.find_tool", side_effect=AssertionError("Unexpected external tool")):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--config", str(config), "--check"]), 0)
                self.assertFalse((self.root / "out").exists())
                self.assertEqual(main(["--config", str(config)]), 0)

    def test_manual_svg_and_repeated_use(self):
        config = load_config(ROOT / "examples/external_svg.json", self.root / "out")
        with contextlib.redirect_stdout(io.StringIO()):
            generate(config)
        self.assertEqual((config.output_dir / "assets/selected.svg").read_bytes(), (ROOT / "examples/sample.svg").read_bytes())
        self.assertTrue((config.output_dir / "procedure_horizontal.svg").exists())

    def test_external_links_and_overlapping_input_output_are_rejected(self):
        source = self.root / "source.svg"
        source.write_text(f'<svg xmlns="{SVG}" viewBox="0 0 100 100"><image href="missing.png"/></svg>')
        with self.assertRaisesRegex(ValueError, "External SVG"):
            Artwork(source, "x-")
        path = self.config(output_dir=".", stimuli=[{"id": "art", "source": "source.svg"}])
        with self.assertRaisesRegex(ValueError, "overwriting inputs"):
            load_config(path)


if __name__ == "__main__":
    unittest.main()
