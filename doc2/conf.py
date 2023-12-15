import importlib
import os
import sys

# enable autodoc to load local modules
from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.parsers.rst.directives import unchanged
from docutils.statemachine import ViewList
from jinja2 import Template
from sphinx.errors import SphinxError
from sphinx.ext.autodoc import AttributeDocumenter, ObjectMembers
from sphinx.util import nested_parse_with_titles
from sphinx.util.docutils import SphinxDirective

from pyvista.core.ivars import IVar

sys.path.insert(0, os.path.abspath("."))
sys.path.append(os.path.abspath("./ext"))

project = "<project>"
copyright = "year, author"
author = "author"
extensions = [
    # "enum_tools.autoenum",
    "notfound.extension",
    "numpydoc",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
#    "sphinx.ext.linkcode",  # This adds the button ``[Source]`` to each Python API site by calling ``linkcode_resolve``
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "sphinx_design",
    # "autodoc_enum",
    # "autodoc_ivar",
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

import inspect


def ivar_process_signature(app, what, name, obj, options, signature: inspect.signature, return_annotation):
    from pyvista.core.ivars import IVar
    if isinstance(obj, IVar):
        print('sig', signature)
        # signature.replace(parameters=[inspect.Parameter("foo", kind=inspect.Parameter.KEYWORD_ONLY)])
        return 'foo', "bar"


def ivar_before_process_signature(app, obj, bound):
    from pyvista.core.ivars import IVar

    # if isinstance(obj, IVar):
    print(obj)


class IVarDocumenter(AttributeDocumenter):
    directivetype = "ivar"
    objtype = "prop"
    priority = 20
    member_order = -100  # This puts properties first in the docs

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return isinstance(member, IVar)

    def get_object_members(self, want_all: bool) -> tuple[bool, ObjectMembers]:
        return False, []


PROP_DETAIL = Template("""
.. attribute:: {{ name }}
    :module: {{ module }}
    :annotation: = {{ default }}

    :Type: {{ type_info }}
    {% if doc %}

    {{ doc|indent(4) }}
    {% endif %}
""".strip())


class IvarDirective(SphinxDirective):

    has_content = True
    required_arguments = 1
    optional_arguments = 2
    option_spec = {"module": unchanged, "type": unchanged}

    def parse(self, rst_text, annotation):
        result = ViewList()
        for line in rst_text.split("\n"):
            result.append(line, annotation)
        node = nodes.paragraph()
        node.document = self.state.document
        nested_parse_with_titles(self.state, result, node)
        return node.children

    def run(self):

        full_name = self.arguments[0]
        model_name, prop_name = full_name.rsplit(".")
        module_name = self.options["module"]

        try:
            module = importlib.import_module(module_name)
        except ImportError:
            raise SphinxError(f"Could not generate reference docs for {full_name}: could not import module {module_name}")

        model = getattr(module, model_name, None)
        if model is None:
            raise SphinxError(f"Unable to generate reference docs for {full_name}: no model {model_name} in module {module_name}")

        # We may need to instantiate deprecated objects as part of documenting
        # them in the reference guide. Suppress any warnings here to keep the
        # docs build clean just for this case
        # with warnings.catch_warnings():
        #     warnings.filterwarnings("ignore", category=BokehDeprecationWarning)
        #     model_obj = model()

        # try:
        #     descriptor = model_obj.lookup(prop_name)
        # except AttributeError:
        #     raise SphinxError(f"Unable to generate reference docs for {full_name}: no property {prop_name} on model {model_name}")

        rst_text = PROP_DETAIL.render(
            name=prop_name,
            module=self.options["module"],
            default="default_value",   # repr(descriptor.instance_default(model_obj)),
            type_info="type info", # type_link(descriptor.property),
            doc="doc",  # if descriptor.__doc__ is None else textwrap.dedent(descriptor.__doc__),
        )

        return self.parse(rst_text, "<ivar>")



def setup(app):
    # app.connect("autodoc-process-signature", ivar_process_signature)
    # app.connect("autodoc-before-process-signature", ivar_before_process_signature)
    app.add_directive_to_domain("py", "ivar", IvarDirective)
    app.add_autodocumenter(IVarDocumenter)
    pass