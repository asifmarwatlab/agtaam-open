"""The project itself: a list of layers plus a few settings, saved to one file.

No Qt, no web server, no GIS libraries: just the standard library.

Plain-words picture
-------------------
A project is like a map document. It does NOT contain the DEM data; it remembers
*where* each layer's file is, plus how you were looking at it (visible, opacity, order,
zoom ...). Results created by tools (slope, hillshade ...) have no file of their own yet,
so the host app gives us a small "writer" function that saves them next to the project.
"""
from __future__ import annotations

import copy
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

FORMAT = "A-GTAAM-project"          # same format as the A-GTAAM app: files are interchangeable
FORMAT_VERSION = 2
EXT = ".agtaam"                     # a JSON file with this extension
ALLOWED_EXT = {".agtaam", ".json"}  # .json = older projects, still readable


class ProjectError(Exception):
    """Base class for every error raised here (catch this one)."""


class NoPathError(ProjectError):
    """Save was asked but the project has no file yet. Use save_as()."""


class ProjectFileError(ProjectError):
    """The file is missing, unreadable, or is not an A-GTAAM project."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class Layer:
    """One layer: a reference to a data file plus how it is shown."""
    name: str
    kind: str = "raster"                 # raster | vector | basemap | anything you use
    source: Optional[str] = None         # path to the data file (or URL for a basemap)
    id: str = field(default_factory=new_id)
    visible: bool = True
    opacity: float = 1.0
    derived_from: Optional[str] = None   # id of the layer a tool result came from
    tool: Optional[str] = None           # "slope", "hillshade", ... (None = user-added)
    meta: dict = field(default_factory=dict)


# host app supplies this: save a tool result into `folder`, return the file path (or None)
DerivedWriter = Callable[[Layer, Path], Optional[str]]


class ProjectManager:
    """Holds the open project. One instance per app."""

    def __init__(self, derived_writer: Optional[DerivedWriter] = None) -> None:
        self.derived_writer = derived_writer
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self, name: str = "Untitled") -> None:
        self.name = name
        self.path: Optional[str] = None
        self.created = _now()
        self.layers: list[Layer] = []            # top of the drawing order first
        self.gui: dict[str, Any] = {}            # the host window's own state (zoom, ramp ...)
        self._version = 0
        self._saved_version = 0

    def touch(self) -> None:
        """Tell the project something changed (shows as unsaved)."""
        self._version += 1

    def is_dirty(self) -> bool:
        return self._version != self._saved_version

    def info(self) -> dict:
        return {"name": self.name, "path": self.path, "dirty": self.is_dirty(),
                "layer_count": len(self.layers), "created": self.created}

    # ----------------------------------------------------------------- layers
    def get(self, layer_id: str) -> Layer:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        raise KeyError(layer_id)

    def add_layer(self, layer: Layer) -> Layer:
        self.layers.insert(0, layer)             # new layers go on top
        self.touch()
        return layer

    def remove_layer(self, layer_id: str) -> None:
        self.layers.remove(self.get(layer_id))
        self.touch()

    def update_layer(self, layer_id: str, **fields: Any) -> Layer:
        layer = self.get(layer_id)
        for key, value in fields.items():
            if not hasattr(layer, key):
                raise AttributeError(f"Layer has no field '{key}'")
            setattr(layer, key, value)
        self.touch()
        return layer

    def reorder(self, layer_ids: list[str]) -> None:
        if sorted(layer_ids) != sorted(l.id for l in self.layers):
            raise ValueError("layer_ids must list every layer exactly once")
        by_id = {l.id: l for l in self.layers}
        self.layers = [by_id[i] for i in layer_ids]
        self.touch()

    def set_gui(self, state: dict) -> None:
        self.gui = copy.deepcopy(state)

    # -------------------------------------------------------------------- new
    def new(self, name: str = "Untitled") -> dict:
        self.reset(name)
        return self.info()

    # ------------------------------------------------------------------- save
    def save(self, path: Optional[str] = None, gui: Optional[dict] = None,
             name: Optional[str] = None) -> dict:
        """Save to `path`, or over the current file when `path` is None.

        Returns info plus `saved_layers` and `skipped_layers` (names that could not be kept).
        """
        target = path or self.path
        if not target:
            raise NoPathError("This project has no file yet - use save_as().")
        target_p = Path(target)
        if target_p.suffix.lower() not in ALLOWED_EXT:
            target_p = target_p.with_suffix(EXT)
        if name:
            self.name = name
        if gui is not None:
            self.set_gui(gui)
        data_dir = target_p.with_name(target_p.stem + "_data")

        entries, skipped = [], []
        for layer in reversed(self.layers):                       # file stores bottom first
            source = layer.source
            if layer.tool and layer.derived_from and self.derived_writer:
                try:
                    written = self.derived_writer(layer, data_dir)
                except OSError:
                    written = None
                if written:
                    layer.source = source = written
            if source is None and layer.kind != "basemap":
                skipped.append(layer.name)
                continue
            rel = None
            if source and layer.kind != "basemap":
                try:
                    rel = os.path.relpath(source, target_p.parent)
                except ValueError:                                # other drive on Windows
                    rel = None
            entry = asdict(layer)
            entry["source_rel"] = rel
            entries.append(entry)

        doc = {"format": FORMAT, "version": FORMAT_VERSION, "name": self.name,
               "created": self.created, "saved": _now(), "gui": self.gui, "layers": entries}
        target_p.parent.mkdir(parents=True, exist_ok=True)
        tmp = target_p.with_name(target_p.name + ".tmp")          # write fully, then swap in:
        tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")   # a crash never leaves
        os.replace(tmp, target_p)                                     # a half-written file
        self.path = str(target_p)
        self._saved_version = self._version
        return {**self.info(), "saved_layers": len(entries), "skipped_layers": skipped}

    def save_as(self, path: str, gui: Optional[dict] = None, name: Optional[str] = None) -> dict:
        return self.save(path, gui=gui, name=name)

    # ------------------------------------------------------------------- open
    @staticmethod
    def _find(entry: dict, folder: Path) -> Optional[str]:
        """The data file: the saved path, else the same place relative to the project."""
        rel = entry.get("source_rel")
        for cand in (entry.get("source"), str(folder / rel) if rel else None):
            if cand and Path(cand).is_file():
                return cand
        return None

    def open(self, path: str) -> dict:
        """Open a project file. The data files are NOT read here - the host app loads each
        layer from `layer.source`. Returns info plus `missing_layers` and `gui`.

        A bad file raises ProjectFileError and leaves the current project untouched.
        """
        p = Path(path)
        if not p.is_file():
            raise ProjectFileError(f"Project file not found: {path}")
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ProjectFileError("This is not an A-GTAAM project file.") from None
        if not isinstance(doc, dict) or doc.get("format") != FORMAT:
            raise ProjectFileError("This is not an A-GTAAM project file.")

        layers, missing = [], []
        for entry in doc.get("layers", []):                       # bottom first in the file
            kind = entry.get("kind", "raster")
            source = entry.get("source") if kind == "basemap" else self._find(entry, p.parent)
            if kind != "basemap" and source is None:
                missing.append(entry.get("name", str(entry.get("source"))))
                continue
            layers.append(Layer(
                id=entry.get("id") or new_id(), name=entry.get("name", "Layer"), kind=kind,
                source=source, visible=entry.get("visible", True),
                opacity=entry.get("opacity", 1.0), derived_from=entry.get("derived_from"),
                tool=entry.get("tool"), meta=entry.get("meta", {})))
        layers.reverse()                                          # keep "top first" in memory

        self.reset(doc.get("name", p.stem))
        self.created = doc.get("created", self.created)
        self.layers = layers
        self.gui = doc.get("gui", {}) or {}
        self.path = str(p)
        return {**self.info(), "missing_layers": missing, "gui": self.gui}
