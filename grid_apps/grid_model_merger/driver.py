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
from geoapps_utils.utils.plotting import inv_symlog, symlog
from geoh5py.objects import Octree
from geoh5py.shared.utils import fetch_active_workspace, mask_by_extent
from scipy.spatial import cKDTree

from grid_apps.grid_model_merger.options import GridModelMergerOptions, ScalingTypeEnum
from grid_apps.utils import (
    get_boundary_active_cells,
    refine_tree_by_mesh,
    tensor_to_block_model,
    treemesh_2_octree,
)


logger = logging.getLogger(__name__)


class Driver(BaseDriver):
    """
    Merge multiple grids and models from selection.

    :param params: Options for merging multiple grids and models.
    """

    _params_class = GridModelMergerOptions

    def __init__(self, params: GridModelMergerOptions):

        super().__init__(params)
        self.output_grid = None

    def run(self):
        """Create an octree mesh from input values."""
        with fetch_active_workspace(self.params.geoh5, mode="r+"):
            self.output_grid = self.get_output_grid()
            self.interpolate_models_to_output_grid()
            output = self.params.out_group or self.output_grid
            self.update_monitoring_directory(output)
            logger.info("Done.")

        return self.output_grid

    def get_global_mesh_specs(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Loop through selections to get global mesh specifications for output grid.

        :return: Array of outer extent and core cell dimensions.
        """
        extent = np.vstack([[np.inf] * 3, [-np.inf] * 3])
        cell_size = np.hstack([np.inf] * 3)

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

        return extent, np.abs(cell_size)

    def get_output_grid(self):
        """
        Make block model object from input data.
        """
        with fetch_active_workspace(self.params.geoh5, mode="r+"):
            if self.params.output_grid is not None:
                return self.params.output_grid

            extent, cell_size = self.get_global_mesh_specs()

            # Use type of the first entry
            mesh_type = type(self.params.selections[0].grid)

            logger.info("Merging selected grids to '%s' . . .", mesh_type.__name__)

            mesh = mesh_utils.mesh_builder_xyz(
                extent,
                cell_size,
                mesh_type="tree" if mesh_type is Octree else "tensor",
                tree_diagonal_balance=True,
            )

            if mesh_type is Octree:
                for selection in self.params.selections:
                    mesh = refine_tree_by_mesh(mesh, selection.grid, finalize=False)

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
            threshold = None

            for selection in self.params.selections:
                mesh, model = selection.to_discretize()

                if model is None or not np.any(~np.isnan(model)):
                    continue

                active = ~np.isnan(model)

                logger.info(
                    "Interpolating model '%s' from grid '%s' to output grid '%s' . . .",
                    selection.model.name,
                    selection.grid.name,
                    self.output_grid.name,
                )

                if self.params.scaling_type == ScalingTypeEnum.LOG:
                    if threshold is None:
                        threshold = np.percentile(np.abs(model[active]), 10)

                    model = symlog(model, threshold=threshold)

                active_boundary = get_boundary_active_cells(
                    mesh, active, horizontal_edges=True
                )
                cosine_taper = self.cosine_taper_weights(
                    mesh.cell_centers[active_boundary], mesh.cell_centers[active]
                )
                weight_model = np.full(active.shape[0], np.nan, dtype=float)
                weight_model[active] = cosine_taper

                # Find nearest neighbors and apply weighted model
                tree = cKDTree(mesh.cell_centers)
                _, ind = tree.query(self.output_grid.centroids, workers=-1)

                # Trim weights for cells outside the extent of the input mesh
                cell_weights = weight_model[ind]
                mask = mask_by_extent(self.output_grid.centroids, selection.grid.extent)
                cell_weights[~mask] = np.nan

                out_model = np.nansum([out_model, cell_weights * model[ind]], axis=0)
                weights = np.nansum([weights, cell_weights], axis=0)
                del tree

            # Normalizes weighted sum
            non_zero = weights > 0
            out_model[non_zero] /= weights[non_zero]
            out_model[~non_zero] = np.nan

            if self.params.scaling_type == ScalingTypeEnum.LOG:
                out_model = inv_symlog(out_model, threshold=threshold)

            if np.any(~np.isnan(out_model)):
                self.output_grid.add_data(
                    {
                        "merged_model": {
                            "values": out_model,
                            "entity_type": selection.model.entity_type,
                        }
                    }
                )

    @staticmethod
    def cosine_taper_weights(edge_locations: np.ndarray, target_locations: np.ndarray):
        # Compute weights based on distance to boundary cells
        tree = cKDTree(edge_locations)
        rad, _ = tree.query(target_locations, workers=-1)

        rad_max = rad.max() + 1e-8  # Avoid zero division
        cosine_taper = -0.5 * np.cos(-rad / rad_max * np.pi) + 0.5

        # Find nearest neighbors and apply weighted model
        del tree

        return cosine_taper


if __name__ == "__main__":
    file = Path(sys.argv[1]).resolve()
    Driver.start(file)
