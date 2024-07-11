# ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024 Mira Geoscience Ltd.                                     '
#                                                                              '
#  This file is part of grid-apps package.                                     '
#                                                                              '
#  All rights reserved.                                                        '
# ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from __future__ import annotations

import logging
import tempfile
from abc import abstractmethod
from pathlib import Path

from geoapps_utils.driver.data import BaseData
from geoapps_utils.driver.driver import BaseDriver
from geoh5py.groups import UIJsonGroup
from geoh5py.objects import BlockModel, ObjectBase
from geoh5py.shared.utils import fetch_active_workspace
from geoh5py.ui_json import InputFile


logger = logging.getLogger(__name__)


class BaseBlockModelDriver(BaseDriver):
    """
    Driver for the block model application.

    :param parameters: Application parameters.
    """

    _parameter_class: type[BaseData]

    def __init__(self, parameters: BaseData | InputFile):
        self._out_group = None
        if isinstance(parameters, InputFile):
            parameters = self._parameter_class.build(parameters)

        # TODO need to re-type params in base class
        super().__init__(parameters)

    @property
    def out_group(self) -> UIJsonGroup | None:
        """Output container group."""

        if self._out_group is None and self.params.output.out_group is not None:
            with fetch_active_workspace(self.workspace, mode="r+") as workspace:
                self._out_group = UIJsonGroup.create(
                    workspace=workspace,
                    name=self.params.output.out_group,
                )
                self._out_group.options = InputFile.stringify(  # type: ignore
                    InputFile.demote(self.params.input_file.ui_json)
                )

        return self._out_group

    def store(self, block_model: BlockModel):
        """
        Update container group and monitoring directory.

        :param surface: Surface to store.
        """
        with fetch_active_workspace(self.workspace, mode="r+") as workspace:
            self.update_monitoring_directory(
                block_model if self.out_group is None else self.out_group
            )
            logger.info(
                "Curve object '%s' saved to '%s'.",
                self.params.output.export_as,
                str(workspace.h5file),
            )

    @abstractmethod
    def make_grid(self):
        pass

    def run(self):
        """Run the surface application driver."""
        logging.info("Begin Process ...")
        block_model = self.make_grid()
        logging.info("Process Complete.")
        self.store(block_model)

    @property
    def params(self) -> BaseData:
        """Application parameters."""
        return self._params

    @params.setter
    def params(self, val: BaseData):
        if not isinstance(val, BaseData):
            raise TypeError("Parameters must be a BaseData subclass.")
        self._params = val

    def add_ui_json(self, entity: ObjectBase | UIJsonGroup) -> None:
        """
        Add ui.json file to entity.

        :param entity: Object to add ui.json file to.
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = Path(temp_dir) / f"{self.params.name}.ui.json"
            self.params.write_ui_json(filepath)

            entity.add_file(str(filepath))
