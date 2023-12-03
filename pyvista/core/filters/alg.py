from __future__ import annotations

import inspect
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


class IVar:
    def __init__(
            self, pvname: str, typ: Any, desc: Optional[Union[str, List[str]]] = None, vtkname: Optional[str] = None):
        self.pvname = pvname
        self.vtkname = vtkname or snake_to_camel_case(pvname)
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

    def property_desc(self):
        if isinstance(self.desc, str):
            return self.desc
        else:
            return '\n'.join(self.desc)

    def install(self, cls: _T_Alg):
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

        setattr(cls, self.pvname, property(fget, fset, doc=self.property_desc()))

    @classmethod
    def from_any(cls, alg: _T_Alg, obj: Any):
        if isinstance(obj, IVar):
            return obj
        elif isinstance(obj, tuple):
            return IVar(*obj)
        else:
            raise NotImplementedError(f"Can't construct IVar from {obj}")

    def numpydoc_name(self, optional=True) -> str:
        typestr = self.typestr.replace('typing.', '')
        out = self.pvname + ' : ' + typestr
        if optional:
            out += ', optional'
        return out

    def numpydoc_desc(self) -> List[str]:
        if isinstance(self.desc, list):
            out = self.desc
        else:
            out = [self.desc]

        if self.is_annotated_int_enum:
            allowable = ', '.join(f"'{v.annotation.lower()}'" for v in self.typ)
            out.append(f"Allowable values are {allowable}.")

        return out


_SENTINEL = object()


class FilterBase(ABC):
    _wrapper: Optional[FilterWrapper] = None
    _ivar_names: FrozenSet[str] = frozenset()

    def __init__(self, input_data: Optional[_Input] = None, kwargs: Optional[Dict[str, Any]] = None):
        """
            Parameters
            ----------
            input_data: DataSource, optional
                The input mesh to which the glyph geometry is copied to each point.
        """
        if kwargs:
            for name in self._ivar_names:
                if (val := kwargs.pop(name, _SENTINEL)) is not _SENTINEL:
                    setattr(self, name, val)

        if input_data:
            self.set_input(input_data)

    def __init_subclass__(cls, **kwargs):
        if cls._wrapper:
            ivars = cls._wrapper.install_ivars(cls)
            cls._wrapper.install_init(cls, ivars)

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
    def __init__(self, superclass: _T_Alg, ivars: Optional[List] = None):
        self._ivars = ivars
        self._superclass = superclass

    def install_ivars(self, cls: Type[_T_Filt]) -> List[IVar]:
        """Add properties to the filter class converting from {Get/Set}Property to .property"""
        ivars = []
        for spec in self._ivars:
            ivar = IVar.from_any(cls, spec)
            ivar.install(cls)
            ivars.append(ivar)
        return ivars

    def install_init(self, cls: _T_Alg, ivars: List[IVar]):
        """Add the default __init__ to the filter class"""
        cls._ivar_names = frozenset(iv.pvname for iv in ivars)
        cls.__doc__ = cls.__doc__ or cls.__name__

        if cls.__init__ in (self._superclass.__init__, FilterBase.__init__):
            # Subclass hasn't overridden __init__
            def __init__(alg: _T_Alg, **kwargs):
                self._superclass.__init__(alg)
                input_data = kwargs.pop('input_data', None)
                FilterBase.__init__(alg, input_data=input_data, kwargs=kwargs)
                alg.__post_init__(**kwargs)

            cls.__init__ = __init__

        # Update the __init__ signature
        sig_params = [param for (name, param) in _FILTERBASE_INIT_SIG.parameters.items() if name != 'kwargs']
        sig_params.extend(
            inspect.Parameter(
                name=iv.pvname,
                annotation=f'Optional[{iv.typestr}]',
                default=None,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
            for iv in ivars
        )

        # Update the docstr
        docstr = docscrape.NumpyDocString(cls.__doc__)
        docstr['Parameters'].extend(
            docscrape.Parameter(
                name=iv.numpydoc_name(optional=True),
                type='',
                desc=iv.numpydoc_desc(),
            )
            for iv in ivars
        )

        # Merge signature params and docstr
        sig_params.extend(
            param for (name, param) in inspect.signature(cls.__post_init__).parameters.items()
            if name != 'self'
        )
        if cls.__post_init__.__doc__:
            for (section, contents) in docscrape.FunctionDoc(cls.__post_init__).items():
                if section == 'index':
                    continue  # docstr['index'].update(contents)?
                docstr[section] += contents

        cls.__init__.__signature__ = _FILTERBASE_INIT_SIG.replace(parameters=sig_params)
        cls.__doc__ = str(docstr)


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
