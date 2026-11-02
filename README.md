# AGTAAM Open

> The open-source building blocks of **A-GTAAM Terrain Studio**: reusable functions for DEM and GIS desktop apps.

[![tests](https://github.com/AsifMarwat/agtaam-open/actions/workflows/tests.yml/badge.svg)](https://github.com/AsifMarwat/agtaam-open/actions)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)

## Modules
| Module | What it gives you | Status |
|---|---|---|
| [`agtaam_project`](agtaam_project) | **Project handling: New, Open, Save, Save As**, unsaved-changes tracking | available |

More A-GTAAM functions will be added here as separate modules. Each one stays independent, so you only take what you need.

---

## agtaam_project: project handling for DEM and GIS apps
**New, Open, Save, Save As.**
Pure Python with no dependencies, and an optional PyQt6 helper that adds the menu actions and
the familiar "Save changes?" question.

Born inside **A-GTAAM Terrain Studio** (a DEM analysis and editing app). Extracted so any
other app can have professional project handling without building it from scratch.

---

## Why
Desktop GIS tools (ArcMap, QGIS, ArcGIS Pro) share one idea: your work is a **project** you
can save and reopen. This library gives your app that idea in about 250 lines:

- A project **remembers where your data files are** and how you were viewing them. It does not copy your DEM.
- It knows when there is **unsaved work** and protects you from losing it.
- It survives real life: moved folders, deleted files, corrupt files, crashes mid-save.

## Features
| | |
|---|---|
| **New** | Empty project, with a "Save changes?" prompt first (Qt helper). |
| **Save / Save As** | One JSON file (`.agtaam`). Save over the current file, or choose a new name. |
| **Open** | Restores layers, visibility, opacity, stacking order and your own window state. |
| **Unsaved tracking** | `is_dirty()`, and `Name*` in the window title (Qt helper). |
| **Tool results** | Slope, hillshade, contours... stored in a `<project>_data` folder beside the project. |
| **Missing files** | Listed after opening; the project still opens with the layers that were found. |
| **Moved project** | Paths are stored relative as well as absolute, so a moved folder still works. |
| **Crash-safe** | The file is written completely, then swapped in. A crash never leaves half a file. |
| **Bad files refused** | A corrupt or foreign file raises a clear error and leaves your open project untouched. |
| **Backwards compatible** | Older `.json` projects still open. |

## Install
```bash
pip install git+https://github.com/AsifMarwat/agtaam-open.git          # core
pip install "agtaam-project[qt] @ git+https://github.com/AsifMarwat/agtaam-open.git"   # + PyQt6 helper
```
Or copy the `agtaam_project/` folder into your project. Requires Python 3.9+.

## Quick start (no window needed)
```python
from agtaam_project import ProjectManager, Layer

pm = ProjectManager()
dem = pm.add_layer(Layer("My DEM", source=r"C:\data\dem.tif"))   # a reference to the file
print(pm.is_dirty())                                            # True - unsaved

pm.save_as(r"C:\work\mine", gui={"zoom": 3}, name="mine")        # writes mine.agtaam
print(pm.is_dirty())                                            # False

pm2 = ProjectManager()
info = pm2.open(r"C:\work\mine.agtaam")
print(info["missing_layers"], info["gui"])                      # [] {'zoom': 3}
for layer in pm2.layers:                                        # top layer first
    ...                                                         # load layer.source in your app
```
Run `python examples/console_demo.py` to see the whole cycle, or `python examples/qt_demo.py`
for a tiny window.

### Saving tool results
Results made by your tools (slope, hillshade...) have no file of their own yet. Give the
manager a writer; it calls it on every save and stores the files in `<project>_data/`:
```python
def write_result(layer, folder):                 # your app writes the data
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{layer.id}.tif"
    ...                                          # write the GeoTIFF / GeoJSON here
    return str(path)                             # return None if it could not be written

pm = ProjectManager(derived_writer=write_result)
pm.add_layer(Layer("dem - slope", derived_from=dem.id, tool="slope"))
```
Without a writer, such layers are reported in `skipped_layers`, never lost silently.

## PyQt6 window helper
```python
from agtaam_project.qt import ProjectWindowMixin

class MainWindow(ProjectWindowMixin, QMainWindow):
    APP_NAME = "My DEM App"
    def __init__(self):
        super().__init__()
        ...                                      # build your window
        self.project = ProjectManager(derived_writer=write_result)
        self._init_project_actions()             # Ctrl+N / O / S / Shift+S, title, close prompt

    def collect_gui_state(self):  return {"zoom": self.canvas.zoom}
    def clear_workspace(self):    ...            # remove all layers from the screen
    def rebuild_from_project(self, layers, gui, missing):
        for layer in reversed(layers):           # bottom layer first
            ...                                  # load layer.source, then apply `gui`
```
Connect your buttons to `act_new_project`, `act_open_project`, `act_save_project`,
`act_save_project_as`, and call `self.mark_dirty()` whenever the user changes something.

## API at a glance
| Call | Returns |
|---|---|
| `ProjectManager(derived_writer=None)` | the manager (one per app) |
| `.new(name)` | project info |
| `.save(path=None, gui=None, name=None)` | info + `saved_layers`, `skipped_layers` |
| `.save_as(path, gui=None, name=None)` | same |
| `.open(path)` | info + `missing_layers`, `gui`; fills `.layers` |
| `.add_layer(Layer)` `.remove_layer(id)` `.update_layer(id, **fields)` `.reorder(ids)` | layer editing |
| `.is_dirty()` `.touch()` | unsaved tracking |

Errors: `ProjectError` (base), `NoPathError` (Save before Save As), `ProjectFileError` (bad file).

## File format
`.agtaam` is plain JSON, so it is easy to inspect and to read from other languages:
```json
{
  "format": "A-GTAAM-project", "version": 2, "name": "mine",
  "gui": {"zoom": 3},
  "layers": [
    {"id": "ab12cd34", "name": "My DEM", "kind": "raster",
     "source": "C:/data/dem.tif", "source_rel": "../data/dem.tif",
     "visible": true, "opacity": 1.0, "derived_from": null, "tool": null, "meta": {}}
  ]
}
```
Layers are stored bottom first. The format is shared with the A-GTAAM backend, so projects
are interchangeable.

## Development
```bash
pip install -e ".[dev]"
python -m pytest
```
Continuous integration runs the tests on Windows and Linux (Python 3.9 / 3.11 / 3.13).
The PyQt6 helper has been tried by hand in a demo window; its logic is not covered by automatic tests yet.

## Contributing
Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License
[MIT](LICENSE) © 2026 Muhammad Asif
