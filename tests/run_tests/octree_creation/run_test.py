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
import pytest
from discretize import TreeMesh
from geoh5py.groups import UIJsonGroup
from geoh5py.objects import (
    CurrentElectrode,
    Curve,
    Octree,
    Points,
    PotentialElectrode,
    Surface,
)
from geoh5py.ui_json.utils import str2list
from geoh5py.workspace import Workspace
from scipy.spatial import Delaunay

from grid_apps.octree_creation.driver import OctreeDriver
from grid_apps.octree_creation.options import OctreeOptions
from grid_apps.utils import octree_2_treemesh, treemesh_2_octree


# pylint: disable=redefined-outer-name, duplicate-code


def test_create_octree_radial(tmp_path: Path, setup_test_octree):  # pylint: disable=too-many-locals
    (locations, refinement, _, params_dict) = setup_test_octree

    with Workspace.create(tmp_path / f"{__name__}.geoh5") as workspace:
        points = Points.create(workspace, vertices=locations)
        out_group = UIJsonGroup.create(workspace, name="Octree Output Group")
        params_dict.update(
            {
                "geoh5": workspace,
                "objects": points,
                "refinements": [
                    {
                        "refinement_object": points,
                        "levels": refinement,
                        "horizon": False,
                    }
                ],
                "out_group": out_group,
                "diagonal_balance": False,
                "ga_group_name": "Tester",
            }
        )
        params = OctreeOptions(**params_dict)
        params.write_ui_json(tmp_path / "testOctree.ui.json")

        driver = OctreeDriver(params)
        driver.run()

        rec_octree = workspace.get_entity("Tester")[0]
        assert rec_octree.parent == out_group
        assert rec_octree.n_cells == 164868


def test_create_octree_surface(tmp_path: Path, setup_test_octree):  # pylint: disable=too-many-locals
    (locations, refinement, _, params_dict) = setup_test_octree

    with Workspace.create(tmp_path / f"{__name__}.geoh5") as workspace:
        simplices = np.unique(
            np.random.randint(0, locations.shape[0] - 1, (locations.shape[0], 3)),
            axis=1,
        )

        surface = Surface.create(
            workspace,
            vertices=locations,
            cells=simplices,
        )
        params_dict.update(
            {
                "geoh5": workspace,
                "objects": surface,
                "refinements": [
                    {
                        "refinement_object": surface,
                        "levels": refinement,
                        "horizon": True,
                        "distance": 1000.0,
                    }
                ],
                "ga_group_name": "Tester",
                "diagonal_balance": False,
            }
        )
        params = OctreeOptions(**params_dict)
        params.write_ui_json(tmp_path / "testOctree.ui.json")
        driver = OctreeDriver(params)
        driver.run()

        rec_octree = workspace.get_entity("Tester")[0]
        assert rec_octree.n_cells == 168487  # Different results on Linux and Windows


def test_create_octree_surface_straight_line(tmp_path: Path, setup_test_octree):
    (_, refinement, treemesh, _) = setup_test_octree

    with Workspace.create(tmp_path / "test.geoh5") as workspace:
        locs = np.c_[np.linspace(-50, 50, 21), np.zeros(21), np.zeros(21)]

        pts = Points.create(workspace, vertices=locs)
        treemesh = OctreeDriver.refine_by_object_type(
            treemesh,
            pts,
            str2list(refinement),
            horizon=True,
            distance=None,
        )
        treemesh.finalize()
        treemesh_2_octree(workspace, treemesh, name="Octree_Mesh")
        strip = workspace.get_entity("Surface strip")[0]
        assert np.allclose(strip.extent, [[-60, -10, 0], [60, 10, 0]])


def test_create_octree_curve(tmp_path: Path, setup_test_octree):  # pylint: disable=too-many-locals
    (locations, refinement, _, params_dict) = setup_test_octree

    with Workspace.create(tmp_path / f"{__name__}.geoh5") as workspace:
        curve = Curve.create(workspace, vertices=locations)
        curve.remove_cells([-1])

        params_dict.update(
            {
                "geoh5": workspace,
                "objects": curve,
                "refinements": [
                    {
                        "refinement_object": curve,
                        "levels": refinement,
                    }
                ],
            }
        )
        params = OctreeOptions(**params_dict)
        params.write_ui_json(tmp_path / "testOctree.ui.json")
        driver = OctreeDriver(params)
        driver.run()

        results = driver.params.geoh5.get_entity("Octree Mesh")
        assert results[0].n_cells == 177230


def test_create_octree_empty_curve(tmp_path: Path, setup_test_octree):  # pylint: disable=too-many-locals
    (locations, refinement, _, params_dict) = setup_test_octree

    with Workspace.create(tmp_path / f"{__name__}.geoh5") as workspace:
        # Create sources along line
        extent = Points.create(workspace, vertices=locations)
        curve = Curve.create(workspace, vertices=[(0, 0, 0), (0, 0, 0)])
        curve.remove_cells([0])

        params_dict.update(
            {
                "geoh5": workspace,
                "objects": extent,
                "minimum_level": 10,
                "refinements": [
                    {
                        "refinement_object": curve,
                        "levels": refinement,
                    }
                ],
            }
        )
        params = OctreeOptions(**params_dict)
        params.write_ui_json(tmp_path / "testOctree.ui.json")
        driver = OctreeDriver(params)
        driver.run()

        results = driver.params.geoh5.get_entity("Octree Mesh")[0]
        assert isinstance(results, Octree)
        assert results.n_cells == 4


