.. _getting_started:

Getting Started
===============

Install `Pixi <https://pixi.sh/>`_ version 0.84.2 or newer and external
`uv <https://docs.astral.sh/uv/>`_, with both commands available on ``PATH``.
Then clone the `grid-apps repository <https://github.com/MiraGeoscience/grid-apps>`_.

From the project directory, install the locked runtime and the local package::

    pixi run --frozen --environment runtime install

The package is installed in editable mode. Keep the source directory in place.
To activate the runtime environment, run::

    pixi shell --frozen --environment runtime

See the :ref:`Basic usage <usage>` section for details on running the applications.
