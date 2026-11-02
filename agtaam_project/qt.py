"""Optional PyQt6 part: the menu actions, "Save changes?" question and shortcuts.

Import this only if your app uses PyQt6:   from agtaam_project.qt import ProjectWindowMixin

How to plug it in (3 steps)
---------------------------
1.  class MainWindow(ProjectWindowMixin, QMainWindow): ...
2.  In __init__, after the window is built:
        self.project = ProjectManager(derived_writer=my_writer)   # my_writer is optional
        self._init_project_actions()
3.  Implement these three small hooks on your window:
        collect_gui_state(self) -> dict            # zoom, colour ramp ... anything to remember
        clear_workspace(self)                       # remove all layers from the screen
        rebuild_from_project(self, layers, gui, missing) -> list[str] | None
            # load each Layer in `layers` (bottom layer last in the list) from layer.source,
            # re-apply `gui`; return notes about layers you could not draw (or None)

Call self.mark_dirty() whenever the user changes something worth saving. Connect your menu
buttons to act_new_project / act_open_project / act_save_project / act_save_project_as.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from .store import EXT, ProjectError

FILTER = "A-GTAAM project (*.agtaam);;Older projects (*.json);;All files (*)"


class ProjectWindowMixin:
    APP_NAME = "My DEM App"          # shown in the window title
    DEFAULT_NAME = "Untitled"

    project = None                    # set to a ProjectManager in your __init__
    _project_ready = False
    _last_dir = str(Path.home())

    # ------------------------------------------------------------------ setup
    def _init_project_actions(self) -> None:
        self._project_ready = True
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.act_new_project)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.act_open_project)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.act_save_project)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.act_save_project_as)
        self.refresh_title()

    def mark_dirty(self) -> None:
        if self._project_ready and not self.project.is_dirty():
            self.project.touch()
            self.refresh_title()
        elif self._project_ready:
            self.project.touch()

    def refresh_title(self) -> None:
        star = "*" if self.project.is_dirty() else ""
        self.setWindowTitle(f"{self.project.name}{star} - {self.APP_NAME}")

    def show_message(self, text: str) -> None:       # override for a toast; default = status bar
        bar = getattr(self, "statusBar", None)
        if callable(bar):
            bar().showMessage(text, 4000)

    # ------------------------------------------------------------ ask first
    def _confirm_discard(self, action: str) -> bool:
        """True = go ahead. With unsaved changes: Save / Don't Save / Cancel."""
        if not self.project.is_dirty():
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Unsaved changes")
        box.setText(f"Save changes to “{self.project.name}” before you {action}?")
        box.setInformativeText("Your changes will be lost if you don't save them.")
        save = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Don't Save", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel:
            return False
        if clicked is save:
            return self.act_save_project()
        return True

    def closeEvent(self, event) -> None:
        if self._confirm_discard("close"):
            event.accept()
        else:
            event.ignore()

    # ---------------------------------------------------------------- actions
    def act_new_project(self) -> None:
        if not self._confirm_discard("create a new project"):
            return
        self.project.new(self.DEFAULT_NAME)
        self.clear_workspace()
        self.refresh_title()
        self.show_message("New project")

    def act_save_project(self) -> bool:
        if self.project.path is None:
            return self.act_save_project_as()
        return self._save(None, None)

    def act_save_project_as(self) -> bool:
        start = str(Path(self._last_dir) / f"{self.project.name}{EXT}")
        path, _ = QFileDialog.getSaveFileName(self, "Save project as", start, FILTER)
        if not path:
            return False
        p = Path(path)
        if p.suffix.lower() not in (EXT, ".json"):
            p = p.with_suffix(EXT)
        return self._save(str(p), p.stem)

    def _save(self, path, name) -> bool:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            res = self.project.save(path, gui=self.collect_gui_state(), name=name)
        except (ProjectError, OSError) as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Save project", f"Could not save the project:\n{exc}")
            return False
        QApplication.restoreOverrideCursor()
        self._last_dir = str(Path(res["path"]).parent)
        self.refresh_title()
        if res["skipped_layers"]:
            QMessageBox.warning(self, "Save project",
                                "These layers could not be written and are not in the project:\n\n"
                                + "\n".join(f"  • {n}" for n in res["skipped_layers"]))
        self.show_message(f"Project saved · {Path(res['path']).name}")
        return True

    def act_open_project(self) -> None:
        if not self._confirm_discard("open another project"):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open project", self._last_dir, FILTER)
        if path:
            self.open_project_file(Path(path))

    def open_project_file(self, path: Path) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            res = self.project.open(str(path))
            self.clear_workspace()
            notes = self.rebuild_from_project(list(self.project.layers), res["gui"],
                                              res["missing_layers"]) or []
        except (ProjectError, OSError) as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Open project", f"Could not open the project:\n{exc}")
            return
        QApplication.restoreOverrideCursor()
        self._last_dir = str(path.parent)
        self.refresh_title()
        lines = [f"  • {n}  (file not found)" for n in res["missing_layers"]]
        lines += [f"  • {n}" for n in notes]
        if lines:
            QMessageBox.warning(self, "Open project",
                                "The project opened, but some layers could not be loaded:\n\n"
                                + "\n".join(lines))
        self.show_message(f"Project opened · {path.name}")

    # ----------------------------------------------- hooks YOU implement
    def collect_gui_state(self) -> dict:
        return {}

    def clear_workspace(self) -> None:
        raise NotImplementedError

    def rebuild_from_project(self, layers, gui, missing):
        raise NotImplementedError
