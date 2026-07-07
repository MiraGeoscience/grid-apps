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
from discretize.utils import mesh_utils
from geoapps_utils.base import Driver as BaseDriver
from geoh5py.objects import Octree
from geoh5py.shared.utils import fetch_active_workspace
from scipy.sparse import find
from scipy.spatial import cKDTree

from grid_apps.block_model_to_octree.driver import Driver as BMODriver
from grid_apps.grid_model_merger.options import GridModelMergerOptions
from grid_apps.utils import (
    refine_tree_by_mesh,
    tensor_to_block_model,
    treemesh_2_octree,
)


logger = logging.getLogger(__name__)


class Driver(BaseDriver):
    """
    Merge multiple grids and models from selection.

    :param parameters: GridModelMergerOptions or InputFile containing the parameters.
    """

    _params_class = GridModelMergerOptions

    def __init__(self, params: GridModelMergerOptions):

        super().__init__(params)
        self.output_grid = None

    def run(self):
        """Create an octree mesh from input values."""
        with fetch_active_workspace(self.params.geoh5, mode="r+"):
            logger.info("Merging grids and models from selection . . .")
            self.output_grid = self.get_output_grid()

            self.interpolate_models_to_output_grid()
            output = self.params.out_group or self.output_grid
            self.update_monitoring_directory(output)
            logger.info("Done.")

        return self.output_grid

    def get_output_grid(self):
        """
        Make block model object from input data.
        """
        with fetch_active_workspace(self.params.geoh5, mode="r+"):
            if self.params.output_grid is not None:
                return self.params.output_grid

            extent = np.vstack([[np.inf] * 3, [-np.inf] * 3])
            cell_size = np.hstack([np.inf] * 3)
            mesh_type = None
            for selection in self.params.selections:
                grid = selection.grid

                extent[0, :] = np.min([extent[0, :], grid.extent[0, :]], axis=0)
                extent[1, :] = np.max([extent[1, :], grid.extent[1, :]], axis=0)

                if isinstance(grid, Octree):
                    cell_size = np.min(
                        [
                            cell_size,
                            np.r_[grid.u_cell_size, grid.v_cell_size, grid.w_cell_size],
                        ],
                        axis=0,
                    )
                else:
                    cell_size = np.min(
                        [
                            cell_size,
                            np.r_[
                                grid.u_cells.min(),
                                grid.v_cells.min(),
                                grid.z_cells.min(),
                            ],
                        ],
                        axis=0,
                    )

                if mesh_type is None:
                    mesh_type = type(grid)

            mesh = mesh_utils.mesh_builder_xyz(
                extent,
                np.abs(cell_size),
                mesh_type="tree" if mesh_type is Octree else "tensor",
                tree_diagonal_balance=True,
            )

            if mesh_type is Octree:
                for selection in self.params.selections:
                    if isinstance(selection.grid, Octree):
                        levels = mesh.max_level - np.log2(
                            selection.grid.octree_cells["NCells"]
                        )
                        mesh.insert_cells(
                            selection.grid.centroids, levels, finalize=False
                        )
                    else:
                        treemesh = BMODriver.block_model_to_treemesh(
                            selection.grid, finalize=False
                        )
                        treemesh = BMODriver.refine_by_cell_volumes(
                            treemesh, selection.grid
                        )
                        treemesh_2_octree(self.params.geoh5, treemesh)
                        mesh = refine_tree_by_mesh(mesh, treemesh, finalize=False)

                mesh.finalize()
                output_grid = treemesh_2_octree(
                    self.params.geoh5, mesh, parent=self.params.out_group
                )
            else:
                output_grid = tensor_to_block_model(
                    self.params.geoh5, mesh, parent=self.params.out_group
                )

        return output_grid

    def interpolate_models_to_output_grid(self):
        """
        Interpolate models from selections to output grid.
        """
        with fetch_active_workspace(self.params.geoh5, mode="r+"):
            out_model = np.full(self.output_grid.n_cells, np.nan, dtype=float)
            weights = np.full(self.output_grid.n_cells, np.nan, dtype=float)

            for selection in self.params.selections:
                mesh, model = selection.to_discretize()

                if model is None:
                    continue

                logger.info(
                    f"Interpolating model {selection.model.name} from grid {selection.grid.name} to output grid {self.output_grid.name} . . ."
                )

                active = ~np.isnan(model)
                is_face = np.zeros_like(active, dtype=bool)
                # Find active horizontal mesh boundary cells
                for face in mesh.cell_boundary_indices[:-2]:
                    is_face[face] = True

                # Find horizontal boundary model cells
                face_diff = ~np.isclose(
                    mesh.stencil_cell_gradient @ active, 0, atol=0.1
                )
                _, cols, _ = find(mesh.stencil_cell_gradient[face_diff, :])
                is_face[cols] = True
                active_boundary = is_face & active

                # Compute weights based on distance to boundary
                tree = cKDTree(mesh.cell_centers[active_boundary])
                rad, _ = tree.query(mesh.cell_centers[active])
                cosine_tapper = -0.5 * np.cos(-rad / rad.max() * np.pi) + 0.5
                weight_model = np.full(active.shape[0], np.nan, dtype=float)
                weight_model[active] = cosine_tapper

                # Find nearest neighbour and apply weighted model
                del tree
                tree = cKDTree(mesh.cell_centers)
                _, ind = tree.query(self.output_grid.centroids)
                out_model = np.nansum(
                    [out_model, weight_model[ind] * model[ind]], axis=0
                )
                weights = np.nansum([weights, weight_model[ind]], axis=0)
                del tree

            # Normalizes weighted sum
            not_nan = ~np.isnan(out_model)
            out_model[not_nan] /= weights[not_nan]

            if np.any(~np.isnan(out_model)):
                self.output_grid.add_data(
                    {
                        "merged_model": {
                            "values": out_model,
                        }
                    }
                )


if __name__ == "__main__":
    file = Path(sys.argv[1]).resolve()
    Driver.start(file)
