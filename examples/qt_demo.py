"""A tiny window to try New / Open / Save / Save As:  python examples/qt_demo.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # run without installing

from PyQt6.QtWidgets import QApplication, QListWidget, QMainWindow, QToolBar

from agtaam_project import Layer, ProjectManager
from agtaam_project.qt import ProjectWindowMixin


class Win(ProjectWindowMixin, QMainWindow):
    APP_NAME = "Project demo"

    def __init__(self):
        super().__init__()
        self.resize(520, 360)
        self.listw = QListWidget()
        self.setCentralWidget(self.listw)
        bar = QToolBar()
        self.addToolBar(bar)
        for text, fn in [("New", self.act_new_project), ("Open", self.act_open_project),
                         ("Save", self.act_save_project), ("Save As", self.act_save_project_as),
                         ("Add layer", self.add_layer)]:
            bar.addAction(text, fn)
        self.project = ProjectManager()
        self._init_project_actions()

    def add_layer(self):
        n = self.listw.count() + 1
        self.project.add_layer(Layer(f"Layer {n}", source=__file__))   # a real file path
        self.listw.insertItem(0, f"Layer {n}")
        self.mark_dirty()

    # the three hooks the mixin needs
    def clear_workspace(self):
        self.listw.clear()

    def rebuild_from_project(self, layers, gui, missing):
        for layer in layers:
            self.listw.addItem(layer.name)

    def collect_gui_state(self):
        return {}


app = QApplication(sys.argv)
win = Win()
win.show()
sys.exit(app.exec())
