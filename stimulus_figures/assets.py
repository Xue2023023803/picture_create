"""SVG embedding and optional conversion of existing EPS/PDF artwork."""
from __future__ import annotations

import copy
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from xml.etree import ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG)
ET.register_namespace("xlink", XLINK)


def element(parent, tag, **attrs):
    return ET.SubElement(parent, f"{{{SVG}}}{tag}", {k.replace("_", "-"): str(v) for k, v in attrs.items()})


def find_tool(name):
    path = shutil.which(name)
    if not path and name == "inkscape":
        candidate = Path("/Applications/Inkscape.app/Contents/MacOS/inkscape")
        if candidate.is_file():
            path = str(candidate)
    if not path:
        raise ValueError(f"Missing {name}: install it and make it available on PATH. Native SVG generation does not need it.")
    return path


def run(command):
    try:
        subprocess.run([str(c) for c in command], check=True, capture_output=True, text=True, timeout=120)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or f"process exited with code {exc.returncode}"
        raise ValueError(f"{Path(str(command[0])).name} conversion failed: {detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Conversion timed out after 120 seconds") from exc


def convert_source(source, target):
    if source.suffix.lower() == ".svg":
        # Validate XML before copying it into the output directory.
        viewbox(ET.parse(source).getroot())
        shutil.copyfile(source, target)
        return target
    inkscape = find_tool("inkscape")
    with tempfile.TemporaryDirectory(prefix="stimulus-figure-") as temp:
        pdf = source
        if source.suffix.lower() == ".eps":
            pdf = Path(temp) / "source.pdf"
            run([find_tool("gs"), "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pdfwrite", "-dEPSCrop", f"-sOutputFile={pdf}", source])
        run([inkscape, pdf, "--pages=1", "--pdf-poppler", "--export-type=svg", "--export-plain-svg", f"--export-filename={target}"])
    return target


def export_svg(source, target, fmt):
    args = [find_tool("inkscape"), source, f"--export-type={fmt}", f"--export-filename={target}"]
    if fmt == "png":
        args += ["--export-dpi=150", "--export-background=white", "--export-background-opacity=1"]
    elif fmt in {"pdf", "eps"}:
        args += ["--export-text-to-path"]
    run(args)
    if not target.is_file() or not target.stat().st_size:
        raise ValueError(f"Converter did not produce {target}")


def viewbox(root):
    if root.tag != f"{{{SVG}}}svg":
        raise ValueError("Artwork must have an SVG root element")
    raw = root.get("viewBox")
    if raw:
        result = tuple(float(x) for x in re.split(r"[\s,]+", raw.strip()))
    else:
        # SVG supports absolute lengths; convert them to CSS pixels.
        def length(value):
            match = re.fullmatch(r"([0-9.]+)(px|pt|in|cm|mm)?", value or "")
            if not match:
                raise ValueError("SVG requires a viewBox or absolute width and height")
            return float(match[1]) * {None: 1, "px": 1, "pt": 96/72, "in": 96, "cm": 96/2.54, "mm": 96/25.4}[match[2]]
        result = (0, 0, length(root.get("width")), length(root.get("height")))
    import math
    if len(result) != 4 or not all(math.isfinite(n) for n in result) or min(result[2:]) <= 0:
        raise ValueError("SVG viewBox must have positive finite dimensions")
    return result


class Artwork:
    def __init__(self, path, prefix):
        root = ET.parse(path).getroot()
        self.box = viewbox(root)
        self.group = ET.Element(f"{{{SVG}}}g")
        # Preserve root-level styles and transformations in an inner group.
        for key, value in root.attrib.items():
            if key not in {"width", "height", "viewBox", "version", "id", "x", "y"}:
                self.group.set(key, value)
        for child in root:
            self.group.append(copy.deepcopy(child))
        ids = {e.get("id"): prefix + e.get("id") for e in self.group.iter() if e.get("id")}
        def urls(value):
            return re.sub(r"url\(\s*['\"]?#([^)'\"\s]+)['\"]?\s*\)",
                          lambda m: f"url(#{ids.get(m[1], m[1])})", value)
        for e in self.group.iter():
            if e.tag in {f"{{{SVG}}}script", f"{{{SVG}}}foreignObject"}:
                raise ValueError("External SVG must be static vector artwork without scripts or foreignObject")
            if e.get("id"):
                e.set("id", ids[e.get("id")])
            for key, value in list(e.attrib.items()):
                if key.lower().startswith("on"):
                    raise ValueError("SVG event handlers are unsupported")
                value = urls(value)
                if key in {"href", f"{{{XLINK}}}href"} and value.startswith("#"):
                    value = "#" + ids.get(value[1:], value[1:])
                elif key in {"href", f"{{{XLINK}}}href"} and not value.startswith("data:"):
                    raise ValueError("External SVG links/images are unsupported; embed images and convert text to paths first")
                e.set(key, value)
            if e.tag == f"{{{SVG}}}style" and e.text:
                e.text = urls(e.text)
                for old, new in ids.items():
                    e.text = re.sub(r"#" + re.escape(old) + r"(?![\w-])", "#" + new, e.text)

    def define(self, defs, name):
        group = element(defs, "g", id=name)
        group.append(self.group)

    def place(self, parent, name, x, y, width, height):
        bx, by, bw, bh = self.box
        scale = min(width / bw, height / bh)
        tx, ty = x + (width - bw * scale) / 2, y + (height - bh * scale) / 2
        use = element(parent, "use", href=f"#{name}", transform=f"translate({tx} {ty}) scale({scale}) translate({-bx} {-by})")
        use.set(f"{{{XLINK}}}href", f"#{name}")
