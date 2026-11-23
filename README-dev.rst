Setup for development
=====================

.. contents:: Table of Contents
   :local:
   :depth: 2

Prerequisites
^^^^^^^^^^^^^

* **Pixi and uv:** Install `Pixi <https://pixi.sh/>`_ 0.84.2 and external
  `uv <https://docs.astral.sh/uv/>`_. Keep both commands on ``PATH``; uv is not
  installed by Pixi.
* **Git LFS:** This repository uses Git LFS. Follow GitHub's `installation
  instructions
  <https://docs.github.com/en/repositories/working-with-files/managing-large-files/installing-git-large-file-storage>`_.
* **prek:** Install `prek <https://prek.j178.dev/>`_ for the configured Git
  hooks.
* **IDE interpreter:** Configure your IDE to use the interpreter inside
  ``.pixi/envs/default`` and exclude ``.pixi`` from source indexing.
  For **PyCharm**, follow Pixi's `JetBrains integration guide
  <https://pixi.prefix.dev/latest/integration/editor/jetbrains/>`_.
* **JFrog authentication:** Pixi uses uv's PyPI authentication, which is
  separate from ``pixi auth login``. Configure a protected ``.netrc`` file
  (``%HOME%\_netrc`` on Windows) with your Artifactory machine, login, and
  password or access token, as described in `Pixi's authentication guide
  <https://pixi.prefix.dev/latest/deployment/authentication/#netrc-file>`_.
  Never add credentials to ``pixi.toml`` or ``pixi.lock``.

.. note:: External contributors using Pixi

   If you do not have Mira Artifactory credentials, comment out ``index-url``
   under ``[feature.mira-pypi.pypi-options]`` in ``pixi.toml``, then run
   ``pixi lock``. Packages configured with version references will resolve from
   public PyPI if the required versions are available there; packages configured
   with Git references will resolve from Git.
   Keep these local ``pixi.toml`` and ``pixi.lock`` changes uncommitted.

Install and test
^^^^^^^^^^^^^^^^

The shared lock covers Windows and Linux with multiple Python versions::

    pixi install --locked -e py312
    pixi run --frozen -e py312 install
    pixi run --frozen -e py312 test

The ``install`` task installs this checkout in editable mode without changing
locked dependencies, then checks package compatibility.

The ``runtime`` environment omits test and lint tools.

On Windows, install the locked runtime into Geoscience Analyst with::

    install_in_analyst.bat
    install_in_analyst.bat -e --name mirageo-dev

Possibly, replace ``mirageo-dev`` with a dedicated environment name of your choice.

The script exports the locked ``win-64`` runtime, installs its dependencies
through Analyst, and installs this checkout without resolving dependencies
again. Pass ``-e`` first for editable mode; optional ``--conda`` and ``--name``
arguments are forwarded to Analyst. A valid ``pixi.lock`` is required. When the
lock points to JFrog, Analyst's pip installation also needs access, for example
through the same ``.netrc`` credentials.

Building documentation
^^^^^^^^^^^^^^^^^^^^^^

The separate ``docs`` environment uses Python 3.14 and Sphinx. Read the Docs
installs uv separately. Fetch the Git LFS documentation images, then
build HTML with::

    git lfs pull
    pixi run --frozen --environment docs build-docs

The task installs the local package without dependencies, uses the checked-in
configuration ``docs/source/conf.py``, and builds the documentation from
``docs/source`` into ``docs/_build/html``. Read the Docs uses the same task.

Updating dependencies
^^^^^^^^^^^^^^^^^^^^^

Keep published package requirements in ``pyproject.toml`` and their Conda/PyPI
environment equivalents in ``pixi.toml`` aligned. Update the recipe's matching
runtime requirements when a dependency constraint changes.

After editing requirements, run ``pixi update`` to update dependencies, or
``pixi lock`` to resolve the manifest and refresh the lock file without
installing the environments.

Commit ``pixi.lock`` with the manifest changes. In ``pixi.toml``, the
``mira-pypi`` feature lists Mira packages resolved from PyPI or GitHub:

- On a development branch, comment out published versions and use git sources.
- When preparing a release, use published versions and comment out git sources.

The lock file is checked by ``tests/pixi_lock_test.py``: it ensures all dependencies
are resolved from Conda, except for the Mira packages listed under the
``mira-pypi`` feature. Keep compatibility bounds on indirect Conda dependencies:
Pixi solves Conda before PyPI and does not backtrack between them.

Git hooks
^^^^^^^^^

Install `prek <https://prek.j178.dev/>`_ and use the existing hook configuration::

    prek install -t prepare-commit-msg -t commit-msg -t pre-commit -f --prepare-hooks
    prek run --all-files

The local pylint hook runs in the locked ``py312`` environment.

Test layout
^^^^^^^^^^^

Tests live under ``tests`` and use the ``_test.py`` filename suffix.


---------

*Copyright (c) 2024-2026 Mira Geoscience Ltd.*
