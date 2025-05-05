# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2025 Mira Geoscience Ltd.                                     '
#  All rights reserved.                                                             '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of a proprietary license '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from __future__ import annotations

import numpy as np
from discretize import TensorMesh
from geoh5py.objects import BlockModel


def block_model_to_discretize(
    entity: BlockModel,
) -> TensorMesh | tuple[TensorMesh, np.ndarray]:
    """
    Convert a block model to a discretize.TensorMesh.

    :param entity: The block model to convert.
    """
    if not isinstance(entity, BlockModel):
        raise TypeError("entity must be an instance of BlockModel.")

    origin = [
        entity.origin["x"] + entity.u_cells[entity.u_cells < 0].sum(),
        entity.origin["y"] + entity.v_cells[entity.v_cells < 0].sum(),
        entity.origin["z"] + entity.z_cells[entity.z_cells < 0].sum(),
    ]
    mesh = TensorMesh(
        [
            np.abs(entity.u_cells),
            np.abs(entity.v_cells),
            np.abs(entity.z_cells[::-1]),
        ],
        x0=origin,
    )
    return mesh


def tensor_mesh_ordering(
    entity: BlockModel,
) -> np.ndarray:
    """
    Map the ordering of cell-based data from geoh5py.BlockModel to discretize.TensorMesh.

    :param entity: The mesh to order.

    :return indices: Array of indices to reorder cell-based values.
    """
    if not isinstance(entity, BlockModel):
        raise TypeError("mesh must be an instance of BlockModel.")

    indices = np.arange(entity.n_cells)
    indices = indices.reshape(
        (
            entity.shape[2],
            entity.shape[0],
            entity.shape[1],
        ),
        order="F",
    )[::-1, :, :]
    indices = indices.transpose((1, 2, 0)).flatten(order="F")

    return indices
