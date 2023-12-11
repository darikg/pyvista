from __future__ import annotations

from typing import TypeVar, Type, Optional, Generic, Callable, cast, Dict, Union

from pyvista.core import _vtk_core as _vtk
from pyvista.core._typing_core import Number


def _snake_to_camel_case(name: str) -> str:
    return ''.join(word.title() for word in name.split('_'))


def _python_to_vtk_name(name: str) -> str:
    if name.startswith('n_'):
        return 'NumberOf' + _snake_to_camel_case(name[2:])
    else:
        return _snake_to_camel_case(name)


_T = TypeVar('_T')
_T_Vtk = TypeVar('_T_Vtk')
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

    getter: Callable[[VTK_OBJECT], GET_TYPE], optional
        A function that gets the IVar's value. If not supplied, defaults to `Get{vtkname}`.
        Supply getter=None to specify that no getter should be provided.

    setter: Callable[[VTK_OBJECT, SET_TYPE], None]], optional
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

    See Also
    --------
    BoolIVar, FloatIVar, EnumIvar, and SimpleIVar.

    """
    def __init__(
            self,
            doc: str = '',
            vtkname: Optional[str] = None,
            getter: Optional[Union[_Getter, Type[_SENTINEL]]] = _SENTINEL,
            setter: Optional[Union[_Setter, Type[_SENTINEL]]] = _SENTINEL,
    ):
        self.__doc__ = doc

        # The following properties may be updated in __set_name__
        self._name = ''
        self._vtkname = vtkname
        self._getter = getter
        self._setter = setter
        self._cls: Type[_vtk.vtkAlgorithm] = _vtk.vtkAlgorithm

    def _default_getter(self, cls: Type[_vtk.vtkAlgorithm]) -> _Getter:
        return getattr(cls, f'Get{self._vtkname}')

    def _default_setter(self, cls: Type[_vtk.vtkAlgorithm]) -> _Setter:
        return getattr(cls, f'Set{self._vtkname}')

    def __set_name__(self, cls: Type[_vtk.vtkAlgorithm], name: str):
        self._name = self._name or name
        self._vtkname = self._vtkname or _python_to_vtk_name(self._name)
        self._cls = cls

        if self._getter is _SENTINEL:
            self._getter = self._default_getter(cls)

        if self._setter is _SENTINEL:
            self._setter = self._default_setter(cls)

    def __get__(self, instance: _vtk.vtkAlgorithm, cls: Type[_vtk.vtkAlgorithm]) -> _T_Get:
        if self._getter is None:
            raise TypeError(f"Property {self._name} in class {self._cls.__name__} has no getter")
        getter = cast(_Getter, self._getter)
        return getter(instance)

    def __set__(self, instance: _vtk.vtkAlgorithm, val: _T_Set):
        if self._setter is None:
            raise TypeError(f"Property {self._name} in class {self._cls.__name__} has no setter")

        setter = cast(_Setter, self._setter)
        setter(instance, val)


class SimpleIVar(IVar[_T, _T], Generic[_T]):
    """IVar whose get and set types are identical."""
    pass


class BoolIVar(SimpleIVar[bool]):
    def _default_getter(self, cls: Type[_vtk.vtkAlgorithm]) -> _Getter:
        getter = super()._default_getter(cls)
        return lambda instance: bool(getter(instance))  # cast from int to bool


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

    def _default_getter(self, cls: Type[_vtk.vtkAlgorithm]) -> _Getter:
        int_getter = super()._default_getter(cls)

        def getter(instance: _vtk.vtkAlgorithm) -> str:
            return self._int_to_str[int_getter(instance)]

        return getter

    def _default_setter(self, cls: Type[_vtk.vtkAlgorithm]) -> _Setter:
        int_setter = super()._default_setter(cls)

        def setter(instance: _vtk.vtkAlgorithm, mode: str) -> None:
            try:
                val = self._str_to_int[mode]
            except KeyError:
                raise ValueError(
                    f"Unrecognized mode '{mode}' for property {self._name} in class {self._cls.__name__}. "
                    + self._allowable_values()
                )

            int_setter(instance, val)

        return setter


def main():
    from vtkmodules.vtkRenderingCore import vtkDistanceToCamera

    class DistanceToCamera2(vtkDistanceToCamera):
        @property
        def screen_size(self) -> float:
            return self.GetScreenSize()

        @screen_size.setter
        def screen_size(self, val: float):
            self.SetScreenSize(val)

        scaling: IVar[bool, bool] = IVar('Whether to scale the distance by the input array to process.')

    dtc = DistanceToCamera1()
    dtc.scaling = True  # Equivalent to dtc.SetScaling(True)


if __name__ == '__main__':
    main()





