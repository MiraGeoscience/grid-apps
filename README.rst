|coverage| |maintainability| |precommit_ci| |docs| |style| |version| |status| |pyversions|


.. |docs| image:: https://readthedocs.org/projects/grid-apps/badge/
    :alt: Documentation Status
    :target: https://grid-apps.readthedocs.io/en/latest/?badge=latest

.. |coverage| image:: https://codecov.io/gh/MiraGeoscience/grid-apps/branch/develop/graph/badge.svg
    :alt: Code coverage
    :target: https://codecov.io/gh/MiraGeoscience/grid-apps

.. |style| image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :alt: Coding style
    :target: https://github.com/pf/black

.. |version| image:: https://img.shields.io/pypi/v/grid-apps.svg
    :alt: version on PyPI
    :target: https://pypi.python.org/pypi/grid-apps/

.. |status| image:: https://img.shields.io/pypi/status/grid-apps.svg
    :alt: version status on PyPI
    :target: https://pypi.python.org/pypi/grid-apps/

.. |pyversions| image:: https://img.shields.io/pypi/pyversions/grid-apps.svg
    :alt: Python versions
    :target: https://pypi.python.org/pypi/grid-apps/

.. |precommit_ci| image:: https://results.pre-commit.ci/badge/github/MiraGeoscience/grid-apps/develop.svg
    :alt: pre-commit.ci status
    :target: https://results.pre-commit.ci/latest/github/MiraGeoscience/grid-apps/develop

.. |maintainability| image:: https://api.codeclimate.com/v1/badges/_token_/maintainability
   :target: https://codeclimate.com/github/MiraGeoscience/grid-apps/maintainability
   :alt: Maintainability


grid-apps: # TODO: SHORT DESCRIPTION
=========================================================================
The **grid-apps** library # TODO: PACKAGE DESCRIPTION

.. contents:: Table of Contents
   :local:
   :depth: 3

Documentation
^^^^^^^^^^^^^
`Online documentation <https://grid-apps.readthedocs.io/en/latest/>`_


Installation
^^^^^^^^^^^^
**grid-apps** is currently written for Python 3.10 or higher.

Install Conda
-------------

To install **grid-apps**, you need to install **Conda** first.

We recommend to install **Conda** using `miniforge`_.

.. _miniforge: https://github.com/conda-forge/miniforge

Quick installation
-------------------

To install (or re-install) a conda environment to run **grid-apps**, simply execute the **install.bat** file.

To install in editable mode, so that changes in the source code are immediately reflected in the
running application, execute with the ``-e`` option: ``install.bat -e``.

.. warning::

    In editable mode, the source folder must not be moved or deleted after installation.


Manual installation
-------------------

You should not install the package directly with ``pip``, as the app requires conda packages to run.

First create a Conda environment with all the required dependencies,
then activate it and install the package in this environment using
``pip install --no-deps ...``

See instructions below for more details and options.

Prepare a Conda environment with dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You can create a Conda environment with all the required dependencies ``conda`` and the ``.lock``
files from a conda prompt::

    $ conda env create --solver libmamba -n my-env -f environments/[the_desired_env].lock.yml

.. note::

    The package itself is not install yet in the Conda environment. See following instructions.

.. warning::

    All the following ``pip`` commands are meant to be executed in the Conda environment you just created.
    Activate it with::

    $ conda activate my-env

From PyPI
~~~~~~~~~

To install the **grid-apps** package published on PyPI::

    $ pip install --no-deps -U grid-apps

From a Git tag or branch
~~~~~~~~~~~~~~~~~~~~~~~~
If the revision of the package is not on PyPI yet, you can install it from a Git tag::

    $ pip install --no-deps -U --force-reinstall https://github.com/MiraGeoscience/grid-apps/archive/refs/tags/TAG.zip

Or to install the latest changes available on a given Git branch::

    $ pip install --no-deps -U --force-reinstall https://github.com/MiraGeoscience/grid-apps/archive/refs/heads/BRANCH.zip

.. note::

    The ``--force-reinstall`` option is used to make sure the updated version
    of the sources is installed, and not the cached version, even if the version number
    did not change.

    The ``-U`` or ``--upgrade`` option is used to make sure to get the latest version,
    on not merely reinstall the same version.

    The option ``--no-deps`` is used to avoid installing the dependencies with pip,
    as they have dependencies are already installed within the **Conda environment**.

From a local copy of the sources
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you have a git clone of the package sources locally, you can install **grid-apps** from the
local copy of the sources. At the root of the sources, you will find a ``pyproject.toml`` file.

Change directory to the root of the sources::

    $ cd path/to/project_folder_with_pyproject_toml

Then run::

    $ pip install --no-deps -U --force-reinstall .

Or in **editable mode**, so that you can edit the sources and see the effect immediately at runtime::

    $ pip install --no-deps -U --force-reinstall -e .

Setup for development
^^^^^^^^^^^^^^^^^^^^^
To configure the development environment and tools, please see `README-dev.rst`_.

.. _README-dev.rst: README-dev.rst

License
^^^^^^^
# TODO: ADD LICENSE TERMS

Third Party Software
^^^^^^^^^^^^^^^^^^^^
The grid-apps Software may provide links to third party libraries or code (collectively "Third Party Software")
to implement various functions. Third Party Software does not comprise part of the Software.
The use of Third Party Software is governed by the terms of such software license(s).
Third Party Software notices and/or additional terms and conditions are located in the
`THIRD_PARTY_SOFTWARE.rst`_ file.

.. _THIRD_PARTY_SOFTWARE.rst: THIRD_PARTY_SOFTWARE.rst

Trademarks
^^^^^^^^^^
"Python" and the Python logos are trademarks or registered trademarks of the Python Software Foundation.

Copyright
^^^^^^^^^
Copyright (c) 2024 Mira Geoscience Ltd.
