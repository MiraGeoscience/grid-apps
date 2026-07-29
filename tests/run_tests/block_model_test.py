# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2026 Mira Geoscience Ltd.                                     '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of the MIT License       '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from __future__ import annotations

from pathlib import Path

import numpy as np
from geoh5py.objects import Points
from geoh5py.workspace import Workspace

from tests.conftest import setup_block_model


def test_get_block_model(tmp_path: Path):  # pylint: disable=too-many-locals
    # padding in the W/E/N/S directions should make create locs at least as
    # far as the core hull plus the padding distances

    pads = [100, 150, 200, 300, 0, 0]
    top = 500
    with Workspace(tmp_path / f"{__name__}.geoh5") as ws:
        grid = setup_block_model(
            ws,
            top=top,
            depth_core=300.0,
            pads=pads,
        )
        points: Points = ws.get_entity("Points")[0]

        assert (grid.origin["z"] + grid.z_cell_delimiters).max() == top
        assert grid.origin["x"] <= points.vertices[:, 0].min() - pads[0]
        assert grid.origin["y"] <= points.vertices[:, 1].min() - pads[2]
        assert grid.u_cell_delimiters.max() >= points.vertices[:, 0].max() + pads[0] + pads[1]  # type: ignore
        assert grid.v_cell_delimiters.max() >= points.vertices[:, 1].max() + pads[2] + pads[3]  # type: ignore


def test_padding(tmp_path: Path):
    # padding in the down direction should create locs at least as deep as the top
    # minus the sum of depth_core, h[2], and bottom padding.
    top = 500
    pads = [0, 0, 0, 0, 100, 0]  # padding on the bottom
    depth_core = 300.0
    cell_size = (50, 50, 50)
    with Workspace(tmp_path / f"{__name__}.geoh5") as ws:
        grid = setup_block_model(
            ws,
            top=top,
            depth_core=depth_core,
            pads=pads,
            cell_size=cell_size,
        )

    depth_delimiters = grid.origin["z"] + grid.z_cell_delimiters
    assert top - (depth_core + cell_size[2] + pads[4]) >= np.min(depth_delimiters)


def test_padding_up_to(tmp_path: Path):
    # padding in the up direction should shift the origin so that the core area
    # envelopes the locs (adjusted by depth_core).
    top = 500
    pads = [0, 0, 0, 0, 0, 100]  # padding on the bottom
    depth_core = 300.0
    expansion_factor = 1.1
    cell_size = (50, 50, 50)
    with Workspace(tmp_path / f"{__name__}.geoh5") as ws:
        grid = setup_block_model(
            ws,
            top=top,
            depth_core=depth_core,
            pads=pads,
            expansion_factor=expansion_factor,
            cell_size=cell_size,
        )

    assert grid.origin["z"] >= top + pads[-1]
    depth_delimiters = grid.origin["z"] + grid.z_cell_delimiters
    core_top_ind = np.argwhere(depth_delimiters == 500).flatten()[0]
    assert np.abs(np.diff(depth_delimiters))[core_top_ind] == cell_size[2]
    assert np.isclose(
        np.abs(np.diff(depth_delimiters))[core_top_ind - 1],
        cell_size[2] * expansion_factor,
    )
