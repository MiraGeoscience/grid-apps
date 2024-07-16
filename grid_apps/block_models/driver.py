# ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024 Mira Geoscience Ltd.                                     '
#                                                                              '
#  This file is part of grid-apps package.                                     '
#                                                                              '
#  All rights reserved.                                                        '
# ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from __future__ import annotations

import logging
import sys

import numpy as np
from discretize.utils import mesh_utils
from geoapps_utils.driver.data import BaseData
from geoh5py.objects import BlockModel
from geoh5py.shared.utils import fetch_active_workspace
from geoh5py.ui_json import InputFile
from geoh5py.workspace import Workspace
from scipy.spatial import cKDTree

from grid_apps.block_models.params import BlockModelParameters
from grid_apps.driver import BaseBlockModelDriver
from grid_apps.utils import get_locations


logger = logging.getLogger(__name__)


class BlockModelDriver(BaseBlockModelDriver):
    """
    Create BlockModel from BlockModelParams.
    """

    _parameter_class = BlockModelParameters

    def __init__(self, parameters: BlockModelParameters | InputFile):
        if isinstance(parameters, InputFile):
            parameters = self._parameter_class.build(parameters)

        # TODO need to re-type params in base class
        super().__init__(parameters)  # type: ignore

    def make_grid(self):
        """
        Make block model object from input data.
        """
        with fetch_active_workspace(self.params.geoh5, mode="r+"):
            xyz = get_locations(self.params.geoh5, self.params.source.objects)
            if xyz is None:
                raise ValueError("Input object has no centroids or vertices.")

            tree = cKDTree(xyz)

            logger.info("Creating block model . . .")

            object_out = BlockModelDriver.get_block_model(
                workspace=self.params.geoh5,
                name=self.params.output.export_as,
                locs=xyz,
                h=self.params.creation.cell_sizes,
                depth_core=self.params.creation.depth_core,
                pads=self.params.creation.padding,
                expansion_factor=self.params.creation.expansion_factor,
            )

            # Try to recenter on nearest
            # Find nearest cells
            if object_out.centroids is None:
                raise ValueError("Block model has no centroids.")

            rad, ind = tree.query(object_out.centroids)
            ind_nn = np.argmin(rad)

            d_xyz = object_out.centroids[ind_nn, :] - xyz[ind[ind_nn], :]

            object_out.origin = np.r_[object_out.origin.tolist()] - d_xyz

            self.update_monitoring_directory(object_out)

        return object_out

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
    def get_block_model(  # pylint: disable=too-many-arguments
        workspace: Workspace,
        name: str,
        locs: np.ndarray,
        h: list,
        depth_core: float,
        pads: list,
        expansion_factor: float,
    ) -> BlockModel:
        """
        Create a BlockModel object from parameters.

        :param workspace: Workspace.
        :param name: Block model name.
        :param locs: Location points.
        :param h: Cell size(s) for the core mesh.
        :param depth_core: Depth of core mesh below locs.
        :param pads: len(6) Padding distances [W, E, N, S, Down, Up]
        :param expansion_factor: Expansion factor for padding cells.

        :return object_out: Output block model.
        """

        locs = BlockModelDriver.truncate_locs_depths(locs, depth_core)
        depth_core = BlockModelDriver.minimum_depth_core(locs, depth_core, h[2])
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
            origin=[mesh.x0[0], mesh.x0[1], locs[:, 2].max()],
            u_cell_delimiters=mesh.nodes_x - mesh.x0[0],
            v_cell_delimiters=mesh.nodes_y - mesh.x0[1],
            z_cell_delimiters=-(mesh.x0[2] + mesh.h[2].sum() - mesh.nodes_z[::-1]),
            name=name,
        )

        top_padding = BlockModelDriver.find_top_padding(object_out, h[2])
        object_out.origin["z"] += top_padding

        return object_out

    @property
    def params(self) -> BaseData:
        """Application parameters."""
        return self._params

    @params.setter
    def params(self, val: BaseData):
        if not isinstance(val, BaseData):
            raise TypeError("Parameters must be a BaseData subclass.")
        self._params = val


if __name__ == "__main__":
    file = sys.argv[1]
    ifile = InputFile.read_ui_json(file)
    driver = BlockModelDriver(ifile)
    driver.run()