def test_create_octree_dipoles(tmp_path: Path, setup_test_octree):  # pylint: disable=too-many-locals
    (_, refinement, _, params_dict) = setup_test_octree

    n_data = 12
    with Workspace.create(tmp_path / f"{__name__}.geoh5") as workspace:
        # Create sources along line
        x_loc, y_loc = np.meshgrid(np.arange(n_data), np.arange(-1, 3))
        vertices = np.c_[x_loc.ravel(), y_loc.ravel(), np.zeros_like(x_loc).ravel()]
        parts = np.kron(np.arange(4), np.ones(n_data)).astype("int")
        currents = CurrentElectrode.create(workspace, vertices=vertices, parts=parts)
        currents.add_default_ab_cell_id()

        n_dipoles = 9
        dipoles = []
        current_id = []
        for val in currents.ab_cell_id.values:
            cell_id = int(currents.ab_map[val]) - 1

            for dipole in range(n_dipoles):
                dipole_ids = currents.cells[cell_id, :] + 2 + dipole

                if (
                    any(dipole_ids > (len(vertices) - 1))
                    or len(np.unique(parts[dipole_ids])) > 1
                ):
                    continue

                dipoles += [dipole_ids]
                current_id += [val]

        potentials = PotentialElectrode.create(
            workspace,
            vertices=vertices,
            cells=np.vstack(dipoles).astype("uint32"),
        )
        potentials.ab_cell_id = np.hstack(current_id).astype("int32")
        potentials.current_electrodes = currents
        params_dict.update(
            {
                "geoh5": workspace,
                "objects": potentials,
                "refinements": [
                    {
                        "refinement_object": potentials,
                        "levels": refinement,
                    }
                ],
            }
        )
        params = OctreeOptions(**params_dict)
        params.write_ui_json(tmp_path / "testOctree.ui.json")
        driver = OctreeDriver(params)
        driver.run()

        assert driver.params.geoh5.get_entity("Octree Mesh")[0]


def test_create_octree_triangulation(tmp_path: Path, setup_test_octree):  # pylint: disable=too-many-locals
    (locations, refinement, _, params_dict) = setup_test_octree

    # Generate a sphere of points
    phi, theta = np.meshgrid(
        np.linspace(-np.pi / 2.0, np.pi / 2.0, 32), np.linspace(-np.pi, np.pi, 32)
    )
    surf = Delaunay(np.c_[phi.flatten(), theta.flatten()])
    x = np.cos(phi) * np.cos(theta) * 200.0
    y = np.cos(phi) * np.sin(theta) * 200.0
    z = np.sin(phi) * 200.0
    # refinement = "1, 2"
    with Workspace.create(tmp_path / f"{__name__}.geoh5") as workspace:
        curve = Curve.create(workspace, vertices=locations)
        sphere = Surface.create(
            workspace,
            vertices=np.c_[x.flatten(), y.flatten(), z.flatten()],
            cells=surf.simplices,  # pylint: disable=no-member
        )
        params_dict.update(
            {
                "geoh5": workspace,
                "objects": curve,
                "refinements": [
                    {
                        "refinement_object": sphere,
                        "levels": refinement,
                    }
                ],
            }
        )
        params = OctreeOptions(**params_dict)
        params.write_ui_json(tmp_path / "testOctree.ui.json")
        driver = OctreeDriver(params)
        driver.run()

        rec_octree = workspace.get_entity("Octree Mesh")[0]
        assert rec_octree.n_cells == 301788


