# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2025 Mira Geoscience Ltd.                                     '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of the MIT License       '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from __future__ import annotations

from logging import warning

import numpy as np
from discretize import TensorMesh, TreeMesh
from geoh5py import Workspace
from geoh5py.objects import BlockModel, Curve, ObjectBase, Octree, Points
from geoh5py.ui_json.utils import fetch_active_workspace
from scipy.interpolate import interp1d
from scipy.spatial import cKDTree


def block_model_to_discretize(
    entity: BlockModel,
) -> TensorMesh | tuple[TensorMesh, np.ndarray]:
    """
    Convert a block model to a discretize.TensorMesh.

    :param entity: The block model to convert.
    """
    if not isinstance(entity, BlockModel):
        raise TypeError("entity must be an instance of BlockModel.")

    origin = [
        entity.origin["x"] + entity.u_cells[entity.u_cells < 0].sum(),
        entity.origin["y"] + entity.v_cells[entity.v_cells < 0].sum(),
        entity.origin["z"] + entity.z_cells[entity.z_cells < 0].sum(),
    ]
    mesh = TensorMesh(
        [
            np.abs(entity.u_cells),
            np.abs(entity.v_cells),
            np.abs(entity.z_cells[::-1]),
        ],
        x0=origin,
    )
    return mesh


def boundary_value_indices(
    mesh: TensorMesh | TreeMesh, values: np.ndarray, target: float | int
) -> np.ndarray:
    """
    Get a mask of the boundary cells in a mesh based on a target value.

    :param mesh: The discretize mesh.
    :param values: The values associated with the cells.
    :param target: The target value to identify boundary cells.

    :return: Mask of boundary cells.
    """
    if not isinstance(mesh, TensorMesh | TreeMesh):
        raise TypeError("Mesh must be an instance of TensorMesh or TreeMesh.")

    if not isinstance(values, np.ndarray):
        raise TypeError("Values must be a numpy array.")

    if target is np.nan:
        is_target = np.isnan(values)
    else:
        is_target = values == target

    on_face = (mesh.cell_gradient @ is_target).astype(bool)
    boundary_cells = (mesh.average_face_to_cell @ on_face).astype(bool)

    return boundary_cells


def collocate_octrees(global_mesh: Octree, local_meshes: list[Octree]):
    """
    Collocate a list of octree meshes into a global octree mesh.

    :param global_mesh: Global octree mesh.
    :param local_meshes: List of local octree meshes.
    """
    attributes = get_octree_attributes(global_mesh)
    cell_size = attributes["cell_size"]

    if (
        global_mesh.octree_cells is None
        or global_mesh.u_cell_size is None
        or global_mesh.v_cell_size is None
        or global_mesh.w_cell_size is None
    ):
        raise ValueError("Global mesh must have octree_cells and cell sizes.")

    u_grid = global_mesh.octree_cells["I"] * global_mesh.u_cell_size
    v_grid = global_mesh.octree_cells["J"] * global_mesh.v_cell_size
    w_grid = global_mesh.octree_cells["K"] * global_mesh.w_cell_size

    xyz = np.c_[u_grid, v_grid, w_grid] + attributes["origin"]
    tree = cKDTree(xyz)

    for local_mesh in local_meshes:
        attributes = get_octree_attributes(local_mesh)

        if cell_size and cell_size != attributes["cell_size"]:
            raise ValueError(
                f"Cell size mismatch in dimension {cell_size} != {attributes['cell_size']}"
            )

        _, closest = tree.query(attributes["origin"])
        shift = xyz[closest, :] - attributes["origin"]

        if np.any(shift != 0.0):
            with fetch_active_workspace(local_mesh.workspace) as workspace:
                warning(
                    f"Shifting {local_mesh.name} mesh origin by {shift} m to match inversion mesh."
                )
                local_mesh.origin = attributes["origin"] + shift
                workspace.update_attribute(local_mesh, "attributes")


