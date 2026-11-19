# ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#  Copyright (c) 2024-2025 Mira Geoscience Ltd.                                          '
#                                                                                        '
#  This file is part of grid-apps package.                                     '
#                                                                                        '
#  grid-apps is distributed under the terms and conditions of the MIT License  '
#  (see LICENSE file at the root of this source code package).                           '
#                                                                                        '
# ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

import os
from datetime import datetime
from importlib.metadata import version as get_version

from docutils import nodes
from packaging.version import Version


# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "grid-apps"
author = "Mira Geoscience Ltd."
project_copyright = "%Y, Mira Geoscience Ltd"

package_name = "grid-apps"

full_version = Version(get_version(package_name))
release = full_version.public
if full_version.is_postrelease:
    release = release.rsplit(".post", 1)[0]
version = full_version.base_version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

nitpicky = True

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_issues",
    "sphinxcontrib.googleanalytics",
]

intersphinx_mapping = {
    "discretize": ("https://discretize.simpeg.xyz/en/main/", None),
    "geoh5py": (
        "https://mirageoscience-geoh5py.readthedocs-hosted.com/en/stable/",
        None,
    ),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
    "python": ("https://docs.python.org/3.14/", None),
}

templates_path = ["_templates"]
exclude_patterns = []

googleanalytics_id = os.environ.get("GOOGLE_ANALYTICS_ID", "")
googleanalytics_enabled = bool(googleanalytics_id)

issues_github_path = f"mirageoscience/{package_name}"

# -- Options for auto-doc ----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#module-sphinx.ext.autodoc

autodoc_typehints = "signature"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "alabaster"
html_theme_options = {
    "description": f"version {release}",
}

# Enable numref
numfig = True


def get_copyright_notice():
    return f"Copyright {datetime.now().strftime(project_copyright)}"


rst_epilog = f"""
.. |copyright_notice| replace:: {get_copyright_notice()}.
"""


def resolve_external_type(app, env, node, contnode):
    if node.get("refdomain") != "py":
        return None

    source_links = {
        "geoapps_utils.base.Driver": "https://github.com/MiraGeoscience/geoapps-utils/blob/release/ga-4.9/geoapps_utils/base.py#L53",
        "geoapps_utils.base.Options": "https://github.com/MiraGeoscience/geoapps-utils/blob/release/ga-4.9/geoapps_utils/base.py#L227",
    }
    target = node.get("reftarget")
    if target in source_links:
        return nodes.reference("", "", contnode, refuri=source_links[target])

    aliases = {
        "Path": "pathlib.Path",
        "UIJsonGroup": "geoh5py.groups.uijson.UIJsonGroup",
        "FloatData": "geoh5py.data.float_data.FloatData",
        "ReferencedData": "geoh5py.data.referenced_data.ReferencedData",
        "BlockModel": "geoh5py.objects.block_model.BlockModel",
        "Points": "geoh5py.objects.points.Points",
        "CellObject": "geoh5py.objects.cell_object.CellObject",
        "GridObject": "geoh5py.objects.grid_object.GridObject",
        "geoh5py.objects.Octree": "geoh5py.objects.octree.Octree",
    }
    if target in aliases:
        node["reftarget"] = aliases[target]
    return None


def setup(app):
    app.connect("missing-reference", resolve_external_type, priority=400)
