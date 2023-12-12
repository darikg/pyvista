from __future__ import annotations

from typing import TypeVar, Type, Optional, Generic, Callable, cast, Dict, Union, Any, Tuple

from pyvista.core import _vtk_core as _vtk
from pyvista.core._typing_core import Number, Vector


def _snake_to_camel_case(name: str) -> str:
    return ''.join(word.title() for word in name.split('_'))


def _python_to_vtk_name(name: str) -> str:
    if name.startswith('n_'):
        return 'NumberOf' + _snake_to_camel_case(name[2:])
    else:
        return _snake_to_camel_case(name)


_T = TypeVar('_T')
_T_Vtk = Any
_T_Set = TypeVar('_T_Set')
_T_Get = TypeVar('_T_Get')
_Getter = Callable[[_T_Vtk], _T_Get]
_Setter = Callable[[_T_Vtk, _T_Set], None]


class _SENTINEL:
    pass


class IVar(Generic[_T_Get, _T_Set]):
    """Property descriptor for python subclasses of VTK classes.

    These provide properties that map to VTK IVars, providing getter and setters, similar to how the python
    `property` decorator operates. IVars are generic over the types returned by the getter and accepted by the setter.

    Parameters
    ----------
    doc: str
        The description assigned to the property's docstr.

    vtkname: str, optional
        The name of the corresponding VTK IVar. By default, the 'original_name' in snake-case is converted
        to 'OriginalName` in camelcase.

    fset: Callable[[VTK_OBJECT], GET_TYPE], optional
        A function that gets the IVar's value. If not supplied, defaults to `Get{vtkname}`.
        Supply fset=None to specify that no getter should be provided.

    fget: Callable[[VTK_OBJECT, SET_TYPE], None]], optional
        A function that sets the IVar's value. If not supplied, defaults to `Set{vtkname}`.
        Supply setter=None to specify that no setter should be provided.

    Examples
    --------
    Add a simple ivar to a subclass of vtkDistanceToCamera.
        >>> from vtkmodules.vtkRenderingCore import vtkDistanceToCamera
        >>>
        >>> class DistanceToCamera1(vtkDistanceToCamera):
        >>>     screen_size: IVar[float, float] = IVar(
        >>>         'The desired screen size obtained by scaling glyphs by the distance array.'
        >>>     )
        >>>
        >>> dtc = DistanceToCamera1()
        >>> dtc.screen_size = 100  # Equivalent to dtc.SetScreenSize(100)
        >>> dtc.screen_size
        100

    This is equivalent to the more verbose @property based approach:
        >>> class DistanceToCamera2(vtkDistanceToCamera):
        >>>     @property
        >>>     def screen_size(self) -> float:
        >>>         '''The desired screen size obtained by scaling glyphs by the distance array.'''
        >>>         return self.GetScreenSize()
        >>>
        >>>     @screen_size.setter
        >>>     def screen_size(self, val: float):
        >>>         self.SetScreenSize(val)

    """
    def __init__(
            self,
            doc: str = '',
            vtkname: Optional[str] = None,
            fget: Optional[Union[_Getter, Type[_SENTINEL]]] = _SENTINEL,
            fset: Optional[Union[_Setter, Type[_SENTINEL]]] = _SENTINEL,
    ):
        self.__doc__ = doc
        self.fget = self._default_fget if fget is _SENTINEL else fget
        self.fset = self._default_fset if fset is _SENTINEL else fset

        # The following properties may be updated in __set_name__
        self.name = ''
        self.vtkname = vtkname
        self._cls: Type[_vtk.vtkAlgorithm] = _vtk.vtkAlgorithm

    def _default_fget(self, instance: _T_Vtk) -> _T_Get:
        return getattr(instance, f'Get{self.vtkname}')()

    def _default_fset(self, instance: _T_Vtk, val: _T_Set) -> None:
        return getattr(instance, f'Set{self.vtkname}')(val)

    def __set_name__(self, cls: Type[_T_Vtk], name: str):
        self.name = self.name or name
        self.vtkname = self.vtkname or _python_to_vtk_name(self.name)
        self._cls = cls

    def __get__(self, instance: _vtk.vtkAlgorithm, cls: Type[_vtk.vtkAlgorithm]) -> _T_Get:
        if self.fget is None:
            raise TypeError(f"Property {self.name} in class {self._cls.__name__} has no getter")
        return self.fget(instance)

    def __set__(self, instance: _vtk.vtkAlgorithm, val: _T_Set):
        if self.fset is None:
            raise TypeError(f"Property {self.name} in class {self._cls.__name__} has no setter")

        self.fset(instance, val)

    def getter(self: _T, fget: _Getter) -> _T:
        self.fget = fget
        return self

    def setter(self: _T, fset: _Setter) -> _T:
        self.fset = fset
        return self


class SimpleIVar(IVar[_T, _T], Generic[_T]):
    """IVar whose get and set types are identical."""
    pass


class BoolIVar(SimpleIVar[bool]):
    def _default_fget(self, instance: _T_Vtk) -> bool:
        return bool(super()._default_fget(instance))  # cast from int to bool


class FloatIVar(IVar[Number, float]):
    pass


class EnumIVar(IVar[str, str]):
    def __init__(self, members: Dict[str, int], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._str_to_int = members
        self._int_to_str = {i: mode for mode, i in members.items()}
        self.__doc__ += '\n' + self._allowable_values()

    def _allowable_values(self):
        names = ', '.join(f"'{name}'" for name in self._str_to_int.keys())
        return f"Allowable values are {names}."

    def _default_fget(self, instance: _T_Vtk) -> _Getter:
        val = super()._default_fget(instance)
        return self._int_to_str[val]

    def _default_fset(self, instance: _T_Vtk, name: str) -> None:
        try:
            val = self._str_to_int[name]
        except KeyError:
            raise ValueError(
                f"Unrecognized mode '{name}' for property {self.name} in class {self._cls.__name__}. "
                + self._allowable_values()
            )

        super()._default_fset(instance, val)


class Glyph3d(_vtk.vtkGlyph3D):
    scaling: BoolIVar = BoolIVar('Turn on/off scaling of source geometry.')
    scale_factor: FloatIVar = FloatIVar('Constant scaling factor.')
    scale_mode: EnumIVar = EnumIVar(
        dict(scalar=0, vector=1, vector_components=2, off=3),
        'How to control scaling of the glyph geometry.'
    )
    range_: IVar[Vector, Tuple[float, float]] = IVar(
        'Range to map scalar values into if a table of glyphs is supplied.',
        vtkname='Range',
    )


def main():
    pass


if __name__ == '__main__':
    main()





