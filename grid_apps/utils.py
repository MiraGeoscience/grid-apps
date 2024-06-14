# ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024 Mira Geoscience Ltd.                                     '
#                                                                              '
#  This file is part of grid-apps package.                                     '
#                                                                              '
#  All rights reserved.                                                        '
# ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

from __future__ import annotations

from uuid import UUID

from geoh5py.shared import Entity
from geoh5py.workspace import Workspace


def get_locations(workspace: Workspace, entity: UUID | Entity):
    """
    Returns entity's centroids or vertices.

    If no location data is found on the provided entity, the method will
    attempt to call itself on its parent.

    :param workspace: Geoh5py Workspace entity.
    :param entity: Object or uuid of entity containing centroid or
        vertex location data.

    :return: Array shape(*, 3) of x, y, z location data
    # todo: should this be in geoapps-utils?
    """
    locations = None

    if isinstance(entity, UUID):
        entity = workspace.get_entity(entity)[0]
    if hasattr(entity, "centroids"):
        locations = entity.centroids
    elif hasattr(entity, "vertices"):
        locations = entity.vertices

    elif getattr(entity, "parent", None) is not None and entity.parent is not None:
        locations = get_locations(workspace, entity.parent)

    return locations

