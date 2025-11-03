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
import pytest
from discretize import TreeMesh
from geoh5py import Workspace
from geoh5py.objects import BlockModel, Curve, Octree, Points
from pytest import raises

from grid_apps.block_models.driver import Driver as BlockModelDriver
from grid_apps.utils import (
    block_model_to_discretize,
    boundary_value_indices,
    collocate_octrees,
    create_octree_from_octrees,
    densify_curve,
    find_endpoints,
    get_neighbouring_cells,
    get_octree_attributes,
    octree_2_treemesh,
    surface_strip,
    tensor_mesh_ordering,
    treemesh_2_octree,
)


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


def test_tensor_boundary_value_indices(tmp_path):
    # Create a test block model
    h5file_path = tmp_path / f"{__name__}.geoh5"
    with Workspace.create(h5file_path) as workspace:
        block = BlockModel.create(
            workspace,
            u_cell_delimiters=np.cumsum(np.ones(16)),
            v_cell_delimiters=np.cumsum(np.ones(16)),
            z_cell_delimiters=np.cumsum(np.ones(16)),
        )

        tensor = block_model_to_discretize(block)

        values = np.ones(tensor.n_cells)
        values[int(tensor.n_cells / 2)] = 2

        indices = boundary_value_indices(tensor, values, 2)

        assert indices.sum() == 7

        # Just for visual validation
        block.add_data(
            {
                "boundary_indices": {
                    "values": indices[np.argsort(tensor_mesh_ordering(block))],
                }
            }
        )


def test_octree_boundary_value_indices(tmp_path):
    treemesh = TreeMesh([16, 16, 16])
    treemesh.refine(4, finalize=True)
    values = np.ones(treemesh.n_cells)
    values[7] = 2

    with pytest.raises(TypeError, match="Mesh must be an instance"):
        indices = boundary_value_indices("abc", values, 2)

    with pytest.raises(TypeError, match="Values must be a numpy array"):
        indices = boundary_value_indices(treemesh, 123, 2)

    indices = boundary_value_indices(treemesh, values, 2)
    h5file_path = tmp_path / f"{__name__}.geoh5"
    with Workspace.create(h5file_path) as workspace:
        octree = treemesh_2_octree(workspace, treemesh, name="TestOctree")
        octree.add_data(
            {
                "boundary_indices": {
                    "values": indices,
                }
            }
        )

    assert indices.sum() == 7


def test_find_endpoints():
    locs = np.array([[-1, -1, 0], [0, 0, 0], [1, 1, 0]])
    endpoints = find_endpoints(locs)
    assert np.allclose(endpoints, np.array([[-1, -1, 0], [1, 1, 0]]))
    locs = np.array([[-1, 1, 0], [0, 0, 0], [1, -1, 0]])
    endpoints = find_endpoints(locs)
    assert np.allclose(endpoints, np.array([[-1, 1, 0], [1, -1, 0]]))
    locs = np.array([[0, -1, 0], [0, 0, 0], [0, 1, 0]])
    endpoints = find_endpoints(locs)
    assert np.allclose(endpoints, np.array([[0, -1, 0], [0, 1, 0]]))
    locs = np.array([[-1, 0, 0], [0, 0, 0], [1, 0, 0]])
    endpoints = find_endpoints(locs)
    assert np.allclose(endpoints, np.array([[-1, 0, 0], [1, 0, 0]]))


def test_surface_strip(tmp_path):
    with Workspace.create(tmp_path / "test.geoh5") as workspace:
        line = Points.create(
            workspace, vertices=np.array([[-1, 0, 0], [0, 0, 0], [1, 0, 0]])
        )
        strip = surface_strip(line, 1)
        assert strip.extent is not None
        assert np.allclose(strip.extent, np.array([[-2, -1, 0], [2, 1, 0]]))


def test_not_implemented_negative():
    workspace = Workspace()

    local_mesh1 = TreeMesh(
        [[10] * 16, [10] * 16, [-10] * 16], [1000, 0, 0], diagonal_balance=True
    )
    local_mesh1.refine(3, finalize=True)

    with pytest.raises(
        NotImplementedError, match=r"Negative cell sizes not supported\."
    ):
        treemesh_2_octree(workspace, local_mesh1)

    octree = Octree.create(
        workspace,
        origin=[0, 0, 0],
        u_count=8,
        v_count=8,
        w_count=8,
        u_cell_size=-5.0,
        v_cell_size=5.0,
        w_cell_size=5.0,
    )

    with pytest.raises(
        NotImplementedError, match=r"Negative cell sizes not supported\."
    ):
        octree_2_treemesh(octree)