def create_octree_from_octrees(meshes: list[Octree | TreeMesh]) -> TreeMesh:
    """
    Create an all encompassing octree mesh from a list of meshes.

    :param meshes: List of Octree or TreeMesh meshes.

    :return octree: A global Octree.
    """
    cell_size = []
    dimensions = None
    origin = None

    for mesh in meshes:
        attributes = get_octree_attributes(mesh)

        if dimensions is None:
            dimensions = attributes["dimensions"]
        elif not np.allclose(dimensions, attributes["dimensions"]):
            raise ValueError("Meshes must have same dimensions")

        if origin is None:
            origin = attributes["origin"]
        elif not np.allclose(origin, attributes["origin"]):
            raise ValueError("Meshes must have same origin")

        cell_size.append(attributes["cell_size"])

    cell_size = np.min(np.vstack(cell_size), axis=0)
    cells = []
    for ind in range(3):
        if dimensions is not None and cell_size is not None:
            extent = dimensions[ind]
            max_level = int(np.ceil(np.log2(np.abs(extent / cell_size[ind]))))
            cells += [np.ones(2**max_level) * cell_size[ind]]

    # Define the mesh and origin
    treemesh = TreeMesh(cells, origin=origin, diagonal_balance=False)

    for mesh in meshes:
        if isinstance(mesh, Octree) and mesh.octree_cells is not None:
            centers = mesh.centroids
            levels = treemesh.max_level - np.log2(mesh.octree_cells["NCells"])
        elif isinstance(mesh, TreeMesh) and mesh.cell_centers is not None:
            centers = mesh.cell_centers
            levels = (
                treemesh.max_level
                - mesh.max_level
                + mesh.cell_levels_by_index(np.arange(mesh.nC))
            )
        else:
            raise TypeError(
                f"All meshes must be Octree or TreeMesh, not {type(mesh)} "
                "and must have octree cells defined."
            )

        treemesh.insert_cells(centers, levels, finalize=False)

    treemesh.finalize()

    return treemesh


def densify_curve(curve: Curve, increment: float) -> np.ndarray:
    """
    Refine a curve by adding points along the curve at a given increment.

    :param curve: Curve object to be refined.
    :param increment: Distance between points along the curve.

    :return: Array of shape (n, 3) of x, y, z locations.
    """
    locations = []
    for part in curve.unique_parts:
        if curve.cells is None or curve.vertices is None:
            continue

        logic = curve.parts == part
        cells = curve.cells[np.all(logic[curve.cells], axis=1)]

        if len(cells) == 0:
            continue

        vert_ind = np.r_[cells[:, 0], cells[-1, 1]]
        locs = curve.vertices[vert_ind, :]
        locations.append(resample_locations(locs, increment))

    if len(locations) == 0:
        return np.empty((0, 3))

    return np.vstack(locations)


def find_endpoints(points: np.ndarray) -> np.ndarray:
    """
    Find the endpoints of a co-linear array of points.

    :param points: locations array of shape (n, 3).
    """

    xmin = points[:, 0].min()
    xmax = points[:, 0].max()
    ymin = points[:, 1].min()
    ymax = points[:, 1].max()

    endpoints = []
    for x in np.unique([xmin, xmax]):
        for y in np.unique([ymin, ymax]):
            is_endy = np.isclose(points[:, :2], [x, y]).all(axis=1)
            if np.any(is_endy):
                endpoints.append(points[is_endy][0])

    return np.array(endpoints)


def get_neighbouring_cells(mesh: TreeMesh, indices: list | np.ndarray) -> tuple:
    """
    Get the indices of neighbouring cells along a given axis for a given list of
    cell indices.

    :param mesh: discretize.TreeMesh object.
    :param indices: List of cell indices.

    :return: Two lists of neighbouring cell indices for every axis.
        axis[0] = (west, east)
        axis[1] = (south, north)
        axis[2] = (down, up)
    """
    if not isinstance(indices, list | np.ndarray):
        raise TypeError("Input 'indices' must be a list or numpy.ndarray of indices.")

    if not isinstance(mesh, TreeMesh):
        raise TypeError("Input 'mesh' must be a discretize.TreeMesh object.")

    neighbors: dict[int, list] = {ax: [[], []] for ax in range(mesh.dim)}

    for ind in indices:
        for ax in range(mesh.dim):
            neighbors[ax][0].append(np.r_[mesh[ind].neighbors[ax * 2]])
            neighbors[ax][1].append(np.r_[mesh[ind].neighbors[ax * 2 + 1]])

    return tuple(
        (np.r_[tuple(neighbors[ax][0])], np.r_[tuple(neighbors[ax][1])])
        for ax in range(mesh.dim)
    )


