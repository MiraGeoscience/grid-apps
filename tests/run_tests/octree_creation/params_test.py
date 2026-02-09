# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2026 Mira Geoscience Ltd.                                     '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of the MIT License       '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

import numpy as np
import pytest
from geoh5py import Workspace
from geoh5py.groups import UIJsonGroup
from geoh5py.objects import Points
from geoh5py.ui_json import InputFile

from grid_apps import assets_path
from grid_apps.octree_creation.driver import OctreeDriver
from grid_apps.octree_creation.options import (
    OctreeOptions,
    collect_refinements_from_dict,
    refinement_identifiers,
)


# pylint: disable=protected-access
def test_collect_refinements_from_dict():
    data = {
        "Not a refinement": "ignore me",
        "Refinement A object": "I am not None. Collect me.",
        "Refinement A levels": [4, 2],
        "Refinement A horizon": False,
        "Refinement A distance": 1000,
        "Refinement B object": None,
        "Refinement B levels": None,
        "Refinement B horizon": None,
        "Refinement B distance": None,
    }
    refinements = collect_refinements_from_dict(data)
    assert len(refinements) == 2
    assert refinements[0] is not None
    assert all(
        k in refinements[0]
        for k in ["refinement_object", "levels", "horizon", "distance"]
    )
    assert refinements[1] is None

    # Test refinements detected
    active = refinement_identifiers(data)
    assert len(active) == 2
    assert all(k in active for k in ["A", "B"])


def test_params_from_dict(tmp_path):
    with Workspace.create(tmp_path / f"{__name__}.geoh5") as ws:
        points = Points.create(ws, name="test", vertices=np.random.rand(100, 3))

        kwargs = {
            "geoh5": ws,
            "objects": points,
            "refinements": [{"refinement_object": points}],
        }
        params = OctreeOptions(**kwargs)
        assert params.geoh5 == ws
        assert params.objects == points
        assert params.refinements is not None
        refinement = params.refinements[0]  # pylint: disable=unsubscriptable-object
        assert refinement is not None
        assert refinement.refinement_object == points
        assert refinement.levels == [4, 2]
        assert refinement.horizon is False
        assert refinement.distance == np.inf

        kwargs = {
            "geoh5": ws,
            "objects": points,
            "Refinement A object": points,
            "Refinement A levels": [4, 4, 4],
            "Refinement A horizon": False,
            "Refinement A distance": 200,
        }
        with pytest.warns(UserWarning):
            _ = OctreeOptions(**kwargs)


def test_refinement_serializer(tmp_path):
    with Workspace.create(tmp_path / f"{__name__}.geoh5") as ws:
        points = Points.create(ws, name="test", vertices=np.random.rand(100, 3))
        out_group = UIJsonGroup.create(ws, name="AutoMesh")

        kwargs = {
            "geoh5": ws,
            "objects": points,
            "refinements": [
                {
                    "refinement_object": points,
                    "levels": [4, 4, 4],
                    "horizon": False,
                    "distance": 200,
                },
                {
                    "refinement_object": points,
                    "horizon": True,
                },
            ],
            "out_group": out_group,
        }
        params = OctreeOptions(**kwargs)
        dump = params.model_dump()
        assert dump["geoh5"] == ws
        assert dump["objects"] == points
        assert dump["Refinement A object"] == points
        assert dump["Refinement A levels"] == "4, 4, 4"
        assert not dump["Refinement A horizon"]
        assert dump["Refinement A distance"] == 200
        assert dump["Refinement B object"] == points
        assert dump["Refinement B levels"] == "4, 2"
        assert dump["Refinement B horizon"]
        assert dump["Refinement B distance"] == np.inf


def test_treemesh_from_params(tmp_path):
    with Workspace.create(tmp_path / f"{__name__}.geoh5") as ws:
        points = Points.create(ws, name="test", vertices=np.random.rand(100, 3))
        uijson_path = assets_path() / "uijson/octree_mesh.ui.json"
        ifile = InputFile.read_ui_json(uijson_path, validate=False)
        ifile.update_ui_values(
            {
                "geoh5": ws,
                "objects": points,
                "Refinement A object": points,
                "Refinement A levels": [4, 2],
                "Refinement A horizon": False,
                "Refinement A distance": 1000,
            }
        )
        params = OctreeOptions.build(ifile)
        mesh = OctreeDriver.octree_from_params(params)
        assert mesh.u_cell_size == 25.0
        assert mesh.v_cell_size == 25.0
        assert mesh.w_cell_size == 25.0
