# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2025 Mira Geoscience Ltd.                                     '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of the MIT License       '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from geoapps_utils.base import Options
from geoh5py.groups import UIJsonGroup
from geoh5py.objects import CellObject, Points
from geoh5py.objects.grid_object import GridObject
from pydantic import BaseModel, ConfigDict

from grid_apps import assets_path


class BlockModelSourceOptions(BaseModel):
    """
    Source parameters providing input data to the driver.

    :param objects: A Grid2D, Octree, BlockModel, Points, Curve or
        Surface source object.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    objects: Points | CellObject | GridObject


class BlockModelCreationOptions(BaseModel):
    """
    Block model specification parameters.

    :param cell_size_x: Cell size in x direction.
    :param cell_size_y: Cell size in y direction.
    :param cell_size_z: Cell size in z direction.
    :param depth_core: Depth of core mesh below locs.
    :param horizontal_padding: Horizontal padding.
    :param bottom_padding: Bottom padding.
    :param expansion_factor: Expansion factor for padding cells.
    """

    cell_size_x: float
    cell_size_y: float
    cell_size_z: float
    depth_core: float
    horizontal_padding: float
    bottom_padding: float
    expansion_factor: float

    @property
    def cell_sizes(self) -> list[float]:
        """
        Cell sizes in x, y and z directions.
        """
        return [self.cell_size_x, self.cell_size_y, self.cell_size_z]

    @property
    def padding(self) -> list[float]:
        """
        Padding distances in west, east, south, north, down and up directions.
        """
        return [self.horizontal_padding] * 4 + [self.bottom_padding, 0.0]


class BlockModelOutputOptions(BaseModel):
    """
    Output parameters for block model creation.

    :param export_as: Name of the output entity.
    :param out_group: Name of the output group.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    export_as: str = "block_model"
    out_group: UIJsonGroup | None = None


class BlockModelOptions(Options):
    """
    Block model parameters for use with `block_models.driver`.

    :param source: Source data parameters.
    :param creation: Block Model creation parameters.
    :param output: Block Model output parameters.
    """

    name: ClassVar[str] = "block_model"
    default_ui_json: ClassVar[Path] = assets_path() / "uijson/block_models.ui.json"
    title: ClassVar[str] = "Block Model Creation"
    run_command: ClassVar[str] = "grid_apps.block_models.driver"

    conda_environment: str = "grid_apps"
    source: BlockModelSourceOptions
    creation: BlockModelCreationOptions
    output: BlockModelOutputOptions = BlockModelOutputOptions()
