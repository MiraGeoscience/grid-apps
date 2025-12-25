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
from geoh5py.data import FloatData, ReferencedData
from geoh5py.groups import UIJsonGroup
from geoh5py.objects import BlockModel
from pydantic import BaseModel, ConfigDict

from grid_apps import assets_path


class OutputOptions(BaseModel):
    """
    Output parameters for block model creation.

    :param export_as: Name of the output entity.
    :param out_group: Output UIJson group.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    export_as: str | None = None
    out_group: UIJsonGroup | None = None


class BlockModel2OctreeOptions(Options):
    """
    Block model parameters for use with `block_models.driver`.

    :param entity: BlockModel source object.
    :param data: Optional data to refine the octree mesh.
    :param output: Output options.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: ClassVar[str] = "block_model_to_octree"
    default_ui_json: ClassVar[Path] = (
        assets_path() / "uijson/block_model_to_octree.ui.json"
    )
    title: ClassVar[str] = "Block Model to Octree Conversion"
    run_command: ClassVar[str] = "grid_apps.block_model_to_octree.driver"
    conda_environment: str = "grid_apps"

    entity: BlockModel
    data: FloatData | ReferencedData | None = None

    output: OutputOptions = OutputOptions()
