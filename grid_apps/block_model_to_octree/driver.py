# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2025 Mira Geoscience Ltd.                                     '
#  All rights reserved.                                                             '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of a proprietary license '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from __future__ import annotations

import logging
import sys

import numpy as np
from discretize import TreeMesh
from geoh5py.objects import BlockModel
from geoh5py.ui_json import InputFile
from geoh5py.ui_json.utils import fetch_active_workspace
from octree_creation_app.utils import treemesh_2_octree

from grid_apps.block_model_to_octree.options import BlockModel2OctreeOptions
from grid_apps.driver import BaseBlockModelDriver


logger = logging.getLogger(__name__)


class BlockModelToOctreeDriver(BaseBlockModelDriver):
    """
    Convert a BlockModel object to Octree with various refinement strategies.
    """

    _parameter_class = BlockModel2OctreeOptions

    def __init__(self, parameters: BlockModel2OctreeOptions | InputFile):
        if isinstance(parameters, InputFile):
            parameters = self._parameter_class.build(parameters)

        super().__init__(parameters)  # type: ignore

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

    def make_grid(self):
        """
        Convert the block model and output the octree mesh.
        :return:
        """
        with fetch_active_workspace(self.params.geoh5, mode="r+"):
            entity = self.params.source.entity

            treemesh = BlockModelToOctreeDriver.block_model_to_treemesh(entity)
            treemesh = BlockModelToOctreeDriver.refine_by_cell_volumes(
                treemesh, entity, finalize=True
            )

            octree = treemesh_2_octree(self.params.geoh5, treemesh)

            return octree

    @staticmethod
    def refine_by_cell_volumes(
        mesh: TreeMesh, entity: BlockModel, finalize=True
    ) -> TreeMesh:
        """
        Refine the octree mesh by the cell volumes of the block model.

        :param mesh: TreeMesh object to be refined.
        :param entity: BlockModel object to be used for refinement.
        :param finalize: Whether to finalize the treemesh after refinement.

        :return: TreeMesh object with refinement.
        """
        tensor_oct_level = []
        for ax in "uvz":
            cell_sizes = np.abs(getattr(entity, f"{ax}_cells"))
            h_core = cell_sizes.min()

            # Find the core region
            tensor_oct_level.append(np.log2(cell_sizes / h_core).astype(int))

        e_x, e_y, e_z = np.meshgrid(*tensor_oct_level)
        max_level = np.c_[np.ravel(e_x), np.ravel(e_y), np.ravel(e_z)].max(axis=1)
        mesh.insert_cells(
            entity.centroids, mesh.max_level - max_level, finalize=finalize
        )

        return mesh


if __name__ == "__main__":
    file = sys.argv[1]
    ifile = InputFile.read_ui_json(file)
    driver = BlockModelToOctreeDriver(ifile)
    driver.run()
