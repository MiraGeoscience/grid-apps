# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2025 Mira Geoscience Ltd.                                     '
#  All rights reserved.                                                             '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of a proprietary license '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''


import numpy as np
from geoh5py import Workspace
from geoh5py.objects import BlockModel
from geoh5py.ui_json import InputFile

from grid_apps.block_model_to_octree.driver import Driver as BlockModelToOctreeDriver
from grid_apps.block_model_to_octree.options import BlockModel2OctreeOptions
from grid_apps.block_models.driver import Driver as BlockModelDriver


def generate_block_model(
    workspace: Workspace,
) -> BlockModel:
    """
    Create a block model object from input data.
    """
    locs = np.array([[-75, -75, -75], [75, 75, 75]])
    depth_core = 150.0
    pads = [1000, 1000, 1000, 1000, 1000, 1000]  # padding on the top
    h = [10, 10, 10]
    if locs is None:
        raise ValueError("Input object has no centroids or vertices.")

    # Create the block model
    block_model = BlockModelDriver.get_block_model(
        workspace=workspace,
        locs=locs,
        h=h,
        depth_core=depth_core,
        pads=pads,
        expansion_factor=1.5,
        name="TestBlockModel",
    )
    return block_model


def test_block_model_to_octree(tmp_path):
    # Create a test block model
    h5file_path = tmp_path / f"{__name__}.geoh5"
    ifile = tmp_path / f"{__name__}.ui.json"
    with Workspace.create(h5file_path) as workspace:
        block_model = generate_block_model(workspace)

        params = BlockModel2OctreeOptions.build(
            {
                "geoh5": workspace,
                "entity": block_model,
            }
        )

        params.write_ui_json(ifile)

    ifile_class = InputFile.read_ui_json(ifile)
    driver = BlockModelToOctreeDriver(ifile_class)
    octree = driver.make_grid()

    assert octree.n_cells == 13987


def test_block_model_to_refine_octree(tmp_path):
    # Create a test block model
    h5file_path = tmp_path / f"{__name__}.geoh5"
    with Workspace.create(h5file_path) as workspace:
        block_model = generate_block_model(workspace)

        wave = 100 * np.exp(
            -0.5
            * (
                (block_model.locations[:, 0] / 50) ** 2.0
                + (block_model.locations[:, 1] / 50) ** 2.0
                + (block_model.locations[:, 2] / 50) ** 2.0
            )
        )  #

        # Create float data
        float_data = block_model.add_data({"wave": {"values": wave.flatten()}})

        params = BlockModel2OctreeOptions.build(
            {"geoh5": workspace, "entity": block_model, "data": float_data}
        )

        driver = BlockModelToOctreeDriver(params)
        octree = driver.make_grid()

        assert octree.n_cells == 1254

        # Repeat with reference data
        wave[wave < 25] = 1
        wave[wave > 25] = 2
        ref_data = block_model.add_data(
            {"wave": {"values": wave.flatten(), "type": "referenced"}}
        )

        params = BlockModel2OctreeOptions.build(
            {"geoh5": workspace, "entity": block_model, "data": ref_data}
        )

        driver = BlockModelToOctreeDriver(params)
        octree = driver.make_grid()

        assert octree.n_cells == 5223
