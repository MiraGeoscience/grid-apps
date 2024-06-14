# ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024 Mira Geoscience Ltd.                                     '
#                                                                              '
#  This file is part of grid-apps package.                                     '
#                                                                              '
#  All rights reserved.                                                        '
# ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
from __future__ import annotations

from pathlib import Path

import numpy as np
from geoh5py.workspace import Workspace

from grid_apps.driver import BlockModelDriver


def test_get_block_model(tmp_path: Path):
    # padding in the W/E/N/S directions should make create locs at least as
    # far as the core hull plus the padding distances
    top = 500
    depth_core = 300.0
    height = 300
    width = 1000
    n = 100

    X, Y = np.meshgrid(np.arange(0, width, n), np.arange(0, height, n))
    Z = np.around((top / 2) * np.sin(X) + (top / 2), -1)
    locs = np.c_[X.ravel(), Y.ravel(), Z.ravel()]
    pads = [100, 150, 200, 300, 0, 0]
    ws = Workspace(tmp_path / "data_transfer.geoh5")
    obj = BlockModelDriver.get_block_model(
        ws, "test", locs, [50, 50, 50], depth_core, pads, 1.1
    )
    assert (obj.origin["z"] + obj.z_cell_delimiters).max() == top
    assert obj.origin["x"] < -pads[0]
    assert obj.origin["y"] < -pads[2]
    assert obj.u_cell_delimiters.max() >= locs[:, 0].max() + pads[1] + pads[0]
    assert obj.v_cell_delimiters.max() >= locs[:, 1].max() + pads[3] + pads[2]

    # padding in the down direction should create locs at least as deep as the top
    # minus the sum of depth_core, h[2], and bottom padding.
    top = 500
    depth_core = 300.0
    height = 300
    width = 1000
    n = 100

    X, Y = np.meshgrid(np.arange(0, width, n), np.arange(0, height, n))
    Z = np.around((top / 2) * np.sin(X) + (top / 2), -1)
    locs = np.c_[X.ravel(), Y.ravel(), Z.ravel()]
    pads = [0, 0, 0, 0, 100, 0]  # padding on the bottom
    h = [50, 50, 50]

    obj = BlockModelDriver.get_block_model(ws, "test2", locs, h, depth_core, pads, 1.1)

    assert top - (depth_core + h[2] + pads[4]) >= np.min(
        obj.origin["z"] + obj.z_cell_delimiters
    )

    # padding in the up direction should shift the origin so that the core area
    # envelopes the locs (adjusted by depth_core).
    top = 500
    depth_core = 300.0
    height = 300
    width = 1000
    n = 100
    expansion_rate = 1.1

    X, Y = np.meshgrid(np.arange(0, width, n), np.arange(0, height, n))
    Z = np.around((top / 2) * np.sin(X) + (top / 2), -1)
    locs = np.c_[X.ravel(), Y.ravel(), Z.ravel()]
    pads = [0, 0, 0, 0, 0, 100]  # padding on the top
    h = [50, 50, 50]

    obj = BlockModelDriver.get_block_model(
        ws, "test2", locs, h, depth_core, pads, expansion_rate
    )

    assert obj.origin["z"] >= top + pads[-1]
    depth_delimiters = obj.origin["z"] + obj.z_cell_delimiters
    core_top_ind = np.argwhere(depth_delimiters == 500).flatten()[0]
    assert np.abs(np.diff(depth_delimiters))[core_top_ind] == h[2]
    assert np.isclose(
        np.abs(np.diff(depth_delimiters))[core_top_ind - 1], h[2] * expansion_rate
    )