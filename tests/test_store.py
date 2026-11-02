import json
import shutil

import pytest

from agtaam_project import Layer, NoPathError, ProjectFileError, ProjectManager


def _dem(tmp_path, name="dem.tif"):
    f = tmp_path / name
    f.write_bytes(b"fake raster")
    return str(f)


def test_new_project_is_empty_and_clean():
    pm = ProjectManager()
    pm.add_layer(Layer("a", source="x"))
    assert pm.is_dirty()
    pm.new("Fresh")
    assert pm.layers == [] and pm.name == "Fresh" and not pm.is_dirty() and pm.path is None


def test_dirty_flag_follows_changes_and_save(tmp_path):
    pm = ProjectManager()
    assert not pm.is_dirty()
    layer = pm.add_layer(Layer("dem", source=_dem(tmp_path)))
    assert pm.is_dirty()
    pm.save_as(str(tmp_path / "p"))
    assert not pm.is_dirty()
    pm.update_layer(layer.id, visible=False)
    assert pm.is_dirty()


def test_save_without_a_path_asks_for_save_as():
    with pytest.raises(NoPathError):
        ProjectManager().save()


def test_round_trip_keeps_layers_order_and_gui(tmp_path):
    pm = ProjectManager()
    bottom = pm.add_layer(Layer("bottom", source=_dem(tmp_path, "b.tif")))
    top = pm.add_layer(Layer("top", source=_dem(tmp_path, "t.tif"), visible=False, opacity=0.4))
    res = pm.save_as(str(tmp_path / "mine"), gui={"zoom": 3, "ramp": "terrain"}, name="mine")
    assert res["path"].endswith("mine.agtaam") and res["saved_layers"] == 2

    other = ProjectManager()
    info = other.open(res["path"])
    assert info["name"] == "mine" and info["gui"] == {"zoom": 3, "ramp": "terrain"}
    assert info["missing_layers"] == [] and not other.is_dirty()
    assert [l.name for l in other.layers] == ["top", "bottom"]        # top first
    assert other.get(top.id).visible is False and other.get(top.id).opacity == 0.4
    assert other.get(bottom.id).name == "bottom"


def test_save_over_current_file_needs_no_path(tmp_path):
    pm = ProjectManager()
    pm.add_layer(Layer("dem", source=_dem(tmp_path)))
    pm.save_as(str(tmp_path / "p.agtaam"))
    pm.add_layer(Layer("two", source=_dem(tmp_path, "two.tif")))
    assert pm.save()["saved_layers"] == 2


def test_tool_results_are_written_next_to_the_project(tmp_path):
    def writer(layer, folder):
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{layer.id}.tif"
        target.write_bytes(b"result")
        return str(target)

    pm = ProjectManager(derived_writer=writer)
    dem = pm.add_layer(Layer("dem", source=_dem(tmp_path)))
    slope = pm.add_layer(Layer("slope", derived_from=dem.id, tool="slope"))   # no file yet
    res = pm.save_as(str(tmp_path / "p"))
    assert res["saved_layers"] == 2 and res["skipped_layers"] == []
    assert (tmp_path / "p_data" / f"{slope.id}.tif").exists()
    reopened = ProjectManager()
    info = reopened.open(res["path"])
    assert info["missing_layers"] == []
    got = reopened.get(slope.id)
    assert got.tool == "slope" and got.derived_from == dem.id


def test_tool_result_without_a_writer_is_reported_not_silently_lost(tmp_path):
    pm = ProjectManager()
    dem = pm.add_layer(Layer("dem", source=_dem(tmp_path)))
    pm.add_layer(Layer("slope", derived_from=dem.id, tool="slope"))
    res = pm.save_as(str(tmp_path / "p"))
    assert res["saved_layers"] == 1 and res["skipped_layers"] == ["slope"]


def test_moved_project_folder_still_finds_its_data(tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    pm = ProjectManager()
    pm.add_layer(Layer("dem", source=_dem(a)))
    pm.save_as(str(a / "p.agtaam"))
    b = tmp_path / "b"
    shutil.copytree(a, b)
    shutil.rmtree(a)
    info = ProjectManager().open(str(b / "p.agtaam"))
    assert info["missing_layers"] == []


def test_missing_data_is_listed_but_project_still_opens(tmp_path):
    pm = ProjectManager()
    pm.add_layer(Layer("gone", source=_dem(tmp_path, "gone.tif")))
    pm.add_layer(Layer("kept", source=_dem(tmp_path, "kept.tif")))
    res = pm.save_as(str(tmp_path / "p"))
    (tmp_path / "gone.tif").unlink()
    other = ProjectManager()
    info = other.open(res["path"])
    assert info["missing_layers"] == ["gone"] and [l.name for l in other.layers] == ["kept"]


def test_bad_file_is_refused_and_current_project_is_untouched(tmp_path):
    pm = ProjectManager()
    pm.add_layer(Layer("keep me", source="x"))
    bad = tmp_path / "x.agtaam"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(ProjectFileError):
        pm.open(str(bad))
    other = tmp_path / "y.agtaam"
    other.write_text(json.dumps({"format": "something-else"}), encoding="utf-8")
    with pytest.raises(ProjectFileError):
        pm.open(str(other))
    with pytest.raises(ProjectFileError):
        pm.open(str(tmp_path / "nope.agtaam"))
    assert [l.name for l in pm.layers] == ["keep me"]


def test_older_json_projects_still_open(tmp_path):
    f = tmp_path / "old.json"
    f.write_text(json.dumps({"format": "A-GTAAM-project", "version": 1, "name": "Old",
                             "layers": []}), encoding="utf-8")
    assert ProjectManager().open(str(f))["name"] == "Old"


def test_reorder_and_remove(tmp_path):
    pm = ProjectManager()
    a = pm.add_layer(Layer("a", source="x"))
    b = pm.add_layer(Layer("b", source="x"))
    pm.reorder([a.id, b.id])
    assert [l.name for l in pm.layers] == ["a", "b"]
    pm.remove_layer(a.id)
    assert [l.name for l in pm.layers] == ["b"]
    with pytest.raises(ValueError):
        pm.reorder(["nope"])


def test_opens_a_project_saved_by_the_a_gtaam_backend(tmp_path):
    dem = _dem(tmp_path)
    f = tmp_path / "from_backend.agtaam"
    f.write_text(json.dumps({
        "format": "A-GTAAM-project", "version": 2, "name": "From backend",
        "workspace": {"mode": "explore"}, "gui": {"ramp": "terrain"},
        "layers": [{"id": "ab12cd34", "name": "dem", "kind": "raster", "source": dem,
                    "source_rel": "dem.tif", "visible": True, "opacity": 1.0,
                    "derived_from": None, "tool": None, "meta": {}}]}), encoding="utf-8")
    pm = ProjectManager()
    info = pm.open(str(f))
    assert info["name"] == "From backend" and pm.layers[0].id == "ab12cd34"
