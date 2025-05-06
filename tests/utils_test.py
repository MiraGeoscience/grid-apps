# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2025 Mira Geoscience Ltd.                                     '
#  All rights reserved.                                                             '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of a proprietary license '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from pathlib import Path

import numpy as np
from geoh5py import Workspace
from pytest import raises

from grid_apps.block_models.driver import Driver as BlockModelDriver
from grid_apps.utils import block_model_to_discretize, tensor_mesh_ordering


# pylint: disable=duplicate-code
def test_truncate_locs_depths():
    # If z range of locations is larger than depth_core then locations are truncated
    # to the depth_core and the depth_core is reduced to w_cell_size
    top = 500
    depth_core = 300.0
    height = 300
    width = 1000
    n = 100

    x_grid, y_grid = np.meshgrid(np.arange(0, width, n), np.arange(0, height, n))
    z_grid = np.around((top / 2) * np.sin(x_grid) + (top / 2), -1)
    locs = np.c_[x_grid.ravel(), y_grid.ravel(), z_grid.ravel()]
    z = 50

    locs = BlockModelDriver.truncate_locs_depths(locs, depth_core)
    assert locs[:, 2].min() == (locs[:, 2].max() - depth_core)

    depth_core = BlockModelDriver.minimum_depth_core(locs, depth_core, z)
    assert depth_core == z

    # If z range of locs are the same as the depth_core then locations are unaffected
    # but depth_core is reduced to w_cell_size
    top = 500
    depth_core = 500.0
    height = 300
    width = 1000
    n = 100

    x_grid, y_grid = np.meshgrid(np.arange(0, width, n), np.arange(0, height, n))
    z_grid = np.around((top / 2) * np.sin(x_grid) + (top / 2), -1)
    locs = np.c_[x_grid.ravel(), y_grid.ravel(), z_grid.ravel()]
    z = 50

    locs = BlockModelDriver.truncate_locs_depths(locs, depth_core)
    assert locs[:, 2].min() == (locs[:, 2].max() - depth_core)

    depth_core = BlockModelDriver.minimum_depth_core(locs, depth_core, z)
    assert depth_core == z

    # If z range of locs are less than the the depth core then the depth_core is
    # reduced by the z range
    top = 400
    depth_core = 500.0
    height = 300
    width = 1000
    n = 100

    x_grid, y_grid = np.meshgrid(np.arange(0, width, n), np.arange(0, height, n))
    z_grid = np.around((top / 2) * np.sin(x_grid) + (top / 2), -1)
    locs = np.c_[x_grid.ravel(), y_grid.ravel(), z_grid.ravel()]
    z = 50

    locs = BlockModelDriver.truncate_locs_depths(locs, depth_core)
    zrange = locs[:, 2].max() - locs[:, 2].min()
    assert zrange == top
    depth_core_new = BlockModelDriver.minimum_depth_core(locs, depth_core, z)
    assert zrange + depth_core_new == depth_core + z


def test_find_top_padding(tmp_path: Path):
    top = 500
    depth_core = 300.0
    height = 300
    width = 1000
    n = 100
    ws = Workspace(tmp_path / "data_transfer.geoh5")

    x_grid, y_grid = np.meshgrid(np.arange(0, width, n), np.arange(0, height, n))
    z_grid = np.around((top / 2) * np.sin(x_grid) + (top / 2), -1)
    locs = np.c_[x_grid.ravel(), y_grid.ravel(), z_grid.ravel()]
    pads = [0, 0, 0, 0, 100, 100]  # padding on the top
    h = [50, 50, 50]

    obj = BlockModelDriver.get_block_model(
        ws, locs, h, depth_core, pads, 1.1, name="test2"
    )

    top_padding = BlockModelDriver.find_top_padding(obj, h[2])

    assert top_padding >= pads[-1]


def test_block_model_to_discretize(tmp_path):
    # Create a test block model
    h5file_path = tmp_path / f"{__name__}.geoh5"
    with Workspace.create(h5file_path) as workspace:
        locs = np.array([[0, 0, 0], [150, 0, 0], [0, 150, 0]])
        depth_core = 150.0
        pads = [0, 0, 0, 0, 0, 0]  # padding on the top
        h = [50, 50, 50]
        block_model = BlockModelDriver.get_block_model(
            workspace,
            locs,
            h,
            depth_core,
            pads,
            1.1,
            name="TestBlockModel",
        )

        with raises(TypeError):
            block_model_to_discretize("abc")

        tensor = block_model_to_discretize(block_model)
        indices = tensor_mesh_ordering(block_model)

        # Check the shape of the discretized points
        np.testing.assert_allclose(block_model.centroids[indices], tensor.cell_centers)
