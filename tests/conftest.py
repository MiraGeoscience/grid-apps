# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2026 Mira Geoscience Ltd.                                     '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of the MIT License       '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
from __future__ import annotations

import numpy as np
import pytest
from discretize.utils import mesh_builder_xyz
from geoh5py.objects import BlockModel, Grid2D

from grid_apps.block_models.driver import Driver as BlockModelDriver


@pytest.fixture
def setup_test_octree(diagonal_balance=False):
    """
    Create a circle of points and treemesh from extent.
    """
    refinement = "4, 4"
    minimum_level = 4
    cell_sizes = [5.0, 5.0, 5.0]
    n_data = 16
    degree = np.linspace(0, 2 * np.pi, n_data)
    locations = np.c_[
        np.cos(degree) * 200.0, np.sin(degree) * 200.0, np.sin(degree * 2.0) * 40.0
    ]
    # Add point at origin
    locations = np.r_[locations, np.zeros((1, 3))]
    depth_core = 400.0
    horizontal_padding = 500.0
    vertical_padding = 200.0
    paddings = [
        [horizontal_padding, horizontal_padding],
        [horizontal_padding, horizontal_padding],
        [vertical_padding, vertical_padding],
    ]
    # Create a tree mesh from discretize
    treemesh = mesh_builder_xyz(
        locations,
        cell_sizes,
        padding_distance=paddings,
        mesh_type="tree",
        depth_core=depth_core,
        tree_diagonal_balance=diagonal_balance,
    )

    params_dict = {
        "u_cell_size": cell_sizes[0],
        "v_cell_size": cell_sizes[1],
        "w_cell_size": cell_sizes[2],
        "horizontal_padding": horizontal_padding,
        "vertical_padding": vertical_padding,
        "depth_core": depth_core,
        "diagonal_balance": False,
        "minimum_level": minimum_level,
    }

    return (
        locations,
        refinement,
        treemesh,
        params_dict,
    )


def setup_block_model(
    workspace,
    *,
    top=200,
    depth_core=300.0,
    pads=(100, 150, 200, 300, 0, 0),
    cell_size=(50, 50, 50),
    expansion_factor=1.1,
) -> BlockModel:
    # padding in the W/E/N/S directions should make create locs at least as
    # far as the core hull plus the padding distances
    height = 300
    width = 1000
    n = 3
    x_grid, y_grid = np.meshgrid(np.arange(0, width, n), np.arange(0, height, n))
    z_grid = np.around((top / 2) * np.sin(x_grid) + (top / 2), -1)
    locs = np.c_[x_grid.ravel(), y_grid.ravel(), z_grid.ravel()]

    mesh = BlockModelDriver.get_block_model(
        workspace, locs, cell_size, depth_core, pads, expansion_factor, name="test"
    )
    return mesh


def setup_grid2d_model(workspace) -> Grid2D:
    mesh = Grid2D.create(
        workspace,
        origin=[0, 0, 0],
        u_cell_size=50.0,
        v_cell_size=50.0,
        u_count=10,
        v_count=15,
    )
    return mesh
