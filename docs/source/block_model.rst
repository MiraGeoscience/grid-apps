.. _block_model:

Block Model Creation
====================

The ``Block Model`` module has been developed as a user-interface for the creation of regular (Tensor) BlockModel objects using the `discretize <https://discretize.simpeg.xyz/en/main/>`_ package.

.. figure:: /images/block_model_creation_uijson.png
   :width: 500

A Block Model grid is a discretization of a 3D volume into a set of rectangular cells. The core region is defined by both the input ``Object`` with a depth limiter provided by the
``Core depth (m)``.  Cell sizes are provided for each axis, and a padding region may be specified where the cells expand at a rate given by the ``Expansion factor``.

.. figure:: /images/block_model_creation_result.png
    :width: 800
