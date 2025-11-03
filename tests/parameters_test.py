# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2025 Mira Geoscience Ltd.                                     '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of the MIT License       '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from geoh5py import Workspace
from geoh5py.objects import Points
from geoh5py.ui_json import InputFile

from grid_apps import assets_path
from grid_apps.block_models.options import BlockModelOptions


def test_block_model_params_from_uijson(tmp_path):
    ws = Workspace(tmp_path / "test.geoh5")
    pts = Points.create(ws, name="my points", vertices=[[0, 0, 0]])

    updates = {
        "geoh5": ws,
        "objects": pts,
        "cell_size_x": 50.0,
        "cell_size_y": 50.0,
        "cell_size_z": 50.0,
        "depth_core": 300.0,
        "horizontal_padding": 100.0,
        "bottom_padding": 100.0,
        "export_as": "my block model",
    }

    ifile = InputFile.read_ui_json(
        assets_path() / "uijson/block_models.ui.json", validate=False
    )
    for k, v in updates.items():
        ifile.set_data_value(k, v)

    params = BlockModelOptions.build(ifile)
    assert params.geoh5 == ws
    assert params.source.objects == updates["objects"]
    assert params.creation.cell_size_x == updates["cell_size_x"]
    assert params.creation.cell_size_y == updates["cell_size_y"]
    assert params.creation.cell_size_z == updates["cell_size_z"]
    assert params.creation.depth_core == updates["depth_core"]
    assert params.creation.horizontal_padding == updates["horizontal_padding"]
    assert params.creation.bottom_padding == updates["bottom_padding"]
    assert params.creation.expansion_factor == 1.1
    assert params.output.export_as == updates["export_as"]
