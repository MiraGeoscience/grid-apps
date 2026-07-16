# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2026 Mira Geoscience Ltd.                                     '
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
from geoh5py.data import FloatData, ReferencedData
from geoh5py.objects import BlockModel, Curve, Grid2D, ObjectBase, Octree, Points
from geoh5py.ui_json.utils import fetch_active_workspace
from pydantic import ConfigDict, validate_call
from scipy.interpolate import interp1d
from scipy.sparse import find
from scipy.spatial import cKDTree


typed_call = validate_call(config=ConfigDict(arbitrary_types_allowed=True))


@typed_call
def block_model_to_tensor(
    entity: BlockModel,
) -> TensorMesh:
    """
    Convert a block model to a discretize.TensorMesh.

    :param entity: The block model to convert.

    :return: An equivalent TensorMesh object.
    """
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


@typed_call
def tensor_to_block_model(
    workspace: Workspace, mesh: TensorMesh, **kwargs
) -> BlockModel:
    """
    Convert a tensor mesh to a block model.

    :param workspace: Workspace to create the block model.
    :param mesh: Tensor mesh object from discretize
    :param kwargs: Extra parameters to pass to the block model.

    :return: BlockModel entity.
    """
    block_model = BlockModel.create(
        workspace,
        origin=[mesh.x0[0], mesh.x0[1], mesh.x0[2] + mesh.h[2].sum()],
        u_cell_delimiters=mesh.nodes_x - mesh.x0[0],
        v_cell_delimiters=mesh.nodes_y - mesh.x0[1],
        z_cell_delimiters=-(mesh.x0[2] + mesh.h[2].sum() - mesh.nodes_z[::-1]),
        **kwargs,
    )
    return block_model


@typed_call
def tensor_to_grid2d(
    workspace: Workspace, mesh: TensorMesh, elevation: float = 0.0, **kwargs
) -> Grid2D:
    """
    Convert a tensor mesh to a 2D grid object.

    :param workspace: Workspace to create the block model.
    :param mesh: Tensor mesh object from discretize
    :param kwargs: Extra parameters to pass to the block model.

    :return: Grid2D entity.
    """
    grid = Grid2D.create(
        workspace,
        origin=[mesh.x0[0], mesh.x0[1], elevation],
        u_cell_size=np.mean(mesh.h[0]),
        v_cell_size=np.mean(mesh.h[1]),
        u_count=len(mesh.h[0]),
        v_count=len(mesh.h[1]),
        **kwargs,
    )
    return grid


