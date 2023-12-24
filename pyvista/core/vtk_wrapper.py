import inspect
from dataclasses import dataclass
from functools import cached_property
from typing import Iterator, Dict, Self, Any, TypeVar, dataclass_transform, Optional

from pyvista.core.ivars import IVar, _Hints


_SENTINEL = object()

_T_Wrapped = TypeVar('_T_Wrapped', bound=type)


def _signature_parameter(ivar: IVar, optional=True, default=None) -> inspect.Parameter:
    return inspect.Parameter(
        name=ivar.name,
        annotation=f'Optional[{self.typestr}]' if optional else self.typestr,
        default=default,
        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )


def _iter_ivars(obj: object) -> Iterator[IVar]:
    for _name, ivar in inspect.getmembers(obj, lambda m: isinstance(m, IVar)):
        yield ivar


def _set_ivars(obj: object, ivars: Dict[str, Any]) -> None:
    avail_ivars = {iv.name: iv for iv in _iter_ivars(obj)}

    for name, val in ivars.items():  # Assume ivars is an ordered dict, set ivar values in that order
        if name in avail_ivars:
            ivars.pop(name)
            setattr(obj, name, val)


def _build_init(cls: type):
    orig_init = cls.__init__

    def __init__(self, /, **kwargs):
        orig_init(self)
        _set_ivars(self, kwargs)  # Pops ivars
        if hasattr(self, '__post_init__'):
            self.__post_init__(**kwargs)  # Handle remaining init kwargs
        elif kwargs:
            names = ', '.join(kwargs.keys())
            raise TypeError(f'Unexpected keyword arguments {names}')

    sig = inspect.signature(__init__)
    sig_params = [param for (name, param) in sig.parameters.items() if name != 'kwargs']
    doc_params = []

    for ivar in _iter_ivars(cls):
        sig_params.append(_signature_parameter(ivar, optional=True))  # default=arg.default
        # doc_params.append(arg.numpydoc_parameter(optional=True))

    # cls.__init__.__signature__ = sig.replace(parameters=sig_params)
    # docstr = docscrape.NumpyDocString(cls.__doc__)
    # docstr['Parameters'].extend(doc_params)

    if hasattr(cls, '__post_init__'):
        # Merge signature params and docstr
        # if cls.__post_init__.__doc__:
        #     for (section, contents) in docscrape.FunctionDoc(cls.__post_init__).items():
        #         if section == 'index':
        #             continue  # docstr['index'].update(contents)?
        #         docstr[section] += contents
        #
        # cls.__doc__ = str(docstr)

        for param in inspect.signature(cls.__post_init__).parameters.values():
            if param.name != 'self':
                sig_params.append(param)

    __init__.__signature__ = sig.replace(parameters=sig_params)
    return __init__


@dataclass_transform(field_specifiers=(IVar,))
def vtk_wrapper(init=True):
    def wrap(cls: _T_Wrapped) -> _T_Wrapped:
        cls.__vtk_wrapper = _VtkWrapper(cls)
        if init:
            cls.__init__ = _build_init(cls)
        return cls

    return wrap


class _VtkWrapper:
    def __init__(self, cls: type):
        self.cls = cls
        self.ivars = {iv.name: iv for iv in _iter_ivars(cls)}

    @cached_property
    def _types(self) -> Dict[str, _Hints]:
        types = {}
        annotations = inspect.get_annotations(self.cls, eval_str=True)

        for ivar in self.ivars.keys():
            if types := ivar.get_type_hints(anno=annotations.get(ivar.name)):
                get_type, set_type = types
                get_type = None if ivar.fget is None else get_type
                set_type = None if ivar.fset is None else set_type
                types[ivar.name] = (get_type, set_type)

        return types
