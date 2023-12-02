import os
import sys

# enable autodoc to load local modules
sys.path.insert(0, os.path.abspath("."))

project = "<project>"
copyright = "year, author"
author = "author"
extensions = [
    "enum_tools.autoenum",
    "notfound.extension",
    "numpydoc",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
#    "sphinx.ext.linkcode",  # This adds the button ``[Source]`` to each Python API site by calling ``linkcode_resolve``
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "sphinx_design",
]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
templates_path = ["_templates"]

html_static_path = ["_static"]
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None)
}
html_theme_options = {"nosidebar": True}

# See https://numpydoc.readthedocs.io/en/latest/install.html
numpydoc_use_plots = True
numpydoc_show_class_members = False
numpydoc_xref_param_type = True

# linkcheck ignore entries
nitpick_ignore_regex = [
    (r'py:.*', '.*ColorLike'),
    (r'py:.*', '.*lookup_table_ndarray'),
    (r'py:.*', 'ActiveArrayInfo'),
    (r'py:.*', 'FieldAssociation'),
    (r'py:.*', 'VTK'),
    (r'py:.*', 'colors.Colormap'),
    (r'py:.*', 'cycler.Cycler'),
    (r'py:.*', 'ipywidgets.Widget'),
    (r'py:.*', 'meshio.*'),
    (r'py:.*', 'networkx.*'),
    (r'py:.*', 'of'),
    (r'py:.*', 'optional'),
    (r'py:.*', 'or'),
    (r'py:.*', 'pyvista.LookupTable.n_values'),
    (r'py:.*', 'pyvista.PVDDataSet'),
    (r'py:.*', 'sys.float_info.max'),
    (r'py:.*', 'various'),
    (r'py:.*', 'vtk.*'),
]

add_module_names = False

# Autosummary configuration
autosummary_context = {
    # Methods that should be skipped when generating the docs
    # __init__ should be documented in the class docstring
    # override is a VTK method
    "skipmethods": ["__init__", "override"]
}

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
import pydata_sphinx_theme  # noqa

html_theme = "pydata_sphinx_theme"
html_context = {
    "github_user": "pyvista",
    "github_repo": "pyvista",
    "github_version": "main",
    "doc_path": "doc/source",
    "examples_path": "examples",
}
html_show_sourcelink = False
html_copy_source = False

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
html_show_sphinx = False
cname = os.getenv("DOCUMENTATION_CNAME", "docs.pyvista.org")



html_theme_options = {
    "analytics": {"google_analytics_id": "UA-140243896-1"},
    "show_prev_next": False,
    "github_url": "https://github.com/pyvista/pyvista",
    "collapse_navigation": True,
    "use_edit_page_button": True,
    "icon_links": [
        {
            "name": "Slack Community",
            "url": "http://slack.pyvista.org",
            "icon": "fab fa-slack",
        },
        {
            "name": "Support",
            "url": "https://github.com/pyvista/pyvista/discussions",
            "icon": "fa fa-comment fa-fw",
        },
        {
            "name": "Contributing",
            "url": "https://github.com/pyvista/pyvista/blob/main/CONTRIBUTING.rst",
            "icon": "fa fa-gavel fa-fw",
        },
        {
            "name": "The Paper",
            "url": "https://doi.org/10.21105/joss.01450",
            "icon": "fa fa-file-text fa-fw",
        },
    ],
    "check_switcher": False,
    "navbar_end": ["version-switcher", "theme-switcher", "navbar-icon-links"],
}

# sphinx-panels shouldn't add bootstrap css since the pydata-sphinx-theme
# already loads it
panels_add_bootstrap_css = False
pygments_style = "friendly"

