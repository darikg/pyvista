import importlib
import os
import sys

# enable autodoc to load local modules
from typing import get_args

from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.parsers.rst.directives import unchanged
from docutils.statemachine import ViewList
from jinja2 import Template
from sphinx import addnodes
from sphinx.addnodes import desc_signature
from sphinx.domains.python import PyObject
from sphinx.errors import SphinxError
from sphinx.ext.autodoc import AttributeDocumenter, ObjectMembers, PropertyDocumenter, DocstringStripSignatureMixin, \
    ClassLevelDocumenter, ModuleLevelDocumenter, annotation_option
from sphinx.util import nested_parse_with_titles
from sphinx.util.docutils import SphinxDirective
from sphinx.util.typing import stringify_annotation

from pyvista.core.ivars import IVar, SimpleIVar

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


def ivar_process_signature(app, what, name, obj, options, signature: str, return_annotation):
    from pyvista.core.ivars import IVar
    if isinstance(obj, type) and issubclass(obj, IVar):
        print('sig', type(signature), signature)
        # signature.replace(parameters=[inspect.Parameter("foo", kind=inspect.Parameter.KEYWORD_ONLY)])
        return 'foo', "bar"


class IVarDocumenter(DocstringStripSignatureMixin, ClassLevelDocumenter):
    directivetype = "ivar"
    objtype = "ivar"
    priority = PropertyDocumenter.priority + 1
    # member_order = -100  # This puts properties first in the docs

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return isinstance(member, IVar)

    def document_members(self, all_members: bool = False) -> None:
        pass

    def import_object(self, raiseerror: bool = False) -> bool:
        ret = super().import_object(raiseerror)
        if self.parent:
            AttributeDocumenter.update_annotations(self, self.parent)
            # self.update_annotations(self.parent)

        return ret

    def add_directive_header(self, sig: str) -> None:
        super().add_directive_header(sig)
        sourcename = self.get_sourcename()

        ivar: IVar = self.object
        types = ivar._types()
        if types is None:
            types = None, None
            if anno := self.parent.__annotations__.get(ivar.name):
                if isinstance(self.object, SimpleIVar):
                    typ = get_args(anno)
                    types = (typ, typ)
                else:
                    types = get_args(anno)

        get_type, set_type = types
        if self.object.fget is None:
            get_type = None
        if self.object.fset is None:
            set_type = None

        get_type = stringify_annotation(get_type, mode='smart') if get_type else None
        set_type = stringify_annotation(set_type, mode='smart') if set_type else None

        self.add_line('   :gettype: ' + get_type, sourcename)
        self.add_line('   :settype: ' + set_type, sourcename)

    def get_object_members(self, want_all: bool) -> tuple[bool, ObjectMembers]:
        return False, []


class IvarDirective(PyObject):
    has_content = True
    required_arguments = 0
    optional_arguments = 3
    option_spec = {"module": unchanged, "gettype": unchanged, "settype": unchanged}

    def handle_signature(self, sig: str, signode: desc_signature) -> tuple[str, str]:
        fullname, prefix = super().handle_signature(sig, signode)  # class, ivar_name
        get_type: str = self.options.get('gettype')
        from sphinx.domains.python import _parse_annotation
        if get_type:
            print('adding_get_type', get_type, type(get_type))
            signode += addnodes.desc_annotation(get_type, '',
                                                addnodes.desc_sig_punctuation('', ':'),
                                                addnodes.desc_sig_space(),
                                                *_parse_annotation(get_type, self.env))
        # if typ:
        #     annotations = _parse_annotation(typ, self.env)
        #     signode += addnodes.desc_annotation(typ, '',
        #                                         addnodes.desc_sig_punctuation('', ':'),
        #                                         addnodes.desc_sig_space(),
        #                                         *annotations)

        return fullname, prefix

    def get_signature_prefix(self, sig: str) -> list[nodes.Node]:
        return [
            nodes.Text('ivar'),
            addnodes.desc_sig_space(),
        ]

    def get_index_text(self, modname: str, name: tuple[str, str]) -> str:
        pass


def setup(app):
    # app.connect("autodoc-process-signature", ivar_process_signature)
    # app.connect("autodoc-before-process-signature", ivar_before_process_signature)
    app.add_directive_to_domain("py", "ivar", IvarDirective)
    app.add_autodocumenter(IVarDocumenter)
    pass