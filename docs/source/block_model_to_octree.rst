.. _block_model_to_octree:

Block Model to Octree
=====================


The ``Block Model to Octree`` module has been developed as a user interface for the conversion between
regular 3D grid (`BlockModel`) objects to Octree, using the `discretize <https://discretize.simpeg.xyz/en/main/>`_
package.

.. figure:: /images/block_model_to_octree_advanced.png
    :width: 800

In its most simple form, the application creates an octree from the input block model.

.. figure:: /images/block_model_to_octree_uijson_basic.png
   :width: 500

In this case the application will create an octree with the core region matching the cells of
the block model with a small padding region where the cells are allowed to expand to the closest
octree level.

.. figure:: /images/block_model_to_octree_basic_usage.png
    :width: 800

Optionally, users can select a model stored on the tensor mesh.

.. figure:: /images/block_model_to_octree_uijson_advanced.png
   :width: 500

The octree will be then be refined in areas that contain large gradients in the selected model.

.. figure:: /images/block_model_to_octree_advanced.png
    :width: 800
