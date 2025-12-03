# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2022-2025 Mira Geoscience Ltd.                                     '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of the MIT License       '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''


from __future__ import annotations

import logging
import sys

import numpy as np
from discretize import TreeMesh
from discretize.utils import mesh_builder_xyz
from geoapps_utils.base import Driver as BaseDriver
from geoapps_utils.utils.locations import get_locations
from geoh5py.objects import Curve, ObjectBase, Octree, Points, Surface
from geoh5py.objects.surveys.direct_current import BaseElectrode
from geoh5py.shared.utils import fetch_active_workspace
from scipy import interpolate
from scipy.spatial import Delaunay, QhullError, cKDTree

from grid_apps.octree_creation.options import OctreeOptions, RefinementOptions
from grid_apps.utils import densify_curve, surface_strip, treemesh_2_octree


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class OctreeDriver(BaseDriver):
    """Driver for octree mesh creation."""

    _params_class = OctreeOptions

    def __init__(self, params: OctreeOptions):
        super().__init__(params)
        self.params: OctreeOptions = params

    def run(self) -> Octree:
        """Create an octree mesh from input values."""
        with fetch_active_workspace(self.params.geoh5, mode="r+"):
            logger.info("Creating octree mesh from params . . .")
            octree = self.octree_from_params(self.params)
            output = self.params.out_group or octree
            self.update_monitoring_directory(output)
            logger.info("Done.")

        return octree

    @staticmethod
    def octree_from_params(params: OctreeOptions) -> Octree:
        """
        Create an Octree object from input parameters.

        :param params: OctreeOptions containing the parameters for octree creation.

        :return: Octree object.
        """
        treemesh = OctreeDriver.treemesh_from_params(params)
        octree = treemesh_2_octree(
            params.geoh5, treemesh, name=params.ga_group_name, parent=params.out_group
        )
        return octree

    @staticmethod
    def treemesh_from_params(params: OctreeOptions) -> TreeMesh:
        """
        Create a TreeMesh object from input parameters.

        :param params: OctreeOptions containing the parameters for mesh creation.

        :return: TreeMesh object.
        """
        logger.info("Setting the mesh extent . . .")
        mesh = OctreeDriver.base_treemesh(params)

        logger.info("Applying minimum level refinement . . .")
        mesh = OctreeDriver.refine_minimum_level(mesh, params.minimum_level)

        logger.info("Applying extra refinements . . .")
        if params.refinements is not None:
            OctreeDriver.refine_objects(mesh, params.refinements)

        logger.info("Finalizing . . .")
        mesh.finalize()

        return mesh

    @staticmethod
    def base_treemesh(params: OctreeOptions) -> TreeMesh:
        """Create a base TreeMesh object from extents."""

        entity = params.objects
        if hasattr(entity, "complement") and entity.complement is not None:
            vertices = np.vstack([entity.vertices, entity.complement.vertices])
        else:
            vertices = entity.vertices

        mesh: TreeMesh = mesh_builder_xyz(
            vertices,
            [
                params.u_cell_size,
                params.v_cell_size,
                params.w_cell_size,
            ],
            padding_distance=params.get_padding(),
            mesh_type="tree",
            depth_core=params.depth_core,
            tree_diagonal_balance=params.diagonal_balance,
        )

        deltas = OctreeDriver.tree_offset(mesh, vertices)
        mesh.origin += deltas
        return mesh

    @staticmethod
    def refine_minimum_level(mesh: TreeMesh, minimum_level: int) -> TreeMesh:
        """Refine a TreeMesh with the minimum level of refinement."""
        minimum_level = OctreeDriver.minimum_level(mesh, minimum_level)
        mesh.refine(minimum_level, finalize=False)
        return mesh

    @staticmethod
    def refine_objects(
        mesh: TreeMesh, refinements: list[RefinementOptions | None]
    ) -> TreeMesh:
        """
        Refine by object or object + complement.

        :param mesh: Tree mesh to refine.
        :param refinements: List of refinements to apply.
        """
        for refinement in refinements:
            if refinement is None:
                continue
            kwargs = refinement.model_dump()
            kwargs["levels"] = [int(k) for k in kwargs["levels"].split(",")]
            refinement_object = [kwargs.pop("refinement_object")]
            if (
                hasattr(refinement_object[0], "complement")
                and refinement_object[0].complement is not None
            ):
                refinement_object.append(refinement_object[0].complement)

            for obj in refinement_object:
                mesh = OctreeDriver.refine_by_object_type(
                    mesh=mesh,
                    refinement_object=obj,
                    **kwargs,
                )

        return mesh

    @staticmethod
    def minimum_level(mesh: TreeMesh, level: int) -> int:
        """Computes the minimum level of refinement for a given tree mesh."""
        return max([1, mesh.max_level - level + 1])

    @staticmethod
    def refine_by_object_type(
        mesh: TreeMesh,
        refinement_object: ObjectBase,
        levels: list[int],
        *,
        horizon: bool,
        distance: float | None,
    ) -> TreeMesh:
        """Refine Treemesh as a based on object type."""
        if horizon:
            try:
                mesh = OctreeDriver.refine_tree_from_surface(
                    mesh,
                    refinement_object,
                    levels,
                    max_distance=np.inf if distance is None else distance,
                )
            except QhullError:
                base_cell_size = np.min([h.min() for h in mesh.h])
                mesh = OctreeDriver.refine_tree_from_surface(
                    mesh,
                    surface_strip(refinement_object, 2 * base_cell_size),
                    levels,
                    max_distance=np.inf if distance is None else distance,
                )

        elif isinstance(refinement_object, Curve):
            mesh = OctreeDriver.refine_tree_from_curve(mesh, refinement_object, levels)

        elif isinstance(refinement_object, Surface):
            mesh = OctreeDriver.refine_tree_from_triangulation(
                mesh, refinement_object, levels
            )

        elif isinstance(refinement_object, Points):
            mesh = OctreeDriver.refine_tree_from_points(
                mesh,
                refinement_object,
                levels,
            )

        else:
            raise NotImplementedError(
                f"Refinement for object {type(refinement_object)} is not implemented."
            )

        return mesh

    @staticmethod
    def refine_tree_from_curve(
        mesh: TreeMesh,
        curve: Curve,
        levels: list[int] | np.ndarray,
        *,
        finalize: bool = False,
    ) -> TreeMesh:
        """
        Refine a tree mesh along the segments of a curve densified by the
        mesh cell size.

        :param mesh: Tree mesh to refine.
        :param curve: Curve object to use for refinement.
        :param levels: Number of cells requested at each refinement level.
            Defined in reversed order from the highest octree to lowest.
        :param finalize: Finalize the tree mesh after refinement.

        """
        if not isinstance(curve, Curve):
            raise TypeError("Refinement object must be a Curve.")

        if curve.vertices is None:
            return mesh

        if isinstance(levels, list):
            levels = np.array(levels)

        if isinstance(curve, BaseElectrode):
            locations = curve.vertices
        else:
            locations = densify_curve(curve, mesh.h[0][0])

        mesh = OctreeDriver.refine_tree_from_points(
            mesh, locations, levels, finalize=False
        )

        if finalize:
            mesh.finalize()

        return mesh

    @staticmethod
    def refine_tree_from_points(
        mesh: TreeMesh,
        points: ObjectBase | np.ndarray,
        levels: list[int] | np.ndarray,
        *,
        finalize: bool = False,
    ) -> TreeMesh:
        """
        Refine a tree mesh along the vertices of an object.

        :param mesh: Tree mesh to refine.
        :param points: Object to use for refinement.
        :param levels: Number of cells requested at each refinement level.
            Defined in reversed order from the highest octree to lowest.
        :param finalize: Finalize the tree mesh after refinement.

        :return: Refined tree mesh.
        """
        if isinstance(points, ObjectBase):
            locations = get_locations(points.workspace, points)
        else:
            locations = points

        if locations is None:
            raise ValueError("Could not find locations for refinement.")

        if isinstance(levels, list):
            levels = np.array(levels)

        distance = 0
        for ii, n_cells in enumerate(levels):
            distance += n_cells * OctreeDriver.cell_size_from_level(mesh, ii)
            mesh.refine_ball(
                locations,
                distance,
                mesh.max_level - ii,
                finalize=False,
            )

        if finalize:
            mesh.finalize()

        return mesh

    @staticmethod
    def refine_tree_from_surface(  # pylint: disable=too-many-locals
        mesh: TreeMesh,
        surface: ObjectBase,
        levels: list[int] | np.ndarray,
        *,
        max_distance: float = np.inf,
        finalize: bool = False,
    ) -> TreeMesh:
        """
        Refine a tree mesh along the simplicies of a surface.

        :param mesh: Tree mesh to refine.
        :param surface: Surface object to use for refinement.
        :param levels: Number of cells requested at each refinement level.
            Defined in reversed order from the highest octree to lowest.
        :param max_distance: Maximum distance from the surface to refine.
        :param finalize: Finalize the tree mesh after refinement.

        :return: Refined tree mesh.
        """
        if isinstance(levels, list):
            levels = np.array(levels)

        xyz = get_locations(surface.workspace, surface)
        triang = Delaunay(xyz[:, :2])

        tree = cKDTree(xyz[:, :2])
        interp = interpolate.LinearNDInterpolator(triang, xyz[:, -1])
        levels = np.array(levels)

        depth = 0
        # Cycle through the Tree levels backward
        for ind, n_cells in enumerate(levels):
            if n_cells == 0:
                continue

            dx = OctreeDriver.cell_size_from_level(mesh, ind, 0)
            dy = OctreeDriver.cell_size_from_level(mesh, ind, 1)
            dz = OctreeDriver.cell_size_from_level(mesh, ind, 2)

            # Create a grid at the octree level in xy
            assert surface.extent is not None
            cell_center_x, cell_center_y = np.meshgrid(
                np.arange(surface.extent[0, 0], surface.extent[1, 0], dx),
                np.arange(surface.extent[0, 1], surface.extent[1, 1], dy),
            )
            xy = np.c_[cell_center_x.reshape(-1), cell_center_y.reshape(-1)]

            # Only keep points within triangulation
            inside = triang.find_simplex(xy) != -1
            r, _ = tree.query(xy)
            keeper = np.logical_and(r < max_distance, inside)
            nnz = keeper.sum()
            elevation = interp(xy[keeper])

            # Apply vertical padding for current octree level
            for _ in range(int(n_cells)):
                depth += dz
                mesh.insert_cells(
                    np.c_[xy[keeper], elevation - depth],
                    np.ones(nnz) * mesh.max_level - ind,
                    finalize=False,
                )

        if finalize:
            mesh.finalize()

        return mesh

    @staticmethod
    def refine_tree_from_triangulation(
        mesh: TreeMesh,
        surface,
        levels: list[int] | np.ndarray,
        finalize=False,
    ) -> TreeMesh:
        """
        Refine a tree mesh along the simplicies of a surface.

        :param mesh: Tree mesh to refine.
        :param surface: Surface object to use for refinement.
        :param levels: Number of cells requested at each refinement level.
            Defined in reversed order from highest octree to lowest.
        :param finalize: Finalize the tree mesh after refinement.

        :return: Refined tree mesh.
        """
        if not isinstance(surface, Surface):
            raise TypeError("Refinement object must be a Surface.")

        if surface.vertices is None or surface.cells is None:
            raise ValueError("Surface object must have vertices and cells.")

        if isinstance(levels, list):
            levels = np.array(levels)

        vertices = surface.vertices.copy()
        normals = np.cross(
            vertices[surface.cells[:, 1], :] - vertices[surface.cells[:, 0], :],
            vertices[surface.cells[:, 2], :] - vertices[surface.cells[:, 0], :],
        )
        if surface.n_vertices is None:
            raise ValueError("Surface object must have n_vertices.")

        average_normals = np.zeros((surface.n_vertices, 3))

        for vert_ids in surface.cells.T:
            average_normals[vert_ids, :] += normals

        average_normals /= np.linalg.norm(average_normals, axis=1)[:, None]

        base_cells = np.r_[mesh.h[0][0], mesh.h[1][0], mesh.h[2][0]]
        for level, n_cells in enumerate(levels):
            if n_cells == 0:
                continue

            for _ in range(int(n_cells)):
                mesh.refine_surface(
                    (vertices, surface.cells),
                    level=-level - 1,
                    finalize=False,
                )
                vertices -= average_normals * base_cells * 2.0**level

        if finalize:
            mesh.finalize()

        return mesh

    @staticmethod
    def cell_size_from_level(octree, level: int, axis: int = 0):
        """
        Computes the cell size at a given level of refinement for a given tree mesh.

        :param octree: Tree mesh to refine.
        :param level: Level of refinement.
        :param axis: Axis of refinement.

        :return: Cell size at the given level of refinement.
        """
        return octree.h[axis][0] * 2**level

    @staticmethod
    def tree_offset(mesh: TreeMesh, vertices: np.ndarray) -> np.ndarray:
        """
        Compute the offset required to center the mesh around the vertices.

        :param mesh: Tree mesh to center.
        :param vertices: Vertices to center around.

        :return: Offset required to center
        """
        # Center on the nearest central vertices
        center = np.mean(vertices, axis=0)
        ind_mid = np.argmin(np.linalg.norm(vertices - center, axis=1))

        offsets = []
        for ii in range(mesh.dim):
            cell_centers = mesh.origin[ii] + np.cumsum(mesh.h[ii]) - mesh.h[ii] / 2
            nearest = np.min(
                [
                    np.searchsorted(cell_centers, vertices[ind_mid, ii]),
                    mesh.shape_cells[ii] - 1,
                ]
            )
            offsets.append(vertices[ind_mid, ii] - cell_centers[nearest])

        return np.r_[offsets]


if __name__ == "__main__":
    file = sys.argv[1]
    OctreeDriver.start(file)