def get_octree_attributes(mesh: Octree | TreeMesh) -> dict[str, list]:
    """
    Get mesh attributes.

    :param mesh: Input Octree or TreeMesh object.
    :return mesh_attributes: Dictionary of mesh attributes.
    """
    if not isinstance(mesh, Octree | TreeMesh):
        raise TypeError(f"All meshes must be Octree or TreeMesh, not {type(mesh)}")

    cell_size = []
    cell_count = []
    dimensions = []
    if isinstance(mesh, TreeMesh):
        for int_dim in range(3):
            cell_size.append(mesh.h[int_dim][0])
            cell_count.append(mesh.h[int_dim].size)
            dimensions.append(mesh.h[int_dim].sum())
        origin = mesh.origin
    else:
        with fetch_active_workspace(mesh.workspace):
            for str_dim in "uvw":
                cell_size.append(getattr(mesh, f"{str_dim}_cell_size"))
                cell_count.append(getattr(mesh, f"{str_dim}_count"))
                dimensions.append(
                    getattr(mesh, f"{str_dim}_cell_size")
                    * getattr(mesh, f"{str_dim}_count")
                )
            origin = np.r_[mesh.origin["x"], mesh.origin["y"], mesh.origin["z"]]

    extent = np.r_[origin, origin + np.r_[dimensions]]

    return {
        "cell_count": cell_count,
        "cell_size": cell_size,
        "dimensions": dimensions,
        "extent": extent,
        "origin": origin,
    }


def octree_2_treemesh(  # pylint: disable=too-many-locals
    mesh: Octree,
) -> TreeMesh | None:
    """
    Convert a geoh5 octree mesh to discretize.TreeMesh

    Modified code from module discretize.TreeMesh.readUBC function.

    :param mesh: Octree mesh to convert.

    :return: Resulting TreeMesh.
    """
    if (
        mesh.octree_cells is None
        or mesh.u_count is None
        or mesh.v_count is None
        or mesh.w_count is None
    ):
        return None

    n_cell_dim, cell_sizes = [], []
    for ax in "uvw":
        if (
            getattr(mesh, f"{ax}_cell_size") is None
            or getattr(mesh, f"{ax}_count") is None
        ):
            raise ValueError(f"Cell size in {ax} direction is not defined.")

        n_cell_dim.append(getattr(mesh, f"{ax}_count"))
        cell_sizes.append(
            np.ones(getattr(mesh, f"{ax}_count")) * getattr(mesh, f"{ax}_cell_size")
        )

    if any(np.any(cell_size < 0) for cell_size in cell_sizes):
        raise NotImplementedError("Negative cell sizes not supported.")

    ls = np.log2(n_cell_dim).astype(int)

    if len(set(ls)) == 1:
        max_level = ls[0]
    else:
        max_level = min(ls) + 1

    cells = np.vstack(mesh.octree_cells.tolist())
    indexes = cells[:, :-1] * 2 + cells[:, -1][:, None]  # convert to cpp index
    levels = max_level - np.log2(cells[:, -1])
    treemesh = TreeMesh(
        cell_sizes, x0=np.asarray(mesh.origin.tolist()), diagonal_balance=False
    )
    treemesh.__setstate__((indexes, levels))

    return treemesh


