from __future__ import annotations

import inspect
import itertools
from abc import ABC
from enum import IntEnum, Enum
from typing import Union, TypeVar, Any, Optional, List, Type, Callable, cast, Dict, Tuple, Iterator

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
#   mesh.algs.glyph(...)
# Need a newer version of stubgen for --inspect-mode to work
# Assert all init_args and ivs are unique
# Don't really need InitArg as distinct from Argument -- only need IVar as a subclass
#   - Properties have optional getter/setter or custom getter/setter
#   - So the init_arg fn is not actually a special case
# Support for autowrapping arrays
# InitArgs can add parameter docs to set_fn
#

def snake_to_camel_case(name: str) -> str:
    return ''.join(word.title() for word in name.split('_'))


def make_enum(cls_name, names: Tuple[str, ...]) -> Type[Enum]:
    # IntEnum defaults to starting at 1
    return IntEnum(f'_{cls_name}_enum', tuple([name, i] for (i, name) in enumerate(names)))


_SENTINEL = object()


class Argument:
    def __init__(
            self,
            name: str,
            typ: Any,
            desc: Optional[Union[str, List[str]]] = None,
            superclass: Optional[Type[_T_Alg]] = None,
            default=_SENTINEL,
    ):
        _ = superclass  # Might be used by subclasses, not here
        self.name = name
        self.is_enum = False

        if isinstance(typ, tuple) and all(isinstance(el, str) for el in typ):
            typ = make_enum(name, typ)

        if isinstance(typ, type):
            if issubclass(typ, (IntEnum, AnnotatedIntEnum)):
                self.is_enum = True
                self.typestr = 'str'
            else:
                self.typestr = typ.__name__
        elif isinstance(typ, tuple):  # e.g. (float, float)
            self.typestr = f"({', '.join(str(el.__name__) for el in typ)})"
        else:
            self.typestr = str(typ)

        self.typ = typ
        self.desc: List[str] = desc.split('\n') if isinstance(desc, str) else desc
        if self.is_enum:
            allowable = ', '.join(f"'{v.name}'" for v in self.typ)
            self.desc.append(f"Allowable values are {allowable}.")

        self.default = default

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

        return docscrape.Parameter(name=name, type='', desc=self.desc)

    @classmethod
    def from_any(cls, alg: _T_Alg, obj: Any):
        if isinstance(obj, cls):
            return obj
        elif isinstance(obj, tuple):
            return cls(*obj)
        else:
            raise NotImplementedError(f"Can't construct {cls.__name__} from {obj}")


class IVar(Argument):
    def __init__(
            self,
            name: str,
            typ: Any,
            desc: Optional[Union[str, List[str]]] = None,
            vtkname: Optional[str] = None,
            default=_SENTINEL,
            init: bool = False,
            setter=_SENTINEL,
            getter=_SENTINEL,
    ):
        super().__init__(name=name, typ=typ, desc=desc, default=default)
        self.vtkname = vtkname or snake_to_camel_case(self.name)
        self.init = init
        self.setter = setter  # TODO
        self.getter = getter

    def install_property(self, cls: Type[_T_Filt]):
        name, typ = self.vtkname, self.typ
        get_ivar, set_ivar = getattr(cls, f'Get{name}'), getattr(cls, f'Set{name}')

        if self.is_enum:
            # Convert to/from strings by default
            def fget(alg) -> str:
                return typ(get_ivar(alg)).name

            def fset(alg, val: str):
                val = typ[val].value
                set_ivar(alg, val)
        else:
            def fget(alg):
                return get_ivar(alg)

            def fset(alg, val):
                set_ivar(alg, val)

            _set_in_out_types(fget, out_type=self.typestr)
            _set_in_out_types(fset, in_type=self.typestr)

        setattr(cls, self.name, property(fget, fset, doc='\n'.join(self.desc)))


class InitArg(Argument):
    def __init__(
            self,
            name: str,
            typ: _T,
            desc: Optional[Union[str, List[str]]] = None,
            fn: Optional[Union[Callable[[_T_Alg, _T], None]], str] = None,
    ):
        super().__init__(name=name, typ=typ, desc=desc)
        self.fn = fn or 'set_' + name


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

    def __init_subclass__(cls, **kwargs):
        if not cls._wrapper:
            return

        for iv in cls._wrapper.ivars:
            iv.install_property(cls)

        for arg in cls._wrapper.init_args:
            if isinstance(arg.fn, str):
                # Because the FilterWrapper may have been defined before class methods had been created,
                # convert from strings to actual functions here
                arg.fn = getattr(cls, arg.fn)

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
            superclass: Type[_T_Alg],
            input_data_desc: Optional[str] = 'Input data',
            init_args: Optional[List] = None,
            ivars: Optional[List] = None,
    ):
        self.superclass = superclass
        self.init_args = [InitArg.from_any(superclass, arg) for arg in init_args] if init_args else []
        self.ivars = [IVar.from_any(superclass, iv) for iv in ivars] if ivars else []

        if input_data_desc is not None:
            self.init_args = [
                InitArg(
                    name='input_data',
                    typ=_Input,
                    desc=input_data_desc,
                    fn=FilterBase.set_input,
                )
            ] + self.init_args

    def _iter_init_args(self) -> Iterator[Argument]:
        yield from self.init_args
        for iv in self.ivars:
            if iv.init:
                yield iv

    def install_init(self, cls: Type[_T_Filt]):
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

        for arg in self._iter_init_args():
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
