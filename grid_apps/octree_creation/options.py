# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2022-2025 Mira Geoscience Ltd.                                     '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of the MIT License       '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
from __future__ import annotations

import string
import warnings
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
from geoapps_utils.base import Options
from geoh5py.groups import UIJsonGroup
from geoh5py.objects import Points
from pydantic import (
    BaseModel,
    ConfigDict,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

from grid_apps import assets_path


class OctreeOptions(Options):
    """
    Octree creation parameters.

    :param objects: Object used to define the core of the mesh.
    :param depth_core: Limit the depth of the core of the mesh.
    :param diagonal_balance: Whether to limit the cell size change
        to one level in the transition between diagonally adjacent
        cells.
    :param minimum_level: Provides a minimum level of refinement for
        the whole mesh to prevent excessive coarsenin in padding
        regions.
    :param u_cell_size: Cell size in the x-direction.
    :param v_cell_size: Cell size in the y-direction.
    :param w_cell_size: Cell size in the z-direction.
    :param horizontal_padding: Padding in the x and y directions.
    :param vertical_padding: Padding in the z direction.
    :param refinements: List of refinements to be applied.
    """

    model_config = ConfigDict(
        frozen=True,
        arbitrary_types_allowed=True,
    )

    name: ClassVar[str] = "Octree_Mesh"
    default_ui_json: ClassVar[Path] = assets_path() / "uijson/octree_mesh.ui.json"

    title: str = "Octree Mesh Creator"
    run_command: str = "grid_apps.octree_creation.driver"
    conda_environment: str = "grid_apps"
    objects: Points
    depth_core: float = 500.0
    ga_group_name: str = "Octree Mesh"  # TODO: Alias this in uijson (mesh_name)
    diagonal_balance: bool = True
    minimum_level: int = 8
    u_cell_size: float = 25.0
    v_cell_size: float = 25.0
    w_cell_size: float = 25.0
    horizontal_padding: float = 500.0
    vertical_padding: float = 200.0
    refinements: list[RefinementOptions | None] | None = None
    out_group: UIJsonGroup | None = None

    @model_validator(mode="before")
    @classmethod
    def collect_refinements(cls, values: dict):
        """Collect refinements from the input dictionary."""
        if "refinements" not in values:
            refinements = collect_refinements_from_dict(values)
            if refinements:
                msg = (
                    "Detected deprecated 'Refinement A property' style refinements,"
                    " converting to a list of dictionaries."
                )
                warnings.warn(msg)
            values["refinements"] = refinements
        return values

    @model_serializer(mode="wrap")
    def distribute_refinements(self, handler, info):
        """Convert refinements to a individual parameters."""
        dump = handler(self, info)
        refinements = dump.pop("refinements")
        refinement_params: dict[str, Any] = {}
        for i, group in enumerate(refinements):
            group_id = string.ascii_uppercase[i]
            if group is None:
                refinement_params[f"Refinement {group_id} object"] = None
                refinement_params[f"Refinement {group_id} levels"] = None
                refinement_params[f"Refinement {group_id} horizon"] = None
                refinement_params[f"Refinement {group_id} distance"] = None
            else:
                for param, value in group.items():
                    param_type = "object" if param == "refinement_object" else param
                    param_name = f"Refinement {group_id} {param_type}"
                    refinement_params[param_name] = value

        return dict(dump, **refinement_params)

    @classmethod
    def collect_input_from_dict(cls, model: type[BaseModel], data: dict[str, Any]):
        """
        Recursively replace BaseModel objects with dictionary of 'data' values.

        :param model: BaseModel object holding data and possibly other nested
            BaseModel objects.
        :param data: Dictionary of parameters and values without nesting structure.
        """

        update = super().collect_input_from_dict(model, data)
        update["refinements"] = collect_refinements_from_dict(data)

        return update

    def get_padding(self) -> list:
        """
        Utility to get the padding values as a list of padding along each axis.
        """
        return [
            [
                self.horizontal_padding,
                self.horizontal_padding,
            ],
            [
                self.horizontal_padding,
                self.horizontal_padding,
            ],
            [self.vertical_padding, self.vertical_padding],
        ]


class RefinementOptions(BaseModel):
    """
    Refinement parameters.

    :param object: Object used to define the core of the mesh.
    :param levels: Levels of refinement.
    :param horizon: Whether the refinement is a surface or radial.
    :param distance: Distance from the object to refine.
    """

    model_config = ConfigDict(
        frozen=True,
        arbitrary_types_allowed=True,
    )
    refinement_object: Points
    levels: list[int] = [4, 2]
    horizon: bool = False
    distance: float | None = np.inf

    @field_validator("levels", mode="before")
    @classmethod
    def int_2_list(cls, levels: int | list[int]):
        """
        Convert single integer to list.
        """
        if isinstance(levels, int):
            levels = [levels]
        return levels

    @field_validator("levels", mode="before")
    @classmethod
    def string_2_list(cls, levels: str | list[int]):
        """
        Convert comma-separated string to list of integers.
        """
        if isinstance(levels, str):
            levels = [int(level) for level in levels.split(",")]
        return levels

    @field_serializer("levels")
    def list_to_string(self, value):
        """
        Convert list of integers to comma-separated string.
        """
        return ", ".join(str(v) for v in value)


def collect_refinements_from_dict(data: dict) -> list[dict | None]:
    """Collect active refinement dictionaries from input dictionary."""
    refinements: list[dict | None] = []
    for identifier in refinement_identifiers(data):
        refinement_params = {}
        for param in ["object", "levels", "horizon", "distance"]:
            name = f"refinement_{param}" if param == "object" else param
            refinement_name = f"Refinement {identifier} {param}"
            refinement_params[name] = data.get(refinement_name, None)

        if refinement_params["refinement_object"] is None:
            refinements.append(None)
        else:
            refinements.append(refinement_params)
    return refinements


def refinement_identifiers(data: dict) -> list[str]:
    """Return identifiers for active refinements (object not none)."""
    refinements = [k for k in data if "Refinement" in k]
    active = [k for k in refinements if "object" in k]
    return np.unique([k.split(" ")[1] for k in active])
