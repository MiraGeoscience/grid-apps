# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2026 Mira Geoscience Ltd.                                     '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of the MIT License       '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from __future__ import annotations

import string
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
from discretize import TensorMesh, TreeMesh
from geoapps_utils.base import Options
from geoh5py.data import NumericData
from geoh5py.objects import BlockModel, Octree
from geoh5py.objects.grid_object import GridObject
from pydantic import BaseModel, ConfigDict, model_serializer, model_validator

from grid_apps import assets_path
from grid_apps.utils import (
    block_model_to_tensor,
    octree_2_treemesh,
    tensor_mesh_ordering,
)


class GridModelMergerOptions(Options):
    """
    Block model parameters for use with `block_models.driver`.

    :param selections: List of grid and model selections.
    """

    name: ClassVar[str] = "grid_model_merger"
    default_ui_json: ClassVar[Path] = assets_path() / "uijson/grid_model_merger.ui.json"
    title: ClassVar[str] = "Grid Model Merger"
    run_command: ClassVar[str] = "grid_apps.grid_model_merger.driver"

    conda_environment: str = "grid_apps"
    output_grid: GridObject | None = None
    selections: list[MeshModelSelection | None] | None = None

    @model_validator(mode="before")
    @classmethod
    def collect_selections(cls, values: dict):
        """Collect selections from the input dictionary."""
        if "selections" not in values:
            selections = collect_selections_from_dict(values)
            values["selections"] = selections
        return values

    @model_serializer(mode="wrap")
    def distribute_selections(self, handler, info):
        """Convert selections to a individual parameters."""
        dump = handler(self, info)
        selections = dump.pop("selections")
        refinement_params: dict[str, Any] = {}
        for i, group in enumerate(selections):
            group_id = string.ascii_lowercase[i]
            if group is None:
                refinement_params[f"input_{group_id}_grid"] = None
                refinement_params[f"input_{group_id}_model"] = None
            else:
                for param, value in group.items():
                    param_name = f"input_{group_id}_{param}"
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
        update["selections"] = collect_selections_from_dict(data)

        return update


class MeshModelSelection(BaseModel):
    """
    Input parameters.

    :param grid: Grid object with data.
    :param model: NumericalData (model) entity.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    grid: GridObject
    model: NumericData | None = None

    def to_discretize(self) -> tuple[TreeMesh | TensorMesh, np.ndarray | None]:
        """
        Convert the geoh5 entity to discretized mesh object.

        :return: Discretize mesh object and model if provided.
        """
        model = None
        mesh = None
        if self.model is not None:
            model = self.model.values

        if isinstance(self.grid, BlockModel):
            model = model[tensor_mesh_ordering(self.grid)]
            mesh = block_model_to_tensor(self.grid)

        elif isinstance(self.grid, Octree):
            mesh = octree_2_treemesh(self.grid)

        if mesh is None:
            raise TypeError(f"Mesh type {type(self.grid)} currently not supported.")

        return mesh, model


def collect_selections_from_dict(data: dict) -> list[dict | None]:
    """Collect active input dictionaries from input dictionary."""
    inputs: list[dict | None] = []
    for identifier in input_identifiers(data):
        input_params = {}
        for param in ["grid", "model"]:
            input_name = f"input_{identifier}_{param}"
            value = data.get(input_name, None)

            if value is not None:
                input_params[param] = value

        if input_params.get("grid", None) is not None:
            inputs.append(input_params)

    return inputs


def input_identifiers(data: dict) -> list[str]:
    """Return identifiers for active inputs (object not none)."""
    active = [k for k in data if "_grid" in k]
    return np.unique([k.split("_")[1] for k in active])
