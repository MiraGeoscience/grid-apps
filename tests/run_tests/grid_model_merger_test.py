# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2026 Mira Geoscience Ltd.                                     '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of the MIT License       '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from __future__ import annotations

from pathlib import Path

import numpy as np
from geoh5py.objects import BlockModel, Octree, Points
from geoh5py.workspace import Workspace

from grid_apps.block_models.driver import Driver as BlockModelDriver
from grid_apps.grid_model_merger.driver import Driver
from grid_apps.grid_model_merger.options import GridModelMergerOptions
from grid_apps.octree_creation.driver import OctreeDriver
from grid_apps.octree_creation.options import OctreeOptions


def setup_block_model(workspace) -> BlockModel:
    # padding in the W/E/N/S directions should make create locs at least as
    # far as the core hull plus the padding distances
    top = 500
    depth_core = 300.0
    height = 300
    width = 1000
    n = 100

    x_grid, y_grid = np.meshgrid(np.arange(0, width, n), np.arange(0, height, n))
    z_grid = np.around((top / 2) * np.sin(x_grid) + (top / 2), -1)
    locs = np.c_[x_grid.ravel(), y_grid.ravel(), z_grid.ravel()]
    pads = [100, 150, 200, 300, 0, 0]
    mesh = BlockModelDriver.get_block_model(
        workspace, locs, [50, 50, 50], depth_core, pads, 1.1, name="test"
    )
    return mesh


def setup_octree(workspace, locations, refinement, params_dict) -> Octree:
    points = Points.create(workspace, vertices=locations)

    params_dict.update(
        {
            "geoh5": workspace,
            "objects": points,
            "u_cell_size": 25.0,
            "v_cell_size": 25.0,
            "w_cell_size": 25.0,
            "refinements": [
                {
                    "refinement_object": points,
                    "levels": refinement,
                    "horizon": False,
                }
            ],
        }
    )
    params = OctreeOptions(**params_dict)
    driver = OctreeDriver(params)
    return driver.run()


def test_merge_block_model(tmp_path: Path):  # pylint: disable=too-many-locals

    with Workspace.create(tmp_path / f"{__name__}.geoh5") as ws:
        mesh = setup_block_model(ws)
        other = mesh.copy(origin=(515, 10, 500))
        model_b = other.add_data({"values": {"values": np.full(mesh.n_cells, 2.0)}})
        model_a = mesh.add_data({"values": {"values": np.full(mesh.n_cells, 1.0)}})

        options = GridModelMergerOptions.build(
            {
                "geoh5": ws,
                "input_a_grid": mesh,
                "input_b_grid": other,
                "input_a_model": model_a,
                "input_b_model": model_b,
            }
        )

        driver = Driver(options)
        out_grid = driver.run()

        merged_model = out_grid.children[0]
        np.testing.assert_almost_equal(merged_model.values[2642], 1.5, decimal=2)

        # Repeat with a hole in the first model
        values = model_a.values
        values[(mesh.centroids[:, 0] > 750) & (mesh.centroids[:, 1] > 250)] = np.nan
        model_a.values = values

        out_grid = driver.run()
        merged_model = out_grid.children[0]
        np.testing.assert_almost_equal(merged_model.values[2642], 2.0, decimal=2)


def test_merge_octree_model(tmp_path: Path, setup_test_octree):  # pylint: disable=too-many-locals
    (locations, refinement, _, params_dict) = setup_test_octree

    with Workspace.create(tmp_path / f"{__name__}.geoh5") as ws:
        mesh = setup_octree(ws, locations, refinement, params_dict)
        other = mesh.copy(origin=(-600, -600, mesh.origin["z"]))

        model_b = other.add_data({"values": {"values": np.full(mesh.n_cells, 2.0)}})
        model_a = mesh.add_data({"values": {"values": np.full(mesh.n_cells, 1.0)}})

        options = GridModelMergerOptions.build(
            {
                "geoh5": ws,
                "input_a_grid": mesh,
                "input_b_grid": other,
                "input_a_model": model_a,
                "input_b_model": model_b,
            }
        )

        driver = Driver(options)
        out_grid = driver.run()

        merged_model = out_grid.children[0]
        np.testing.assert_almost_equal(merged_model.values[1542], 1.5, decimal=2)

        # Repeat with a hole in the first model
        values = model_a.values
        values[(mesh.centroids[:, 0] > 200) & (mesh.centroids[:, 1] > 200)] = np.nan
        model_a.values = values

        out_grid = driver.run()
        merged_model = out_grid.children[0]
        np.testing.assert_almost_equal(merged_model.values[1568], 2.0, decimal=2)


def test_merge_mixed_model(tmp_path: Path, setup_test_octree):  # pylint: disable=too-many-locals
    (locations, refinement, _, params_dict) = setup_test_octree

    with Workspace.create(tmp_path / f"{__name__}.geoh5") as ws:
        octree = setup_octree(ws, locations, refinement, params_dict)
        block_model = setup_block_model(ws)

        model_a = octree.add_data({"values": {"values": np.full(octree.n_cells, 1.0)}})
        model_b = block_model.add_data(
            {"values": {"values": np.full(block_model.n_cells, 2.0)}}
        )

        options = GridModelMergerOptions.build(
            {
                "geoh5": ws,
                "input_a_grid": octree,
                "input_b_grid": block_model,
                "input_a_model": model_a,
                "input_b_model": model_b,
            }
        )

        driver = Driver(options)
        out_grid = driver.run()

        assert isinstance(out_grid, Octree)

        options = GridModelMergerOptions.build(
            {
                "geoh5": ws,
                "input_b_grid": octree,
                "input_a_grid": block_model,
                "input_b_model": model_a,
                "input_a_model": model_b,
            }
        )

        driver = Driver(options)
        out_grid = driver.run()

        assert isinstance(out_grid, BlockModel)
