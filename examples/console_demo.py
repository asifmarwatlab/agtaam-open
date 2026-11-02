"""Runs without any window:  python examples/console_demo.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # run without installing

from agtaam_project import Layer, ProjectManager


def write_result(layer, folder: Path):
    """Your app's job: save one tool result (slope, hillshade ...) and return its file path."""
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{layer.id}.tif"
    out.write_bytes(b"pretend this is a GeoTIFF")          # replace with your real writer
    return str(out)


work = Path(tempfile.mkdtemp())
dem = work / "dem.tif"
dem.write_bytes(b"pretend DEM")

pm = ProjectManager(derived_writer=write_result)
dem_layer = pm.add_layer(Layer("My DEM", source=str(dem)))
pm.add_layer(Layer("My DEM - slope", derived_from=dem_layer.id, tool="slope"))
print("unsaved?", pm.is_dirty())

print(pm.save_as(str(work / "demo"), gui={"zoom": 2.5}, name="demo"))
print("unsaved?", pm.is_dirty())

fresh = ProjectManager()
info = fresh.open(str(work / "demo.agtaam"))
print(info["name"], [l.name for l in fresh.layers], "missing:", info["missing_layers"], "gui:", info["gui"])
