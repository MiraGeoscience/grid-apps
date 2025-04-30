# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2025 Mira Geoscience Ltd.                                     '
#  All rights reserved.                                                             '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of a proprietary license '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''


import numpy as np
from geoh5py import Workspace
from pytest import raises

from grid_apps.block_models.driver import BlockModelDriver
from grid_apps.utils import block_model_to_discretize


def test_block_model_to_octree(tmp_path):
    # Create a test block model
    h5file_path = tmp_path / f"{__name__}.geoh5"
    with Workspace.create(h5file_path) as workspace:
        locs = np.array([[0, 0, 0], [150, 0, 0], [0, 150, 0]])
        depth_core = 150.0
        pads = [0, 0, 0, 0, 0, 0]  # padding on the top
        h = [50, 50, 50]
        block_model = BlockModelDriver.get_block_model(
            workspace,
            locs,
            h,
            depth_core,
            pads,
            1.1,
            name="TestBlockModel",
        )

        origin = []
        for ax, ori in zip("uvz", block_model.origin, strict=False):
            cell_sizes = getattr(block_model, f"{ax}_cells")
            cc_x = np.median(block_model.local_axis_centers(ax))
            n_cx = np.ceil(np.log2(np.sum(cell_sizes) / cell_sizes.min()))

            cell_sizes_octree = np.ones(int(2**n_cx)) * cell_sizes.min()
            cc_x_octree = np.median(
                np.cumsum(cell_sizes_octree) - cell_sizes_octree / 2
            )

            origin.append(ori + cc_x - cc_x_octree)
