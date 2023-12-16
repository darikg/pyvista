from __future__ import annotations

import typing
from typing import TypeVar, Type, Optional, Generic, Callable, Dict, Any, Tuple

from typing_extensions import Self, get_args

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
_T_Get_Set = Tuple[Type[_T_Get], Type[_T_Set]]
_Getter = Callable[[_T_Vtk], _T_Get]
_Setter = Callable[[_T_Vtk, _T_Set], None]


def _sentinel_get(instance: _T_Vtk) -> Any: ...


def _sentinel_set(instance: _T_Vtk, val: Any): ...


_sentinel_get.__repr__ = lambda _: '<DEFAULT_GETTER>'
_sentinel_set.__repr__ = lambda _: '<DEFAULT_SETTER>'


class AFoo:
    """A foo."""

    def __init__(self):
        self.x: int = 8

    @property
    def y(self) -> int:
        return 3


class IVar(Generic[_T_Get, _T_Set]):
    """IVar(doc: str = '', vtkname: Optional[str] = None, fget: Callable[[VTK_TYPE], GET_TYPE] = DEFAULT_GETTER,
    fset: Callable[[INSTANCE, SET_TYPE], None] = DEFAULT_SETTER)

    Property descriptor for python subclasses of VTK classes.

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
        >>> class DistanceToCamera(vtkDistanceToCamera):
        >>>     screen_size: IVar[float, float] = IVar(
        >>>         'The desired screen size obtained by scaling glyphs by the distance array.'
        >>>     )
        >>>
        >>> dtc = DistanceToCamera()
        >>> dtc.screen_size = 100  # Equivalent to dtc.SetScreenSize(100)
        >>> dtc.screen_size
        100
        >>>
        >>> # This is equivalent to the more verbose @property based approach:
        >>> class _DistanceToCamera(vtkDistanceToCamera):
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
            fget: Optional[_Getter] = _sentinel_get,
            fset: Optional[_Setter] = _sentinel_set,
            _name: str = '',
            _cls: type = object,
    ):

        self.__doc__ = doc
        self.fget: Optional[_Getter] = self._default_fget if fget is _sentinel_get else fget
        self.fset: Optional[_Setter] = self._default_fset if fset is _sentinel_set else fset

        # The following properties may be updated in __set_name__
        self.vtkname = vtkname
        self.name = _name
        self.cls = _cls

    def _default_fget(self, instance: _T_Vtk) -> _T_Get:
        return getattr(instance, f'Get{self.vtkname}')()

    def _default_fset(self, instance: _T_Vtk, val: _T_Set) -> None:
        getattr(instance, f'Set{self.vtkname}')(val)

    def __set_name__(self, cls: Type[_T_Vtk], name: str):
        self.name = self.name or name
        self.vtkname = self.vtkname or _python_to_vtk_name(self.name)
        self.cls = cls

    def __get__(self, instance: Optional[_T_Vtk], cls: Type[_T_Vtk]) -> _T_Get:
        if instance is None:  # Class-level __get__
            return self

        if self.fget is None:
            raise TypeError(f"Property {self.name} in class {self.cls.__name__} has no getter")
        return self.fget(instance)

    def __set__(self, instance: _vtk.vtkAlgorithm, val: _T_Set):
        if self.fset is None:
            raise TypeError(f"Property {self.name} in class {self.cls.__name__} has no setter")

        self.fset(instance, val)

    def replace(self, fget: Optional[_Getter], fset: Optional[_Setter], **kwargs) -> Self:
        """Return a copy of self with fget or fset replaced."""
        return type(self)(
            doc=self.__doc__, vtkname=self.vtkname, fget=fget, fset=fset, _name=self.name, _cls=self.cls, **kwargs)

    def getter(self, fget: Optional[_Getter]) -> Self:
        """Function decorator to replace fget."""
        return self.replace(fget=fget, fset=self.fset)

    def setter(self, fset: Optional[_Setter]) -> Self:
        """Function decorator to replace fset."""
        return self.replace(fget=self.fget, fset=fset)

    def _types(self) -> Optional[_T_Get_Set]:
        """Return a tuple of (GET_TYPE, SET_TYPE).

        Only used for building documentation. Return None if unknown.
        """
        return None


class SimpleIVar(IVar[_T, _T], Generic[_T]):
    """IVar whose get and set types are identical."""
    pass


class BoolIVar(SimpleIVar[bool]):
    """IVar representing a bool."""
    def _default_fget(self, instance: _T_Vtk) -> bool:
        return bool(super()._default_fget(instance))  # cast from int to bool

    def _types(self) -> Optional[_T_Get_Set]:
        return bool, bool


class FloatIVar(IVar[Number, float]):
    """IVar representing a float."""
    def _types(self) -> Optional[_T_Get_Set]:
        return Number, float


class EnumIVar(IVar[str, str]):
    """IVar representing an enumeration."""
    def __init__(
            self,
            *args,
            str_to_int: Dict[str, int],
            int_to_str: Dict[int, str],
            **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._str_to_int = str_to_int
        self._int_to_str = int_to_str

    def _allowable_values(self):
        names = ', '.join(f"'{name}'" for name in self._str_to_int.keys())
        return f"Allowable values are {names}."

    def _default_fget(self, instance: _T_Vtk) -> str:
        val: int = getattr(instance, f'Get{self.vtkname}')()
        return self._int_to_str[val]

    def _default_fset(self, instance: _T_Vtk, name: str) -> None:
        try:
            val: int = self._str_to_int[name]
        except KeyError:
            raise ValueError(
                f"Unrecognized mode '{name}' for property {self.name} in class {self.cls.__name__}. "
                + self._allowable_values()
            )
        getattr(instance, f'Set{self.vtkname}')(val)

    @staticmethod
    def from_dict(members: Dict[str, int], *args, **kwargs) -> EnumIVar:
        out = EnumIVar(
            *args,
            str_to_int=members,
            int_to_str={i: mode for mode, i in members.items()},
            **kwargs,
        )
        out.__doc__ += '\n' + out._allowable_values()
        return out

    def replace(self, fget: Optional[_Getter], fset: Optional[_Setter], **kwargs) -> Self:
        """Return a copy of self with fget or fset replaced."""
        return super().replace(fget=fget, fset=fset, str_to_int=self._str_to_int, int_to_str=self._int_to_str, **kwargs)

    def _types(self) -> Optional[_T_Get_Set]:
        return str, str


class Glyph3d(_vtk.vtkGlyph3D):
    scaling: BoolIVar = BoolIVar()
    """Turn on/off scaling of source geometry.xxx"""
    
    scale_factor: FloatIVar = FloatIVar('Constant scaling factor.')
    scale_mode: EnumIVar = EnumIVar.from_dict(
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





