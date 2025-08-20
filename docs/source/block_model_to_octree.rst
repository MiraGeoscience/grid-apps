.. _block_model_to_octree:

Block Model to Octree
=====================

.. note::

    Under construction.

The ``Block model to Octree`` module has been developed as a user-interface for the conversion between regular (Tensor) BlockModel objects to Octree, using the `discretize <https://discretize.simpeg.xyz/en/main/>`_ package.

# .. figure:: /images/octree_grid.png
#    :width: 800

An octree mesh is a discretization of a 3D volume into a set of rectangular cells. The cells are defined by a tree
structure, where each node has 8 children.