def test_collocate_octrees(tmp_path: Path):
    with Workspace.create(tmp_path / "test.geoh5") as workspace:
        local_mesh1 = TreeMesh(
            [[10] * 16, [10] * 16, [10] * 16], [1000, 0, 0], diagonal_balance=True
        )
        local_mesh1.insert_cells([120, 120, -40], local_mesh1.max_level, finalize=True)
        local_omesh1 = treemesh_2_octree(workspace, local_mesh1)

        local_mesh2 = TreeMesh(
            [[10] * 16, [10] * 16, [10] * 16], [-500, 500, -500], diagonal_balance=True
        )
        local_mesh2.insert_cells([40, 40, -120], local_mesh2.max_level, finalize=True)
        local_omesh2 = treemesh_2_octree(workspace, local_mesh2)

        global_mesh = TreeMesh(
            [[10] * 16, [10] * 16, [10] * 16], [0, 0, 0], diagonal_balance=True
        )
        global_mesh.insert_cells([620, 300, -300], global_mesh.max_level, finalize=True)
        global_omesh = treemesh_2_octree(workspace, global_mesh)

        original_global_extent = global_omesh.extent

        # Bounds do not overlap initially
        for mesh in [local_omesh1, local_omesh2]:
            if mesh.extent is not None and original_global_extent is not None:
                for i in range(3):
                    assert (mesh.extent[0][i] >= original_global_extent[0][i]) or (
                        mesh.extent[1][i] <= original_global_extent[1][i]
                    )

        # Collocate octrees
        collocate_octrees(global_omesh, [local_omesh1, local_omesh2])
        global_extent = global_omesh.extent
        assert np.all(global_extent == original_global_extent)

        # Check that bounds overlap
        for mesh in [local_omesh1, local_omesh2]:
            if mesh.extent is not None and global_extent is not None:
                for i in range(3):
                    assert (mesh.extent[0][i] >= global_extent[0][i]) or (
                        mesh.extent[1][i] <= global_extent[1][i]
                    )


def test_create_octree_from_octrees():
    workspace = Workspace()
    mesh1 = TreeMesh(
        [[10] * 16, [10] * 16, [10] * 16], [0, 0, 0], diagonal_balance=False
    )
    mesh1.insert_cells([120, 120, -40], mesh1.max_level, finalize=True)
    omesh1 = treemesh_2_octree(workspace, mesh1)

    mesh2 = TreeMesh(
        [[10] * 16, [10] * 16, [10] * 16], [0, 0, 0], diagonal_balance=False
    )
    mesh2.insert_cells([40, 40, -120], mesh2.max_level, finalize=True)
    omesh2 = treemesh_2_octree(workspace, mesh2)

    assert omesh1.n_cells == omesh2.n_cells == 57

    # Create mesh from octrees
    resulting_mesh = create_octree_from_octrees([omesh1, omesh2])
    resulting_omesh = treemesh_2_octree(workspace, resulting_mesh)

    in_both = []
    for cell in resulting_omesh.centroids:
        in_mesh1 = np.any(np.all(cell == omesh1.centroids, axis=1))
        in_mesh2 = np.any(np.all(cell == omesh2.centroids, axis=1))
        in_both.append(in_mesh1 or in_mesh2)

    assert np.all(in_both)

    # Compare with mesh from treemeshes
    new_mesh = create_octree_from_octrees([mesh1, mesh2])

    assert [np.all(new_mesh.h[dim] == resulting_mesh.h[dim]) for dim in range(3)]
    assert np.all(new_mesh.shape_cells == resulting_mesh.shape_cells)
    assert np.all(new_mesh.origin == resulting_mesh.origin)


def test_create_octree_from_octrees_errors():
    workspace = Workspace()
    mesh = TreeMesh([[10] * 16, [10] * 16, [10] * 16], [0, 0, 0], diagonal_balance=True)
    mesh.insert_cells([120, 120, -40], mesh.max_level, finalize=True)
    omesh = treemesh_2_octree(workspace, mesh)

    mesh_invalid_dimension = TreeMesh(
        [[10] * 16, [10] * 32, [10] * 16], [0, 0, 0], diagonal_balance=True
    )
    mesh_invalid_dimension.insert_cells(
        [40, 40, -120], mesh_invalid_dimension.max_level, finalize=True
    )
    omesh_invalid_dimension = treemesh_2_octree(workspace, mesh_invalid_dimension)

    mesh_invalid_origin = TreeMesh(
        [[10] * 16, [10] * 16, [10] * 16], [1, 0, 0], diagonal_balance=True
    )
    mesh_invalid_origin.insert_cells(
        [40, 40, -120], mesh_invalid_origin.max_level, finalize=True
    )
    omesh_invalid_origin = treemesh_2_octree(workspace, mesh_invalid_origin)

    with pytest.raises(ValueError, match="Meshes must have same dimensions"):
        create_octree_from_octrees([omesh, omesh_invalid_dimension])

    with pytest.raises(ValueError, match="Meshes must have same origin"):
        create_octree_from_octrees([omesh, omesh_invalid_origin])


def test_densify_curve(tmp_path: Path):
    with Workspace.create(tmp_path / "test.geoh5") as workspace:
        curve = Curve.create(
            workspace,
            vertices=np.vstack([[0, 0, 0], [10, 0, 0], [10, 10, 0]]),
            name="test_curve",
        )
        locations = densify_curve(curve, 2)
        assert locations.shape[0] == 11


