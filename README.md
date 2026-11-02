# agtaam-project

**New Project, Open Project, Save and Save As** for a DEM / GIS desktop app.
Plain Python, no backend, no web server, no GIS libraries. An optional PyQt6 part adds the
menu actions and the "Save changes?" question.

Made for the A-GTAAM Terrain Studio. Project files (`.agtaam`) are interchangeable with
the A-GTAAM backend's projects.

## What it does (plain words)
A project is like an ArcMap map document. It does **not** copy your DEM; it remembers
*where* each layer's file is, plus how you were looking at it.

| Function | What happens |
|---|---|
| **New** | Clears everything and starts an empty "Untitled" project. |
| **Save** | Overwrites the project file. The first time it asks where (acts like Save As). |
| **Save As** | Always asks for a new name or place; keeps the old file untouched. |
| **Open** | Brings back the layer list, visibility, opacity, order and your window state (zoom, colour ramp ...). Missing files are listed, the project still opens. |
| Unsaved marker | `Name*` in the title while there are unsaved changes; "Save changes?" before New / Open / closing. |

Safe by design: the file is written completely and then swapped in (a crash never leaves a
half-written project); a corrupt file is refused without touching your current work; a moved
project folder still finds its data (paths are stored relative as well).

## Install
```
pip install .            # core only (pure Python)
pip install ".[qt]"      # + the PyQt6 part
```
or just copy the `agtaam_project/` folder into your project.

## Use it without any window
```python
from agtaam_project import ProjectManager, Layer

pm = ProjectManager()
dem = pm.add_layer(Layer("My DEM", source=r"C:\data\dem.tif"))
pm.save_as(r"C:\work\mine", gui={"zoom": 3}, name="mine")   # -> mine.agtaam

pm2 = ProjectManager()
info = pm2.open(r"C:\work\mine.agtaam")
info["missing_layers"], info["gui"], pm2.layers              # load each layer from layer.source
```
`python examples/console_demo.py` shows the whole cycle.

### Tool results (slope, hillshade, contours ...)
These have no file of their own. Give the manager a writer and they are saved in a
`<project>_data` folder next to the project (keep the two together):
```python
def write_result(layer, folder):          # your app saves layer's data into `folder`
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{layer.id}.tif"
    ...                                    # write the GeoTIFF / GeoJSON here
    return str(path)

pm = ProjectManager(derived_writer=write_result)
pm.add_layer(Layer("dem - slope", derived_from=dem.id, tool="slope"))
```
Without a writer these layers are reported in `skipped_layers` (never silently lost).

## Use it in a PyQt6 window
```python
from agtaam_project import ProjectManager
from agtaam_project.qt import ProjectWindowMixin

class MainWindow(ProjectWindowMixin, QMainWindow):
    APP_NAME = "My DEM App"
    def __init__(self):
        super().__init__()
        ...build your window...
        self.project = ProjectManager(derived_writer=write_result)
        self._init_project_actions()          # shortcuts: Ctrl+N / O / S / Shift+S

    # three small hooks:
    def collect_gui_state(self): return {"zoom": self.canvas.zoom}
    def clear_workspace(self):   self.remove_all_layers_from_screen()
    def rebuild_from_project(self, layers, gui, missing):
        for layer in reversed(layers):        # bottom layer first
            self.load_into_window(layer.source, layer)
        self.canvas.zoom = gui.get("zoom", 1)
```
Connect your menu buttons to `act_new_project`, `act_open_project`, `act_save_project`,
`act_save_project_as`, and call `self.mark_dirty()` whenever the user changes something.
Adding a layer yourself? Call `self.project.add_layer(Layer(...))` and then `mark_dirty()`.

## Tests
```
pip install ".[dev]"
python -m pytest
```
