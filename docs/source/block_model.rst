.. _block_model:

Block Model Creation
====================

The ``Block Model Creation`` module has been developed as a user interface for the creation of regular (Tensor)
BlockModel objects using the `discretize <https://discretize.simpeg.xyz/en/main/>`_ package.  A Block
Model grid is a discretization of a 3D volume into a set of rectangular cells.

.. figure:: /images/block_model_creation_result.png
    :width: 800

In order to determine the core extents of the block model, the user will select an input ``Object`` and
``Core depth``.  The padding is controlled by ``Horizontal padding``, ``Bottom padding``, and
``Expansion factor``.  The resolution is set per axis by the ``Minimum cell size`` parameters.

.. figure:: /images/block_model_creation_uijson.png
   :width: 500

The resulting block model will have its core region set by the object and limited by the ``Core depth``
parameter. The core region will contain cells at the requested ``Minimum cell size`` in all three
Cartesian directions. ``Horizontal`` and ``Vertical padding`` will be applied outward from the
core region to the specified distances.  Within the padding region, the cells expand outward at the
provided ``Expansion factor`` rate.

.. figure:: /images/block_model_creation_result.png