@pytest.mark.parametrize(
    "diagonal_balance, exp_values, exp_counts",
    [(True, [0, 1], [22, 10]), (False, [0, 1, 2], [22, 8, 2])],
)
def test_octree_diagonal_balance(  # pylint: disable=too-many-locals
    tmp_path: Path, diagonal_balance, exp_values, exp_counts
):
    with Workspace.create(tmp_path / "testDiagonalBalance.geoh5") as workspace:
        point = [125, 0, 125]
        points = Points.create(
            workspace, vertices=np.array([[150, 0, 150], [200, 0, 200], point])
        )

        # Repeat the creation using the app
        params_dict = {
            "geoh5": workspace,
            "objects": points,
            "u_cell_size": 10.0,
            "v_cell_size": 10.0,
            "w_cell_size": 10.0,
            "horizontal_padding": 500.0,
            "vertical_padding": 200.0,
            "depth_core": 400.0,
            "minimum_level": 4,
            "refinements": [
                {
                    "refinement_object": points,
                    "levels": 1,
                    "horizon": False,
                    "distance": 1000.0,
                }
            ],
        }

        params = OctreeOptions(**params_dict, diagonal_balance=diagonal_balance)

        filename = "diag_balance.ui.json"

        params.write_ui_json(tmp_path / filename)

    OctreeDriver.start(tmp_path / filename)

    with workspace.open(mode="r"):
        results = []
        mesh_obj = workspace.get_entity("Octree Mesh")[0]

        assert isinstance(mesh_obj, Octree)

        treemesh = octree_2_treemesh(mesh_obj)
        assert treemesh is not None

        ind = treemesh.get_containing_cells(point)
        starting_cell = treemesh[ind]

        level = starting_cell._level  # pylint: disable=protected-access
        for first_neighbor in starting_cell.neighbors:
            neighbors = []
            for neighbor in treemesh[first_neighbor].neighbors:
                if isinstance(neighbor, list):
                    neighbors += neighbor
                else:
                    neighbors.append(neighbor)

            for second_neighbor in neighbors:
                compare_cell = treemesh[second_neighbor]
                if set(starting_cell.nodes) & set(compare_cell.nodes):
                    results.append(
                        np.abs(
                            level - compare_cell._level  # pylint: disable=protected-access
                        )
                    )

        values, counts = np.unique(results, return_counts=True)

        assert (values == np.array(exp_values)).all()
        assert (counts == np.array(exp_counts)).all()


def test_refine_complement(tmp_path: Path, setup_test_octree):  # pylint: disable=too-many-locals
    (locations, refinement, _, params_dict) = setup_test_octree

    with Workspace.create(tmp_path / f"{__name__}.geoh5") as workspace:
        points = Points.create(workspace, vertices=np.c_[locations[-1, :]].T)
        curve = Curve.create(workspace, vertices=locations)
        curve.remove_cells([-1])
        curve.complement = points
        points.complement = curve

        params_dict.update(
            {
                "geoh5": workspace,
                "objects": curve,
                "refinements": [
                    {
                        "refinement_object": curve,
                        "levels": refinement,
                        "horizon": False,
                    }
                ],
            }
        )
        params = OctreeOptions(**params_dict)
        params.write_ui_json(tmp_path / "testOctree.ui.json")
        driver = OctreeDriver(params)
        driver.run()

        rec_octree = workspace.get_entity("Octree Mesh")[0]
        treemesh = octree_2_treemesh(rec_octree)
        assert isinstance(treemesh, TreeMesh)

        # center of curve should be refined because of point complement
        ind = treemesh.get_containing_cells(np.array([[0.0, 0.0, 0.0]]))
        assert all(k == 5 for k in treemesh[ind].h)
        # between curve and point complement should be > base cell size
        ind = treemesh.get_containing_cells(np.array([[100.0, 0.0, 0.0]]))
        assert all(k == 20 for k in treemesh[ind].h)
        # along curve path should be base cell size
        point = np.mean(locations[1:3, :], axis=0)
        ind = treemesh.get_containing_cells(point)
        assert all(k == 5 for k in treemesh[ind].h)


def test_regular_grid(tmp_path: Path, setup_test_octree):  # pylint: disable=too-many-locals
    (_, refinement, _, params_dict) = setup_test_octree

    x, y = np.meshgrid(
        np.arange(0, 100, 5) + np.random.randn(1),
        np.arange(0, 100, 5) + np.random.randn(1),
    )
    locations = np.c_[x.flatten(), y.flatten(), np.ones(400) * np.random.randn(1)]

    with Workspace.create(tmp_path / f"{__name__}.geoh5") as workspace:
        points = Points.create(workspace, vertices=locations)

        params_dict.update(
            {
                "geoh5": workspace,
                "objects": points,
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
        params.write_ui_json(tmp_path / "testOctree.ui.json")
        driver = OctreeDriver(params)
        driver.run()

        rec_octree = workspace.get_entity("Octree Mesh")[0]

        treemesh = octree_2_treemesh(rec_octree)
        assert isinstance(treemesh, TreeMesh)
    # center of curve should be refined because of point complement
    ind = treemesh.get_containing_cells(locations)

    np.testing.assert_allclose(treemesh.cell_centers[ind], locations)


def test_flat_grid(tmp_path: Path, setup_test_octree):  # pylint: disable=too-many-locals
    (_, refinement, _, params_dict) = setup_test_octree

    locations = np.c_[
        np.linspace(-100, 100, 16),
        np.linspace(-100, 100, 16),
        np.r_[np.ones(7) * 5, np.ones(9) * 10],
    ]

    with Workspace.create(tmp_path / f"{__name__}.geoh5") as workspace:
        points = Points.create(workspace, vertices=locations)
        params_dict.update(
            {
                "geoh5": workspace,
                "objects": points,
                "refinements": [
                    {
                        "refinement_object": points,
                        "levels": refinement,
                        "horizon": False,
                    }
                ],
                "depth_core": 10.0,
                "vertical_padding": 0,
            }
        )
        params = OctreeOptions(**params_dict)
        driver = OctreeDriver(params)
        octree = driver.run()

        assert (octree.origin["z"] + octree.w_cell_size * octree.w_count) > locations[
            :, 2
        ].max()
