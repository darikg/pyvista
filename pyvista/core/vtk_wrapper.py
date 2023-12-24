import inspect
from typing import Iterator, Dict, Self, Any

from pyvista.core.ivars import IVar, _Hints


_SENTINEL = object()


def signature_parameter(ivar: IVar, optional=True, default=None) -> inspect.Parameter:
    return inspect.Parameter(
        name=ivar.name,
        annotation=f'Optional[{self.typestr}]' if optional else self.typestr,
        default=default,
        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )


class VtkWrapper:
    _ivar_types: Dict[str, _Hints] = {}

    @classmethod
    def iter_ivars(cls) -> Iterator[IVar]:
        for _name, ivar in inspect.getmembers(cls, lambda x: isinstance(x, IVar)):
            yield ivar

    @classmethod
    def update_ivar_types(cls):
        ivar_types = cls._ivar_types = {}
        annotations = inspect.get_annotations(cls, eval_str=True)

        for ivar in cls.iter_ivars():
            if types := ivar.get_type_hints(anno=annotations.get(ivar.name)):
                get_type, set_type = types
                get_type = None if ivar.fget is None else get_type
                set_type = None if ivar.fset is None else set_type
                ivar_types[ivar.name] = (get_type, set_type)

    def _post_init(self, **kwargs):
        if kwargs:
            names = ', '.join(kwargs.keys())
            raise ValueError(f"Unrecognized init kwargs {names}")

    def set_ivars(self, kwargs: Dict[str, Any]):
        for ivar in self.iter_ivars():
            if (val := kwargs.pop(ivar.name, _SENTINEL)) is not _SENTINEL:
                setattr(self, ivar.name, val)

    @classmethod
    def _install_init(cls):

        def __init__(self: Self, **kwargs):
            self.set_ivars(kwargs=kwargs)  # pops applicable kwargs here
            self._post_init(**kwargs)

        cls.__init__ = __init__

        # Update the __init__ signature and docstr
        sig = inspect.signature(__init__)
        sig_params = [param for (name, param) in sig.parameters.items() if name != 'kwargs']
        doc_params = []

        for ivar in cls.iter_ivars():
            sig_params.append(arg.signature_parameter(optional=True, default=arg.default))
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