def test_get_neighbouring_cells():
    """
    Check that the neighbouring cells are correctly identified and output
    of the right shape.
    """
    mesh = TreeMesh(
        [[10] * 16, [10] * 16, [10] * 16], [0, 0, 0], diagonal_balance=False
    )
    mesh.insert_cells([100, 100, 100], mesh.max_level, finalize=True)
    ind = mesh.get_containing_cells([95.0, 95.0, 95.0])

    with pytest.raises(
        TypeError, match=r"Input 'indices' must be a list or numpy.ndarray of indices\."
    ):
        get_neighbouring_cells(mesh, ind)

    with pytest.raises(
        TypeError, match=r"Input 'mesh' must be a discretize.TreeMesh object\."
    ):
        get_neighbouring_cells(1, [ind])

    neighbours = get_neighbouring_cells(mesh, [ind])

    assert len(neighbours) == 3, "Incorrect number of neighbours axes returned."
    assert all(len(axis) == 2 for axis in neighbours), (
        "Incorrect number of neighbours returned."
    )
    assert np.allclose(np.r_[neighbours].flatten(), np.r_[76, 78, 75, 79, 73, 81])


def test_get_octree_attributes_with_treemesh(setup_test_octree):
    _, _, treemesh, _ = setup_test_octree
    treemesh.insert_cells([0, 0, 0], treemesh.max_level, finalize=True)

    attributes = get_octree_attributes(treemesh)
    assert np.all(treemesh.origin == attributes["origin"])
    assert np.all(list(treemesh.shape_cells) == attributes["cell_count"])
    assert np.all(
        [treemesh.h[0][0], treemesh.h[1][0], treemesh.h[2][0]]
        == attributes["cell_size"]
    )
    assert [np.sum(cell_sizes) for cell_sizes in treemesh.h] == attributes["dimensions"]


def test_get_octree_attributes_with_octree(setup_test_octree):
    _, _, treemesh, _ = setup_test_octree
    treemesh.insert_cells([0, 0, 0], treemesh.max_level, finalize=True)

    workspace = Workspace()
    otree = treemesh_2_octree(workspace, treemesh)
    attributes = get_octree_attributes(otree)
    assert np.all(
        [otree.origin["x"], otree.origin["y"], otree.origin["z"]]
        == attributes["origin"]
    )
    assert np.all(
        [otree.u_count, otree.v_count, otree.w_count] == attributes["cell_count"]
    )

    if (
        otree.u_count is not None
        and otree.v_count is not None
        and otree.w_count is not None
        and otree.u_cell_size is not None
        and otree.v_cell_size is not None
        and otree.w_cell_size is not None
    ):
        assert [otree.u_cell_size, otree.v_cell_size, otree.w_cell_size] == attributes[
            "cell_size"
        ]
        assert np.all(
            [
                otree.u_count * otree.u_cell_size,
                otree.v_count * otree.v_cell_size,
                otree.w_count * otree.w_cell_size,
            ]
            == attributes["dimensions"]
        )


def test_octree_2_treemesh():
    with Workspace() as workspace:
        mesh = TreeMesh(
            [[10] * 4, [10] * 4, [10] * 4], [0, 0, 0], diagonal_balance=True
        )
        mesh.insert_cells([5, 5, 5], mesh.max_level, finalize=True)
        omesh = treemesh_2_octree(workspace, mesh)
        tmesh = octree_2_treemesh(omesh)
        assert tmesh is not None

        np.testing.assert_allclose(tmesh.cell_centers, mesh.cell_centers)


def test_roundtrip_octree_conversion(tmp_path):
    with Workspace.create(tmp_path / "test.geoh5") as workspace:
        points = np.vstack(
            [
                [10, 10, -10],
                [42, 21, -21],
            ]
        )
        Points.create(workspace, vertices=points)
        mesh = TreeMesh(
            [[10] * 16, [10] * 4, [10] * 8], [0, 0, 0], diagonal_balance=True
        )
        mesh.insert_cells(points, [mesh.max_level] * points.shape[0], finalize=True)
        omesh = treemesh_2_octree(workspace, mesh, name="first")

        np.testing.assert_allclose(mesh.cell_centers, omesh.centroids)

        mesh2 = octree_2_treemesh(omesh)
        assert mesh2 is not None

        np.testing.assert_allclose(mesh.cell_centers, mesh2.cell_centers)


def test_treemesh_2_octree(tmp_path: Path):
    with Workspace.create(tmp_path / "testTreemesh2Octree.geoh5") as workspace:
        mesh = TreeMesh(
            [[10] * 16, [10] * 4, [10] * 8], [0, 0, 0], diagonal_balance=True
        )
        mesh.insert_cells([10, 10, 10], mesh.max_level, finalize=True)
        omesh = treemesh_2_octree(workspace, mesh, name="test_mesh")

        mesh_attrs = get_octree_attributes(mesh)
        omesh_attrs = get_octree_attributes(omesh)
        for key, value in mesh_attrs.items():
            assert np.all(value == omesh_attrs[key])

        assert omesh.n_cells == mesh.n_cells

        tmesh = octree_2_treemesh(omesh)
        assert tmesh is not None
        np.testing.assert_allclose(tmesh.cell_centers, mesh.cell_centers)
        np.testing.assert_allclose(omesh.centroids, mesh.cell_centers)
