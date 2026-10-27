"""Optional end-to-end checks requiring Inkscape and Ghostscript."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from xml.etree import ElementTree as ET

# Works both from a checkout and after pip install -e .
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stimulus_figures.cli import generate
from stimulus_figures.config import load_config
from stimulus_figures.assets import convert_source, viewbox
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="stimulus-converters-") as folder:
        temp = Path(folder)
        for layout in ("horizontal", "3d"):
            config = load_config(root / "examples/demo.json", temp / layout, layout, ["svg", "pdf", "png"])
            with contextlib.redirect_stdout(io.StringIO()):
                generate(config)
            stem = config.output_dir / f"procedure_{layout}"
            assert stem.with_suffix(".pdf").read_bytes().startswith(b"%PDF-")
            assert stem.with_suffix(".png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        source = temp / "horizontal/assets/connected_01.eps"
        config_path = temp / "external.json"
        config_path.write_text(json.dumps({
            "output_dir": "imported", "asset_formats": ["svg"],
            "stimuli": [{"id": "eps_source", "source": str(source)}],
            "rows": [{"title": "Imported EPS", "stimuli": ["eps_source"]}],
            "times_ms": [0, 300], "figure_formats": ["svg", "pdf", "png"]
        }), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            generate(load_config(config_path))
        assert (temp / "imported/procedure_horizontal.pdf").stat().st_size > 100
        # Also read a PDF source through the same interface.
        data = json.loads(config_path.read_text())
        data["output_dir"] = "imported_pdf"
        data["stimuli"][0]["source"] = str(temp / "imported/procedure_horizontal.pdf")
        config_path.write_text(json.dumps(data), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            generate(load_config(config_path))
        # Distinct page sizes catch importing the wrong page or a combined canvas.
        multipage = temp / "multipage.pdf"
        with PdfPages(multipage) as document:
            for size in ((2, 1), (1, 2)):
                figure = Figure(figsize=size)
                figure.add_subplot().plot([0, 1], [0, 1])
                document.savefig(figure)
        first_page = convert_source(multipage, temp / "first_page.svg")
        _, _, width, height = viewbox(ET.parse(first_page).getroot())
        assert abs(width / height - 2) < 1e-6, "PDF import must retain page 1 dimensions"
    print("PASS: horizontal/3d SVG→PDF/PNG, EPS→SVG→figure, PDF→SVG→figure, multipage PDF page 1")


if __name__ == "__main__":
    main()
