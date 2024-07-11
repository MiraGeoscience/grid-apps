# ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024 Mira Geoscience Ltd.                                     '
#                                                                              '
#  This file is part of grid-apps package.                                     '
#                                                                              '
#  All rights reserved.                                                        '
# ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from pathlib import Path
from typing import ClassVar
from pydantic import BaseModel, ConfigDict
from geoh5py.objects import Points, CellObject
from geoh5py.objects.grid_object import ObjectBase, GridObject
from geoapps_utils.driver.data import BaseData

from grid_apps import assets_path


class BlockModelSourceParameters(BaseModel):
    """
    Source parameters providing input data to the driver.

    :param objects: A Grid2D, Octree, BlockModel, Points, Curve or
        Surface source object.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    objects: Points | CellObject | GridObject


class BlockModelCreationParameters(BaseModel):
    """
    Block model specification parameters.

    :param cell_size_x: Cell size in x direction.
    :param cell_size_y: Cell size in y direction.
    :param cell_size_z: Cell size in z direction.
    :param depth_core: Depth of core mesh below locs.
    :param horizontal_padding: Horizontal padding.
    :param bottom_padding: Bottom padding.
    :param expansion_fact: Expansion factor for padding cells.
    """

    cell_size_x: float
    cell_size_y: float
    cell_size_z: float
    depth_core: float
    horizontal_padding: float
    bottom_padding: float
    expansion_fact: float


class BlockModelOutputParameters(BaseModel):
    """
    Output parameters for block model creation.

    :param export_as: Name of the output entity.
    :param out_group: Name of the output group.
    """

    export_as: str = "block_model"
    out_group: str | None = None


class BlockModelParameters(BaseData):
    """
    Block model parameters for use with `block_models.driver`.

    :param source: Source data parameters.
    :param creation: Block Model creation parameters.
    :param output: Block Model output parameters.
    """

    name: ClassVar[str] = "block_model"
    default_ui_json: ClassVar[Path] = assets_path() / "uijson/block_model.ui.json"
    title: ClassVar[str] = "Block Model Creation"
    run_command: ClassVar[str] = "grid_apps.block_models.driver"

    conda_environment: str = "grid_apps"
    source: BlockModelSourceParameters
    creation: BlockModelCreationParameters
    output: BlockModelOutputParameters
