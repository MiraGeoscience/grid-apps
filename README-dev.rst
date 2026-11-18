
Setup for development
=====================

.. contents:: Table of Contents
   :local:
   :depth: 2

After you have cloned the Git repository, you will need to:

#. install the Pixi environments for the project
#. execute the tests
#. setup Git LFS if needed
#. configure the prek hooks for static code analysis and auto-formatting
#. configure the Python IDE (PyCharm)


.. _Pixi: https://pixi.sh/
.. _prek: https://prek.j178.dev/


Install the Pixi environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Install `Pixi`_ version 0.84.2 or newer. From the project root, install the default
development environment with::

    pixi install

The default environment includes the test and lint tools. Run the tests with::

    pixi run test

The project also provides ``py312``, ``py313`` and ``py314`` test environments,
plus ``runtime`` environments for application use.
On Windows, run ``install_in_analyst.bat`` to install the locked runtime in Geoscience
Analyst; pass ``-e`` for an editable installation.


Updating dependencies
^^^^^^^^^^^^^^^^^^^^^

Runtime dependency constraints are maintained in ``pyproject.toml`` and ``pixi.toml``.
After changing either file, refresh the resolved environment with::

    pixi update


Adding a dependency
-------------------
Add runtime requirements to both the PEP 621 dependency list in ``pyproject.toml``
and the matching Pixi package requirements in ``pixi.toml``. Put development-only
tools in the appropriate Pixi feature. Run ``pixi update`` after changing them.


Configure prek hooks
^^^^^^^^^^^^^^^^^^^^

`prek`_ runs the checks configured in ``.pre-commit-config.yaml``. Install it with::

    uv tool install prek

From the project directory, install the Git hook and run all checks with::

    prek install --prepare-hooks
    prek run --all-files

Run ``prek run`` to check only the files selected for the current commit. Update
hook revisions with ``prek auto-update``.


Running the tests
^^^^^^^^^^^^^^^^^

Test files are placed under the ``tests`` folder. Inside this folder and sub-folders,
Python test files are to be named with ``_test.py`` as a suffix.
The test function within this files must have a ``test_`` prefix.


Install pytest
--------------
.. _pytest: https://docs.pytest.org/

After installing the default Pixi environment, run pytest from the project folder::

    pixi run pytest tests


Code coverage with Pytest
-------------------------
.. _pytest-cov: https://pypi.org/project/pytest-cov/

`pytest-cov`_ is installed in the default environment. Run the tests with HTML coverage::

    pixi run pytest --cov-report html tests

The html report is generated in the folder ``htmlcov`` at the root of the project.
You can then explore the report by opening ``index.html`` in a browser.


Git LFS
^^^^^^^
In the case your package requires large files, `git-lfs`_ can be used to store those files.
Copy it from the `git-lfs`_ website, and install it.

Then, in the project folder, run the following command to install git-lfs::

    $ git lfs install


It will update the file ``.gitattributes`` with the list of files to track.

Then, add the files and the ``.gitattributes`` to the git repository, and commit.

.. _git-lfs: https://git-lfs.com/

Then, add the files to track with git-lfs::

    $ git lfs track "*.desire_extension"


IDE : PyCharm
^^^^^^^^^^^^^
`PyCharm`_, by JetBrains, is a very good IDE for developing with Python.


Configure the Python interpreter in PyCharm
--------------------------------------------

First, exclude the ``.pixi`` folder from PyCharm by right-clicking it and selecting
``Mark Directory as > Excluded``.

    ..  image:: devtools/images/pycharm-exclude_conda_env.png
        :alt: PyCharm: Exclude Pixi environment
        :align: center
        :width: 40%

Add the Pixi environment's Python interpreter (``.pixi/envs/default/Scripts/python.exe``
on Windows or ``.pixi/envs/default/bin/python`` on Linux).

In PyCharm settings, open ``File > Settings``, go to ``Python Interpreter``,
and add click add interpreter (at the top left):

    ..  image:: devtools/images/pycharm-add_Python_interpreter.png
        :alt: PyCharm: Python interpreter settings
        :align: center
        :width: 80%

Select the option for an existing or system interpreter and choose the Python executable
inside ``.pixi/envs/default``:

    ..  image:: devtools/images/pycharm-set_conda_env_as_interpreter.png
        :alt: PyCharm: Set Pixi environment as interpreter
        :align: center
        :width: 80%

Then you can check the list of installed packages in the ``Packages`` table. You should see
this source package and its dependencies. Make sure to turn off the ``Use Conda Package Manager``
option to see also the packages installed through pip:

    ..  image:: devtools/images/pycharm-list_all_conda_packages.png
        :alt: PyCharm: Pixi environment packages
        :align: center
        :width: 80%


Run the tests from PyCharm
--------------------------
First, right click on the ``tests`` folder and select ``Mark Directory as > Test Sources Root``:

    ..  image:: devtools/images/pycharm-mark_directory_as_tests.png
        :alt: PyCharm: Add Python interpreter
        :align: center
        :width: 40%

You can now start tests with a right click on the ``tests`` folder and
select ``Run 'pytest in tests'``, or select the folder and just hit ``Ctrl+Shift+F10``.

PyCharm will nicely present the test results and logs:

    ..  image:: devtools/images/pycharm-test_results.png
        :alt: PyCharm: Run tests
        :align: center
        :width: 80%


Execute tests with coverage from PyCharm
----------------------------------------

You can run the tests with a nice report of the code coverage, thanks to the pytest-cov plugin
(already installed in the virtual environment as development dependency as per `pyproject.toml`_).


To set up this option in PyCharm, right click on the ``tests`` folder and ``Modify Run Configuration...``,
then add the following option in the ``Additional Arguments`` field:

    ..  image:: devtools/images/pycharm-menu_modify_test_run_config.png
        :alt: PyCharm tests contextual menu: modify run configuration
        :width: 30%

    ..  image:: devtools/images/pycharm-dialog_edit_test_run_config.png
        :alt: PyCharm dialog: edit tests run configuration
        :width: 60%

Select ``pytest in tests``, and add the following option in the ``Additional Arguments`` field::

    --cov --cov-report html

Then, run the tests as usual, and you will get a nice report of the code coverage.

.. note::

    Running tests with coverage disables the debugger, so breakpoints will be ignored.

Some useful plugins for PyCharm
--------------------------------
Here is a suggestion for some plugins you can install in PyCharm.

- `Toml`_, to edit and validate ``pyproject.toml`` file.
- `IdeaVim`_, for Vim lovers.
- `GitHub Copilot`_, for AI assisted coding.

.. _PyCharm: https://www.jetbrains.com/pycharm/

.. _Toml: https://plugins.jetbrains.com/plugin/8195-toml/
.. _IdeaVim: https://plugins.jetbrains.com/plugin/164-ideavim/
.. _GitHub Copilot: https://plugins.jetbrains.com/plugin/17718-github-copilot

.. _pyproject.toml: pyproject.toml
.. _.pre-commit-config.yaml: .pre-commit-config.yaml


Copyright
^^^^^^^^^
Copyright (c) 2024-2026 Mira Geoscience Ltd.
