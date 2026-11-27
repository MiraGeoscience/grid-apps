.. _grid_model_merger:

Grid Model Merger
=================

The ``Grid Model Merger`` module combines models from multiple grid objects into
a single output grid. The application supports the merging of different grid types: ``BlockModel``, ``Octree``, and ``Grid2D``
objects.

.. figure:: /images/grid_model_merger.png
    :width: 800

    Example showing the merging of two different grid types into a single output grid.


User Interface
--------------

The user interface allows the selection of an output grid, scaling type, and up to six input grids and models.

.. figure:: /images/grid_model_merger_ui.png
    :width: 800

- **Output grid**: Select an existing output grid to receive the merged model.

  If no output grid is selected, the application creates one that covers the combined extent
  of the input grids. Its type is determined by the first input grid, and its
  cell dimensions are based on the smallest input cell dimensions. For an
  ``Octree`` output, the mesh is also refined to follow the input grids.

- **Scaling**: Choose ``linear`` or ``log`` scaling for the merge. Log scaling
  applies a symmetric-log transform before blending and reverses the transform
  on the result, which can reduce the influence of extreme values.

- **Input A to F**: Select the input grid and model to transfer. The input grid can be a
  ``BlockModel``, ``Octree``, or ``Grid2D`` object. The model is optional; if
  no model is selected, the input grid will still contribute to the output
  grid geometry.


Methodology
-----------

Models are transferred to the output grid and blended where their coverage
overlaps. The operation is performed using a weighted average of the input models,

.. math::

    \mathbf{m}_{out} = \frac{\sum_{i=1}^{N} w_i \mathbf{m}_i}{\sum_{i=1}^{N} w_i}

where the weights are determined by the distance to the nearest active cell in each input grid.

.. figure:: /images/grid_model_merger_weights.png
    :width: 800

A cosine function is used to smoothly transition the weights from 1 at the center of the input grid to 0 at the edge of its coverage.
