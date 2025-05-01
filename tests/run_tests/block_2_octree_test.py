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
from geoh5py.objects import Points
from octree_creation_app.utils import treemesh_2_octree

from grid_apps.block_model_to_octree.driver import BlockModelToOctreeDriver
from grid_apps.block_models.driver import BlockModelDriver


def test_block_model_to_octree(tmp_path):
    # Create a test block model
    h5file_path = tmp_path / f"{__name__}.geoh5"
    with Workspace.create(h5file_path) as workspace:
        locs = np.array([[0, 0, 0], [150, 0, 0], [0, 150, 0]])
        depth_core = 150.0
        pads = [1000, 1000, 1000, 1000, 1000, 1000]  # padding on the top
        h = [50, 50, 50]
        Points.create(workspace, vertices=locs)
        block_model = BlockModelDriver.get_block_model(
            workspace,
            locs,
            h,
            depth_core,
            pads,
            1.5,
            name="TestBlockModel",
        )

        treemesh = BlockModelToOctreeDriver.block_model_to_treemesh(block_model)
        treemesh = BlockModelToOctreeDriver.refine_by_cell_volumes(
            treemesh, block_model
        )
        octree = treemesh_2_octree(workspace, treemesh)

        assert octree.n_cells == 3172