def resample_locations(locations: np.ndarray, increment: float) -> np.ndarray:
    """
    Resample locations along a sequence of positions at a given increment.

    :param locations: Array of shape (n, 3) of x, y, z locations.
    :param increment: Minimum distance between points along the curve.

    :return: Array of shape (n, 3) of x, y, z locations.
    """
    distance = np.cumsum(
        np.r_[0, np.linalg.norm(locations[1:, :] - locations[:-1, :], axis=1)]
    )
    new_distances = np.sort(
        np.unique(np.r_[distance, np.arange(0, distance[-1], increment)])
    )

    resampled = []
    for axis in locations.T:
        interpolator = interp1d(distance, axis, kind="linear")
        resampled.append(interpolator(new_distances))

    return np.c_[resampled].T


def surface_strip(
    points: ObjectBase, width: float, name: str = "Surface strip"
) -> Points:
    """
    Duplicate and offset co-linear input points to create a co-planar strip.

    :param points: Points object whose locations are all co-linear.
    :param width: Width used to displace existing points to create the
        strip.  The surrounding strip will be 2*width wider and longer than
        the input points.
    :param name: Name of the new Points objects.
    """

    assert points.locations is not None

    locs = points.locations
    ends = find_endpoints(locs)
    colinear = np.diff(ends[:, :2], axis=0)[0]
    colinear = colinear / np.linalg.norm(colinear)

    # Gram-Schmidt
    orthogonal = np.random.randn(2)
    orthogonal -= orthogonal.dot(colinear) * colinear
    orthogonal /= np.linalg.norm(orthogonal)

    vertices = np.vstack(
        [
            locs,
            np.r_[ends[1, :2] + width * colinear, ends[1, 2]],
            np.r_[ends[0, :2] - width * colinear, ends[0, 2]],
        ]
    )

    vertices = np.vstack(
        [
            vertices,
            np.c_[vertices[:, :2] + width * orthogonal, vertices[:, 2]],
            np.c_[vertices[:, :2] - width * orthogonal, vertices[:, 2]],
        ]
    )

    return Points.create(points.workspace, vertices=vertices, name=name)


def tensor_mesh_ordering(
    entity: BlockModel,
) -> np.ndarray:
    """
    Map the ordering of cell-based data from geoh5py.BlockModel to discretize.TensorMesh.

    :param entity: The mesh to order.

    :return indices: Array of indices to reorder cell-based values.
    """
    if not isinstance(entity, BlockModel):
        raise TypeError("mesh must be an instance of BlockModel.")

    indices = np.arange(entity.n_cells)
    indices = indices.reshape(
        (
            entity.shape[2],
            entity.shape[0],
            entity.shape[1],
        ),
        order="F",
    )

    if entity.z_cells[0] < 0:
        indices = indices[::-1, :, :]

    indices = indices.transpose((1, 2, 0)).flatten(order="F")

    return indices


def treemesh_2_octree(workspace: Workspace, treemesh: TreeMesh, **kwargs) -> Octree:
    """
    Converts a :obj:`discretize.TreeMesh` to :obj:`geoh5py.objects.Octree` entity.

    :param workspace: Workspace to create the octree in.
    :param treemesh: TreeMesh to convert.

    :return: Octree entity.
    """

    if any(np.any(cell_size < 0) for cell_size in treemesh.h):
        raise NotImplementedError("Negative cell sizes not supported.")

    index_array = np.asarray(treemesh.cell_state["indexes"])
    levels = np.asarray(treemesh.cell_state["levels"])

    new_levels = 2 ** (treemesh.max_level - levels)
    new_index_array = (index_array - new_levels[:, None]) / 2

    origin = treemesh.x0.copy()

    mesh_object = Octree.create(
        workspace,
        origin=origin,
        u_count=treemesh.h[0].size,
        v_count=treemesh.h[1].size,
        w_count=treemesh.h[2].size,
        u_cell_size=treemesh.h[0][0],
        v_cell_size=treemesh.h[1][0],
        w_cell_size=treemesh.h[2][0],
        octree_cells=np.c_[new_index_array, new_levels],
        **kwargs,
    )

    return mesh_object
