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
from geoh5py.objects import BlockModel
from geoh5py.shared.utils import fetch_active_workspace
from geoh5py.workspace import Workspace
from scipy.spatial import cKDTree

from grid_apps.block_models.options import BlockModelOptions
from grid_apps.utils import tensor_to_block_model


logger = logging.getLogger(__name__)


class Driver(BaseDriver):
    """
    Create BlockModel from parameters.
    """

    _params_class = BlockModelOptions

    def run(self):
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

        object_out = tensor_to_block_model(workspace, mesh, name=name)

        return object_out


if __name__ == "__main__":
    file = Path(sys.argv[1]).resolve()
    Driver.start(file)
