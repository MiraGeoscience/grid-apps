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


def gaussian_wave(locations: np.ndarray, width: float, amplitude: float) -> np.ndarray:
    """
    Generate a Gaussian wave function.

    :param locations: Array of shape (n, m) representing the coordinates.
    :param width: Width of the Gaussian wave.
    :param amplitude: Amplitude of the Gaussian wave.

    :return: Array of shape (n,) representing the Gaussian wave values at the given locations.
    """
    exp = np.zeros(locations.shape[0])

    for loc in locations.T:
        exp += (loc / width) ** 2

    return amplitude * np.exp(-0.5 * (exp))


def test_block_model_to_octree(tmp_path):
    # Create a test block model
    h5file_path = tmp_path / f"{__name__}.geoh5"
    ifile = tmp_path / f"{__name__}.ui.json"
    with Workspace.create(h5file_path) as workspace:
        block_model = generate_block_model(workspace)

        params = BlockModel2OctreeOptions.build(
            **{
                "geoh5": workspace,
                "entity": block_model,
            }
        )

        params.write_ui_json(ifile)

    ifile_class = InputFile.read_ui_json(ifile)
    driver = BlockModelToOctreeDriver(ifile_class)
    octree = driver.make_grid()

    assert octree.n_cells == 13987


def test_float_refine_octree(tmp_path):
    # Create a test block model
    h5file_path = tmp_path / f"{__name__}.geoh5"
    with Workspace.create(h5file_path) as workspace:
        block_model = generate_block_model(workspace)

        wave = gaussian_wave(block_model.centroids, width=50, amplitude=100)
        topo = gaussian_wave(block_model.centroids[:, :2], width=100, amplitude=50)
        active = block_model.locations[:, 2] < topo

        wave[~active] = np.nan  # Set values below topography to NaN

        # Create float data
        float_data = block_model.add_data({"wave": {"values": wave.flatten()}})

        params = BlockModel2OctreeOptions.build(
            {"geoh5": workspace, "entity": block_model, "data": float_data}
        )

        driver = BlockModelToOctreeDriver(params)
        octree = driver.make_grid()

        assert octree.n_cells == 7883


def test_integer_refine_octree(tmp_path):
    h5file_path = tmp_path / f"{__name__}.geoh5"
    with Workspace.create(h5file_path) as workspace:
        block_model = generate_block_model(workspace)
        wave = gaussian_wave(block_model.centroids, width=50, amplitude=100)

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
