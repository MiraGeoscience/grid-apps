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

from pathlib import Path
from typing import ClassVar

from geoapps_utils.driver.data import BaseData
from geoh5py.objects import BlockModel
from pydantic import BaseModel, ConfigDict

from grid_apps import assets_path


class SourceOptions(BaseModel):
    """
    Source parameters providing input data to the driver.

    :param objects: A Grid2D, Octree, BlockModel, Points, Curve or
        Surface source object.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    entity: BlockModel


class OutputOptions(BaseModel):
    """
    Output parameters for block model creation.

    :param export_as: Name of the output entity.
    :param out_group: Name of the output group.
    """

    export_as: str = "block_model"
    out_group: str | None = None


class BlockModel2OctreeOptions(BaseData):
    """
    Block model parameters for use with `block_models.driver`.

    :param source: Source data parameters.
    :param creation: Block Model creation parameters.
    :param output: Block Model output parameters.
    """

    name: ClassVar[str] = "block_model_to_octree"
    default_ui_json: ClassVar[Path] = (
        assets_path() / "uijson/block_model_to_octree.ui.json"
    )
    title: ClassVar[str] = "Block Model to Octree Conversion"
    run_command: ClassVar[str] = "grid_apps.block_model_to_octree.driver"

    conda_environment: str = "grid_apps"
    source: SourceOptions
    output: OutputOptions
