# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2025 Mira Geoscience Ltd.                                     '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of the MIT License       '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
from discretize import TreeMesh
from geoapps_utils.base import Driver as BaseDriver
from geoh5py.data import FloatData, ReferencedData
from geoh5py.objects import BlockModel, Octree
from geoh5py.ui_json.utils import fetch_active_workspace
from scipy.spatial import cKDTree

from grid_apps.block_model_to_octree.options import BlockModel2OctreeOptions
from grid_apps.utils import (
    block_model_to_discretize,
    boundary_value_indices,
    tensor_mesh_ordering,
    treemesh_2_octree,
)


logger = logging.getLogger(__name__)


class Driver(BaseDriver):
    """
    Convert a BlockModel object to Octree with various refinement strategies.
    """

    _params_class = BlockModel2OctreeOptions

    def run(self):
        """Create an octree mesh from input values."""
        with fetch_active_workspace(self.params.geoh5, mode="r+"):
            logger.info("Converting BlockModel to Octree mesh . . .")
            octree = self.make_grid()
            output = self.params.out_group or octree
            self.update_monitoring_directory(output)
            logger.info("Done.")

        return octree

    @staticmethod
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
            ind_core = np.where(cell_sizes == h_core)[0]
            center = (
                entity.origin[ii]
                + entity.local_axis_centers(ax)[ind_core[len(ind_core) // 2]]
            )

            axis_center = len(cell_sizes_octree) // 2
            origin.append(center - np.sum(cell_sizes_octree[:axis_center]) - h_core / 2)

        treemesh = TreeMesh(
            octree_cells,
            x0=origin,
            finalize=finalize,
            diagonal_balance=diagonal_balance,
        )

        return treemesh

    def make_grid(self) -> Octree:
        """
        Convert the block model and output the octree mesh.

        :return: Octree object refined by the cell volumes or gradient of the data.
        """
        with fetch_active_workspace(self.params.geoh5, mode="r+"):
            entity = self.params.entity

            treemesh = Driver.block_model_to_treemesh(entity, finalize=False)
            model = None
            if self.params.data is None:
                treemesh = Driver.refine_by_cell_volumes(
                    treemesh, entity, finalize=True
                )
            else:
                treemesh = Driver.refine_by_values(
                    treemesh, self.params.data, finalize=True
                )
                # Transfer the model
                ind = treemesh.get_containing_cells(entity.centroids)
                model = (
                    np.ones(treemesh.n_cells, dtype=self.params.data.values.dtype)
                    * self.params.data.nan_value
                )
                model[ind] = self.params.data.values

                nan_vals = (model == self.params.data.nan_value) | np.isnan(model)
                if np.any(nan_vals):
                    tree = cKDTree(entity.centroids)
                    ind = tree.query(treemesh.cell_centers[nan_vals])[1]
                    model[nan_vals] = self.params.data.values[ind]

            octree = treemesh_2_octree(
                self.params.geoh5,
                treemesh,
                parent=self.params.output.out_group,
                name=self.params.output.export_as or entity.name + "_octree",
            )

            if model is not None and self.params.data is not None:
                octree.add_data(
                    {
                        self.params.data.name: {
                            "values": model,
                            "entity_type": self.params.data.entity_type,
                        }
                    }
                )

            return octree

    @staticmethod
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
        if not isinstance(entity, BlockModel):
            raise TypeError("entity must be an instance of BlockModel.")

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

    @staticmethod
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
        if not isinstance(data, FloatData | ReferencedData):
            raise TypeError(
                "Argument 'data' must be an instance of FloatData or ReferencedData."
            )

        entity = data.parent
        if not isinstance(entity, BlockModel):
            raise TypeError("The parent of 'data' must be an instance of BlockModel.")

        tensor = block_model_to_discretize(entity)
        indices = tensor_mesh_ordering(entity)

        gradients = np.abs(tensor.cell_gradient @ data.values[indices])
        levels = np.zeros(gradients.shape, dtype=int)
        isnan = np.isnan(gradients)

        if isinstance(data, FloatData):
            actives = gradients[~isnan]
            bins = np.percentile(
                actives[actives > 0], np.linspace(5, 95, mesh.max_level)
            )
            levels[~isnan] = np.searchsorted(bins, actives)
        else:
            levels[gradients > 0] = mesh.max_level

        # Refine on the value/nan interface, without boundary cells
        if any(isnan):
            horizon = boundary_value_indices(
                tensor, data.values[indices], data.nan_value
            )
            mesh = Driver.refine_by_cell_volumes(
                mesh, entity, finalize=False, mask=horizon[np.argsort(indices)]
            )

        locs = tensor.average_cell_to_face @ tensor.cell_centers
        mesh.insert_cells(locs[~isnan], levels[~isnan].astype(int), finalize=finalize)

        return mesh


if __name__ == "__main__":
    file = Path(sys.argv[1]).resolve()
    Driver.start(file)
