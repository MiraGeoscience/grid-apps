# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2025 Mira Geoscience Ltd.                                     '
#                                                                                   '
#  This file is part of grid-apps package.                                          '
#                                                                                   '
#  grid-apps is distributed under the terms and conditions of the MIT License       '
#  (see LICENSE file at the root of this source code package).                      '
# '''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from __future__ import annotations

import logging
import sys
import tempfile
from abc import abstractmethod
from pathlib import Path

from geoapps_utils.driver.data import BaseData
from geoapps_utils.driver.driver import BaseDriver
from geoh5py.groups import UIJsonGroup
from geoh5py.objects import BlockModel, ObjectBase
from geoh5py.shared.utils import fetch_active_workspace


logger = logging.getLogger(__name__)


class BaseGridDriver(BaseDriver):
    """
    Driver for the block model application.

    :param parameters: Application parameters.
    """

    _params_class: type[BaseData]

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


if __name__ == "__main__":
    file = Path(sys.argv[1]).resolve()
    BaseGridDriver.start(file)
