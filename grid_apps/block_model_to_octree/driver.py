# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2026 Mira Geoscience Ltd.                                     '
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
from geoapps_utils.base import Driver as BaseDriver
from geoh5py.objects import Octree
from geoh5py.ui_json.utils import fetch_active_workspace
from scipy.spatial import cKDTree

from grid_apps.block_model_to_octree.options import BlockModel2OctreeOptions
from grid_apps.utils import (
    block_model_to_treemesh,
    refine_by_cell_volumes,
    refine_by_values,
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

    def make_grid(self) -> Octree:
        """
        Convert the block model and output the octree mesh.

        :return: Octree object refined by the cell volumes or gradient of the data.
        """
        with fetch_active_workspace(self.params.geoh5, mode="r+"):
            entity = self.params.entity

            treemesh = block_model_to_treemesh(entity, finalize=False)
            model = None
            if self.params.data is None:
                treemesh = refine_by_cell_volumes(treemesh, entity, finalize=True)
            else:
                treemesh = refine_by_values(treemesh, self.params.data, finalize=True)
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


if __name__ == "__main__":
    file = Path(sys.argv[1]).resolve()
    Driver.start(file)
