.. _block_model_to_octree:

Block Model to Octree
=====================

.. figure:: /images/block_model_to_octree_uijson.png
   :width: 500

The ``Block model to Octree`` module has been developed as a user-interface for the conversion between regular (Tensor) BlockModel objects to Octree, using the `discretize <https://discretize.simpeg.xyz/en/main/>`_ package.

In its most simple form, the application will create an octree with the core region matching the cells of the block model with a small padding region where the cells are allowed to expand.

.. figure:: /images/block_model_to_octree_basic_usage.png
    :width: 800

There is also an option to refine the octree on a specified model.  This will create an octree that is refined in areas that contain large gradient in the provided model.

.. figure:: /images/block_model_to_octree_advanced.png
    :width: 800
