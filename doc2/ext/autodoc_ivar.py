from __future__ import annotations

import inspect
from enum import IntEnum
from typing import TYPE_CHECKING, Any

from docutils.statemachine import StringList
from sphinx.application import Sphinx
from sphinx.ext.autodoc import ClassDocumenter, bool_option, ClassLevelDocumenter, ObjectMembers, AttributeDocumenter, \
    PropertyDocumenter, DocstringStripSignatureMixin
from sphinx.util.inspect import safe_getattr
from sphinx.util.typing import stringify_annotation

from pyvista.core.ivars import IVar


class IvarDocumenter(DocstringStripSignatureMixin, ClassLevelDocumenter):
    objtype = 'property'
    directivetype = PropertyDocumenter.objtype  # TODO add ivar directive somehow
    priority = 1 + PropertyDocumenter.priority
    # option_spec = dict(AttributeDocumenter.option_spec)

    def get_object_members(self, want_all: bool) -> tuple[bool, ObjectMembers]:
        return False, []

    @classmethod
    def can_document_member(cls,
                            member: Any, membername: str,
                            isattr: bool, parent: Any) -> bool:
        try:
            return isinstance(member, IVar)
        except TypeError:
            return False

    # def add_content(self,
    #                 more_content: StringList | None,
    #                 ) -> None:
    #
    #     # super().add_content(more_content)
    #
    #     source_name = self.get_sourcename()
    #     ivar: IVar = self.object
    #     self.add_line('', source_name)
    #     self.add_line('foo bar baz', source_name)
    #     # self.add_line(ivar.__doc__, source_name)
    #     self.add_line('', source_name)

    def add_directive_header(self, sig: str) -> None:
        super().add_directive_header(sig)
        sourcename = self.get_sourcename()
        func = self._get_property_getter()
        if func is None or self.config.autodoc_typehints == 'none':
            print("func is none")
            return

        from sphinx.util.inspect import signature as sphinx_sig
        try:
            signature = sphinx_sig(func,
                                          type_aliases=self.config.autodoc_type_aliases)
            if signature.return_annotation is not inspect.Parameter.empty:
                if self.config.autodoc_typehints_format == "short":
                    objrepr = stringify_annotation(signature.return_annotation, "smart")
                else:
                    objrepr = stringify_annotation(signature.return_annotation,
                                                   "fully-qualified-except-typing")
                self.add_line('   :type: ' + objrepr, sourcename)
                # self.add_line('what ' + objrepr, sourcename)
        except TypeError as exc:
            print("Failed to get a function signature for %s: %s",
                           self.fullname, exc)
            pass
        except ValueError:
            pass

    def _get_property_getter(self):
        if safe_getattr(self.object, 'fget', None):  # property
            return self.object.fget
        if safe_getattr(self.object, 'func', None):  # cached_property
            return self.object.func
        return None

    def format_args(self, **kwargs: Any) -> str | None:
        func = self._get_property_getter()
        if func is None:
            return None

        # update the annotations of the property getter
        self.env.app.emit('autodoc-before-process-signature', func, False)
        # correctly format the arguments for a property
        return super().format_args(**kwargs)

    # def format_signature(self, **kwargs: Any) -> str:
    #     return "the sig"


def setup(app: Sphinx) -> None:
    app.setup_extension('sphinx.ext.autodoc')  # Require autodoc extension
    app.add_autodocumenter(IvarDocumenter)