@typed_call
def block_model_to_treemesh(
    entity: BlockModel, diagonal_balance=True, finalize=True
) -> TreeMesh:
    """
    Convert a block model to an octree mesh with the same base cell size and
    centered.

    :param entity: BlockModel object to be converted
    :param diagonal_balance: Whether to balance the mesh diagonally.
    :param finalize: Whether to finalize the treemesh after creation.

    :return: TreeMesh object.
    """
    origin = []
    octree_cells = []
    for ii, ax in zip("xyz", "uvz", strict=True):
        cell_sizes = np.abs(getattr(entity, f"{ax}_cells"))
        h_core = cell_sizes.min()

        # Compute number of octree cells to span the extent
        n_c = np.ceil(np.log2(np.sum(cell_sizes) / h_core))
        cell_sizes_octree = np.ones(int(2**n_c)) * h_core
        octree_cells.append(cell_sizes_octree)

        # Colocate the center of the octree with the center of the block model
        ind_core = np.where(np.isclose(cell_sizes, h_core, atol=1e-1))[0]
        center = (
            entity.origin[ii]
            + entity.local_axis_centers(ax)[ind_core[len(ind_core) // 2]]
        )

        axis_center = len(cell_sizes_octree) // 2
        origin.append(center - np.sum(cell_sizes_octree[:axis_center]) - h_core / 2)

    treemesh = TreeMesh(
        octree_cells,
        x0=origin,
        diagonal_balance=diagonal_balance,
    )

    if finalize:
        treemesh.finalize()

    return treemesh


@typed_call
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


@typed_call
def containing_cell_indices(mesh: TreeMesh | TensorMesh, locations: np.ndarray):
    """
    Return indices of cells containing the list of locations.

    Points that do not intersect return -1.

    :param mesh: Input discretize mesh object.
    :param locations: Input locations array.

    :return: Array of indices
    """
    if isinstance(mesh, TreeMesh):
        indices = mesh.get_containing_cells(locations)

    else:
        in_x = np.searchsorted(mesh.nodes_x, locations[:, 0]) - 1
        in_y = np.searchsorted(mesh.nodes_y, locations[:, 1]) - 1
        in_z = np.searchsorted(mesh.nodes_z, locations[:, 2]) - 1
        indices = (
            in_x
            + mesh.shape_cells[0] * in_y
            + in_z * mesh.shape_cells[0] * mesh.shape_cells[1]
        ).astype(int)

    indices[~mesh.is_inside(locations)] = -1

    return indices


@typed_call
def create_octree_from_octrees(meshes: list[Octree | TreeMesh]) -> TreeMesh:
    """
    Create an all encompassing octree mesh from a list of meshes.

    :param meshes: List of Octree or TreeMesh meshes.

    :return: An all-encompassing TreeMesh object
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
        treemesh = refine_tree_by_mesh(treemesh, mesh)

    treemesh.finalize()

    return treemesh


@typed_call
def refine_tree_by_mesh(
    tree: TreeMesh, mesh: TreeMesh | Octree | BlockModel, finalize: bool = False
) -> TreeMesh:
    """
    Given a TreeMesh, insert cells at the corresponding octree level.

    :param tree: TreeMesh to be refined.
    :param mesh: Input TreeMesh or Octree mesh to refine with.
    :param finalize: Whether to finalize the refined mesh.
    :return: Refined mesh.
    """
    if isinstance(mesh, BlockModel):
        treemesh = block_model_to_treemesh(mesh, finalize=False)
        mesh = refine_by_cell_volumes(treemesh, mesh)

    if isinstance(mesh, Octree) and mesh.octree_cells is not None:
        centers = mesh.centroids
        levels = tree.max_level - np.log2(mesh.octree_cells["NCells"])

    else:
        centers = mesh.cell_centers
        levels = (
            tree.max_level
            - mesh.max_level
            + mesh.cell_levels_by_index(np.arange(mesh.nC))
        )

    tree.insert_cells(centers, levels, finalize=finalize)

    return tree


@typed_call
def refine_by_cell_volumes(
    mesh: TreeMesh,
    entity: BlockModel,
    finalize: bool = True,
    mask: np.ndarray | None = None,
) -> TreeMesh:
    """
    Refine the octree mesh by the cell volumes of the block model.

    :param mesh: TreeMesh object to be refined.
    :param entity: BlockModel object to be used for refinement.
    :param finalize: Whether to finalize the treemesh after refinement.
    :param mask: Optional mask on the block model centroids to apply the refinement over.

    :return: TreeMesh object with refined levels.
    """
    tensor_oct_level = []
    for ax in "uvz":
        cell_sizes = np.abs(getattr(entity, f"{ax}_cells"))
        h_core = cell_sizes.min()
        # Find the core region
        tensor_oct_level.append(np.log2(cell_sizes / h_core).astype(int))

    e_x, e_y, e_z = np.meshgrid(*tensor_oct_level)
    max_level = np.c_[np.ravel(e_x), np.ravel(e_y), np.ravel(e_z)].max(axis=1)

    locations = entity.centroids
    if mask is not None:
        locations = locations[mask]
        max_level = max_level[mask]

    mesh.insert_cells(locations, mesh.max_level - max_level, finalize=finalize)

    return mesh


@typed_call
def refine_by_values(
    mesh: TreeMesh, data: FloatData | ReferencedData, finalize=True
) -> TreeMesh:
    """
    Increase the mesh resolution based on the gradient of data values.

    :param mesh: Input TreeMesh object.
    :param data: FloatData or ReferencedData object containing the values to
        be used for refinement.
    :param finalize: Whether to finalize the treemesh after refinement.

    :return: TreeMesh object with refined levels.
    """
    entity = data.parent

    if not isinstance(entity, BlockModel):
        raise TypeError("The parent of 'data' must be an instance of BlockModel.")

    tensor = block_model_to_tensor(entity)
    indices = tensor_mesh_ordering(entity)

    gradients = np.abs(tensor.cell_gradient @ data.values[indices])
    levels = np.zeros(gradients.shape, dtype=int)
    isnan = np.isnan(gradients)

    if isinstance(data, FloatData):
        actives = gradients[~isnan]
        bins = np.percentile(actives[actives > 0], np.linspace(5, 95, mesh.max_level))
        levels[~isnan] = np.searchsorted(bins, actives)
    else:
        levels[gradients > 0] = mesh.max_level

    # Refine on the value/nan interface, without boundary cells
    if any(isnan):
        horizon = get_boundary_active_cells(
            tensor, data.values[indices] == data.nan_value
        )
        mesh = refine_by_cell_volumes(
            mesh, entity, finalize=False, mask=horizon[np.argsort(indices)]
        )

    locs = tensor.average_cell_to_face @ tensor.cell_centers
    mesh.insert_cells(locs[~isnan], levels[~isnan].astype(int), finalize=finalize)

    return mesh


@typed_call
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

    :return: Array of shape (n, 2) containing the endpoints.
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


@typed_call
def get_boundary_active_cells(
    mesh: TreeMesh | TensorMesh,
    actives: np.ndarray,
    horizontal_edges: bool = False,
    vertical_edges: bool = False,
) -> np.ndarray:
    """
    Given a mesh and a set of active cells, return the active cells
    that are on the boundary of the active domain.

    :param mesh: Tree or TensorMesh object.
    :param actives: Bool array of active cells.
    :param horizontal_edges: Include the cells on the horizontal edges of the mesh.
    :param vertical_edges: Include the cells on the top and bottom edges of the mesh.

    :return: Bool array of boundary cells of the active domain.
    """
    if actives.ndim != 1 or actives.shape[0] != mesh.n_cells:
        raise ValueError("Input array 'actives' must have length mesh.n_cells.")

    is_face = np.zeros_like(actives, dtype=bool)

    # Find actives horizontal mesh boundary cells
    if horizontal_edges:
        for face in mesh.cell_boundary_indices[:-2]:
            is_face[face] = True

    if vertical_edges:
        for face in mesh.cell_boundary_indices[-2:]:
            is_face[face] = True

    # Find boundary active cells
    face_diff = ~np.isclose(mesh.stencil_cell_gradient @ actives, 0, atol=0.1)
    _, cols, _ = find(mesh.stencil_cell_gradient[face_diff, :])
    is_face[cols] = True

    return is_face & actives


@typed_call
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
    neighbors: dict[int, list] = {ax: [[], []] for ax in range(mesh.dim)}

    for ind in indices:
        for ax in range(mesh.dim):
            neighbors[ax][0].append(np.r_[mesh[ind].neighbors[ax * 2]])
            neighbors[ax][1].append(np.r_[mesh[ind].neighbors[ax * 2 + 1]])

    return tuple(
        (np.r_[tuple(neighbors[ax][0])], np.r_[tuple(neighbors[ax][1])])
        for ax in range(mesh.dim)
    )


@typed_call
def get_octree_attributes(mesh: Octree | TreeMesh) -> dict[str, list]:
    """
    Get mesh attributes.

    :param mesh: Input Octree or TreeMesh object.

    :return mesh_attributes: Dictionary of mesh attributes.
    """
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


@typed_call
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

    :return: New points object
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


@typed_call
def tensor_mesh_ordering(
    entity: BlockModel,
) -> np.ndarray:
    """
    Map the ordering of cell-based data from geoh5py.BlockModel to discretize.TensorMesh.

    :param entity: The mesh to order.

    :return indices: Array of indices to reorder cell-based values.
    """
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


@typed_call
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


@typed_call
def grid2d_to_tensor(
    entity: Grid2D,
) -> TensorMesh:
    """
    Convert a block model to a discretize.TensorMesh.

    :param entity: The block model to convert.

    :return: An equivalent TensorMesh object.
    """

    if entity.rotation != 0.0 or entity.dip != 0.0:
        raise NotImplementedError(
            "Conversion of rotated or dipping 2D grid not supported."
        )

    origin = [
        entity.origin["x"] + entity.u_cells[entity.u_cells < 0].sum(),
        entity.origin["y"] + entity.v_cells[entity.v_cells < 0].sum(),
        -np.inf,
    ]
    mesh = TensorMesh(
        [
            np.full(entity.u_count, entity.u_cell_size),
            np.full(entity.v_count, entity.v_cell_size),
            np.full(1, np.inf),
        ],
        x0=origin,
    )
    return mesh
