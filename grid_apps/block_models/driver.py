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
from discretize.utils import mesh_utils
from geoapps_utils.base import Driver as BaseDriver
from geoh5py.objects import BlockModel
from geoh5py.shared.utils import fetch_active_workspace
from geoh5py.workspace import Workspace
from scipy.spatial import cKDTree

from grid_apps.block_models.options import BlockModelOptions


logger = logging.getLogger(__name__)


class Driver(BaseDriver):
    """
    Create BlockModel from parameters.

    :param parameters: BlockModelOptions or InputFile containing the parameters.
    """

    _params_class = BlockModelOptions

    def run(self):
        """Create an octree mesh from input values."""
        with fetch_active_workspace(self.params.geoh5, mode="r+"):
            logger.info("Creating BlockModel mesh from parameters . . .")
            block = self.make_grid()
            output = self.params.out_group or block
            self.update_monitoring_directory(output)
            logger.info("Done.")

        return block

    def make_grid(self):
        """
        Make block model object from input data.
        """
        with fetch_active_workspace(self.params.geoh5, mode="r+"):
            source_locations = self.params.source.objects.locations
            if source_locations is None:
                raise ValueError("Input object has no centroids or vertices.")

            tree = cKDTree(source_locations)

            logger.info("Creating block model . . .")

            block_model = Driver.get_block_model(
                workspace=self.params.geoh5,
                locs=source_locations,
                h=self.params.creation.cell_sizes,
                depth_core=self.params.creation.depth_core,
                pads=self.params.creation.padding,
                expansion_factor=self.params.creation.expansion_factor,
                name=self.params.output.export_as,
            )

            if self.params.output.out_group is not None:
                block_model.parent = self.params.output.out_group

            # Try to recenter on nearest
            # Find nearest cells
            if block_model.centroids is None:
                raise ValueError("Block model has no centroids.")
                # TODO: Remove once GEOPY-1602 is merged

            neighbor_distances, neighbor_indices = tree.query(block_model.centroids)
            nearest_neighbor = np.argmin(neighbor_distances)
            source_to_nearest_neighbor = (
                block_model.centroids[nearest_neighbor, :]
                - source_locations[neighbor_indices[nearest_neighbor], :]
            )
            block_model.origin = (
                np.r_[block_model.origin.tolist()] - source_to_nearest_neighbor
            )

        return block_model

    @staticmethod
    def truncate_locs_depths(locs: np.ndarray, depth_core: float) -> np.ndarray:
        """
        Sets locations below core to core bottom.

        :param locs: Location points.
        :param depth_core: Depth of core mesh below locs.

        :return locs: locs with depths truncated.
        """
        zmax = locs[:, -1].max()  # top of locs
        below_core_ind = (zmax - locs[:, -1]) > depth_core
        core_bottom_elev = zmax - depth_core
        locs[below_core_ind, -1] = (
            core_bottom_elev  # sets locations below core to core bottom
        )
        return locs

    @staticmethod
    def minimum_depth_core(
        locs: np.ndarray, depth_core: float, core_z_cell_size: int
    ) -> float:
        """
        Get minimum depth core.

        :param locs: Location points.
        :param depth_core: Depth of core mesh below locs.
        :param core_z_cell_size: Cell size in z direction.

        :return depth_core: Minimum depth core.
        """
        zrange = locs[:, -1].max() - locs[:, -1].min()  # locs z range
        if depth_core >= zrange:
            return depth_core - zrange + core_z_cell_size

        return depth_core

    @staticmethod
    def find_top_padding(obj: BlockModel, core_z_cell_size: int) -> float:
        """
        Loop through cell spacing and sum until core_z_cell_size is reached.

        :param obj: Block model.
        :param core_z_cell_size: Cell size in z direction.

        :return pad_sum: Top padding.
        """
        pad_sum = 0.0

        if obj.z_cell_delimiters is None:
            raise ValueError("Block model has no z_cell_delimiters.")

        for h in np.abs(np.diff(obj.z_cell_delimiters)):
            if h != core_z_cell_size:
                pad_sum += h
            else:
                break

        return pad_sum

    @staticmethod
    def get_block_model(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        workspace: Workspace,
        locs: np.ndarray,
        h: list,
        depth_core: float,
        pads: list,
        expansion_factor: float,
        name: str = "BlockModel",
    ) -> BlockModel:
        """
        Create a BlockModel object from parameters.

        :param workspace: Workspace.
        :param locs: Location points.
        :param h: Cell size(s) for the core mesh.
        :param depth_core: Depth of core mesh below locs.
        :param pads: len(6) Padding distances [W, E, N, S, Down, Up]
        :param expansion_factor: Expansion factor for padding cells.
        :param name: Block model name.

        :return object_out: Output block model.
        """

        locs = Driver.truncate_locs_depths(locs, depth_core)
        depth_core = Driver.minimum_depth_core(locs, depth_core, h[2])
        mesh = mesh_utils.mesh_builder_xyz(
            locs,
            h,
            padding_distance=[
                [pads[0], pads[1]],
                [pads[2], pads[3]],
                [pads[4], pads[5]],
            ],
            depth_core=depth_core,
            expansion_factor=expansion_factor,
        )

        object_out = BlockModel.create(
            workspace,
            origin=[mesh.x0[0], mesh.x0[1], mesh.x0[2] + mesh.h[2].sum()],
            u_cell_delimiters=mesh.nodes_x - mesh.x0[0],
            v_cell_delimiters=mesh.nodes_y - mesh.x0[1],
            z_cell_delimiters=-(mesh.x0[2] + mesh.h[2].sum() - mesh.nodes_z[::-1]),
            name=name,
        )

        return object_out


if __name__ == "__main__":
    file = Path(sys.argv[1]).resolve()
    Driver.start(file)
