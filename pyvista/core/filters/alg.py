from __future__ import annotations

import inspect
import itertools
from abc import ABC
from typing import Union, TypeVar, Any, Optional, List, Type, Callable, cast, Dict, FrozenSet

from numpydoc import docscrape

from pyvista import AnnotatedIntEnum
from pyvista.core import _vtk_core as _vtk

_Input = Union[_vtk.vtkDataSet, _vtk.vtkAlgorithmOutput]
_T_Enum = TypeVar('_T_Enum', bound=AnnotatedIntEnum)
_T_Alg = TypeVar('_T_Alg', bound=_vtk.vtkAlgorithm)
_T = TypeVar('_T')
DataSource = Union[_vtk.vtkDataSet, _vtk.vtkAlgorithmOutput]


# TODO clean up build_init
# Auto generation of enums
# Need some sort of separation for specifying properties separately from ivars
#   mesh.algs.glyph(...)
# Need a newer version of stubgen for --inspect-mode to work


def snake_to_camel_case(name: str) -> str:
    return ''.join(word.title() for word in name.split('_'))


class Argument:
    def __init__(
            self,
            name: str,
            typ: Any,
            desc: Optional[Union[str, List[str]]] = None,
    ):
        self.name = name
        self.typ = typ
        self.is_annotated_int_enum = False

        if isinstance(typ, type):
            if issubclass(typ, AnnotatedIntEnum):
                self.is_annotated_int_enum = True
                self.typestr = 'str'
            else:
                self.typestr = typ.__name__
        elif isinstance(typ, tuple):  # e.g. (float, float)
            self.typestr = f"({', '.join(str(el.__name__) for el in typ)})"
        else:
            self.typestr = str(typ)

        self.desc = desc

    def signature_parameter(self, optional=True, default=None) -> inspect.Parameter:
        return inspect.Parameter(
            name=self.name,
            annotation=f'Optional[{self.typestr}]' if optional else self.typestr,
            default=default,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )

    def numpydoc_parameter(self, optional=True) -> docscrape.Parameter:
        typestr = self.typestr.replace('typing.', '')
        name = self.name + ' : ' + typestr
        if optional:
            name += ', optional'

        desc = self.desc if isinstance(self.desc, list) else [self.desc]

        # TODO this should happen for ivar.install_property description too.
        if self.is_annotated_int_enum:
            allowable = ', '.join(f"'{v.annotation.lower()}'" for v in self.typ)
            desc.append(f"Allowable values are {allowable}.")

        return docscrape.Parameter(name=name, type='', desc=desc)

    @classmethod
    def from_any(cls, alg: _T_Alg, obj: Any):
        if isinstance(obj, IVar):
            return obj
        elif isinstance(obj, tuple):
            return cls(*obj)
        else:
            raise NotImplementedError(f"Can't construct {cls.__name__} from {obj}")


class IVar(Argument):
    def __init__(self, *args, vtkname: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.vtkname = vtkname or snake_to_camel_case(self.name)

    def install_property(self, cls: FilterBase):
        name, typ = self.vtkname, self.typ

        if self.is_annotated_int_enum:
            # Convert to/from strings by default
            def fget(alg) -> str:
                return typ(getattr(alg, f'Get{name}')()).annotation

            def fset(alg, val: str):
                getattr(alg, f'Set{name}')(typ.from_str(val).value)
        else:
            def fget(alg):
                return getattr(alg, f'Get{name}')()

            def fset(alg, val):
                getattr(alg, f'Set{name}')(val)

            _set_in_out_types(fget, out_type=self.typestr)
            _set_in_out_types(fset, in_type=self.typestr)

        doc = self.desc if isinstance(self.desc, str) else '\n'.join(self.desc)
        setattr(cls, self.name, property(fget, fset, doc=doc))


_SENTINEL = object()


class InitArg(Argument):
    def __init__(self, *args, fn: Callable, **kwargs):
        super().__init__(*args, **kwargs)
        self.fn = fn


class FilterBase(ABC):
    _wrapper: Optional[FilterWrapper] = None

    def __init__(self, kwargs: Optional[Dict[str, Any]] = None):
        if not kwargs:
            return

        for arg in self._wrapper.init_args:
            if (val := kwargs.pop(arg.name, _SENTINEL)) is not _SENTINEL:
                arg.fn(self, val)

        for iv in self._wrapper.ivars:
            if (val := kwargs.pop(iv.name, _SENTINEL)) is not _SENTINEL:
                setattr(self, iv.name, val)

    def __init_subclass__(cls: FilterBase, **kwargs):
        if cls._wrapper:
            for iv in cls._wrapper.ivars:
                iv.install_property(cls)

            cls._wrapper.install_init(cls)

    def set_input(self, input_data: _Input) -> None:
        alg = cast(_vtk.vtkAlgorithm, self)
        if isinstance(input_data, _vtk.vtkDataSet):
            alg.SetInputData(input_data)
        else:
            alg.SetInputConnection(input_data)

    def __post_init__(self): ...


_T_Filt = TypeVar('_T_Filt', bound=FilterBase)
_FILTERBASE_INIT_SIG = inspect.signature(FilterBase.__init__)


class FilterWrapper:
    def __init__(
            self,
            superclass: _T_Alg,
            init_args: Optional[List] = None,
            ivars: Optional[List] = None,
    ):
        self.superclass = superclass
        self.init_args = [InitArg.from_any(superclass, arg) for arg in init_args]
        self.ivars = [IVar.from_any(superclass, iv) for iv in ivars]

    def install_init(self, cls: FilterBase):
        """Add the default __init__ to the filter class"""
        cls.__doc__ = cls.__doc__ or cls.__name__

        if cls.__init__ in (self.superclass.__init__, FilterBase.__init__):
            # Subclass hasn't overridden __init__
            def __init__(alg: _T_Alg, **kwargs):
                self.superclass.__init__(alg)
                FilterBase.__init__(alg, kwargs=kwargs)  # FilterBase.__init__ pops applicable kwargs here
                alg.__post_init__(**kwargs)

            cls.__init__ = __init__

        # Update the __init__ signature and docstr
        sig_params = [param for (name, param) in _FILTERBASE_INIT_SIG.parameters.items() if name != 'kwargs']
        doc_params = []

        for arg in itertools.chain(self.init_args, self.ivars):
            sig_params.append(arg.signature_parameter(optional=True, default=None))
            doc_params.append(arg.numpydoc_parameter(optional=True))

        cls.__init__.__signature__ = _FILTERBASE_INIT_SIG.replace(parameters=sig_params)
        docstr = docscrape.NumpyDocString(cls.__doc__)
        docstr['Parameters'].extend(doc_params)

        # Merge signature params and docstr
        if cls.__post_init__.__doc__:
            for (section, contents) in docscrape.FunctionDoc(cls.__post_init__).items():
                if section == 'index':
                    continue  # docstr['index'].update(contents)?
                docstr[section] += contents

        cls.__doc__ = str(docstr)

        for param in inspect.signature(cls.__post_init__).parameters.values():
            if param.name != 'self':
                sig_params.append(param)

        cls.__init__.__signature__ = _FILTERBASE_INIT_SIG.replace(parameters=sig_params)


def _set_in_out_types(fn: Callable, in_type: Optional[str] = None, out_type: Optional[str] = None):
    sig = inspect.signature(fn)
    if in_type:
        params = list(sig.parameters.values())
        assert len(params) == 2  # self, val
        params = [params[0], params[1].replace(annotation=in_type)]
        sig = sig.replace(parameters=params)
    if out_type:
        sig = sig.replace(return_annotation=out_type)
    fn.__signature__ = sig
