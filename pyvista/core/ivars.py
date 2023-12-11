from __future__ import annotations

from pyvista.core import _vtk_core as _vtk

from typing import TypeVar, Type, Optional, Generic, Callable, cast, TYPE_CHECKING, Dict, Tuple, Union

from pyvista.core._typing_core import Number, Vector

T_Alg = TypeVar('T_Alg')


def snake_to_camel_case(name: str) -> str:
    return ''.join(word.title() for word in name.split('_'))


def python_to_vtk_name(name: str) -> str:
    if name.startswith('n_'):
        return 'NumberOf' + snake_to_camel_case(name[2:])
    else:
        return snake_to_camel_case(name)


T_Set = TypeVar('T_Set')
T_Get = TypeVar('T_Get')
Getter = Callable[[T_Alg], T_Get]
Setter = Callable[[T_Alg, T_Set], None]


class _SENTINEL:
    pass


class IVar(Generic[T_Get, T_Set]):
    def __init__(
            self,
            doc: str = '',
            vtkname: Optional[str] = None,
            getter: Optional[Union[Getter, Type[_SENTINEL]]] = _SENTINEL,
            setter: Optional[Union[Setter, Type[_SENTINEL]]] = _SENTINEL,
    ):
        self.__doc__ = doc

        # The following properties may be updated in __set_name__
        self._name = ''
        self._vtkname = vtkname
        self._getter = getter
        self._setter: Optional[Setter] = setter
        self._cls: Optional[Type[T_Alg]] = None

    def _default_getter(self, cls: Type[T_Alg]) -> Getter:
        return getattr(cls, f'Get{self._vtkname}')

    def _default_setter(self, cls: Type[T_Alg]) -> Setter:
        return getattr(cls, f'Set{self._vtkname}')

    def __set_name__(self, cls: Type[T_Alg], name: str):
        self._name = self._name or name
        self._vtkname = self._vtkname or python_to_vtk_name(self._name)
        self._cls = cls

        if self._getter is _SENTINEL:
            self._getter = self._default_getter(cls)

        if self._setter is _SENTINEL:
            self._setter = self._default_setter(cls)

    def __get__(self, instance: T_Alg, cls: Type[T_Alg]) -> T_Get:
        if self._getter is None:
            raise TypeError(f"Property {self._name} in class {self._cls.__name__} has no getter")
        getter = cast(Getter, self._getter)
        return getter(instance)

    def __set__(self, instance: T_Alg, val: T_Set):
        if self._setter is None:
            raise TypeError(f"Property {self._name} in class {self._cls.__name__} has no setter")

        setter = cast(Setter, self._setter)
        setter(instance, val)


class BoolIVar(IVar[bool, bool]):
    def _default_getter(self, cls: Type[T_Alg]) -> Getter:
        getter = super()._default_getter(cls)
        return lambda instance: bool(getter(instance))  # cast from int to bool


class FloatIVar(IVar[Number, float]):
    pass


class EnumIVar(IVar[str, str]):
    def __init__(self, members: Dict[str, int], doc: str, *args, **kwargs):
        doc += f"\nAllowable values are {', '.join(name for name in members.keys())}."
        super().__init__(*args, **kwargs)
        self._str_to_int = members
        self._int_to_str = {i: mode for mode, i in members.items()}

    def _default_getter(self, cls: Type[T_Alg]) -> Getter:
        int_getter = super()._default_getter(cls)

        def getter(instance: T_Alg) -> str:
            return self._int_to_str[int_getter(instance)]

        return getter

    def _default_setter(self, cls: Type[T_Alg]) -> Setter:
        int_setter = super()._default_setter(cls)

        def setter(instance: T_Alg, mode: str) -> None:
            int_setter(instance, self._str_to_int[mode])

        return setter


if __name__ == '__main__':
    class Glyph3D(_vtk.vtkGlyph3D):
        scaling: BoolIVar = BoolIVar('Turn on/off scaling of source geometry.')
        scale_factor: FloatIVar = FloatIVar('Constant scaling factor.')
        scale_mode: EnumIVar = EnumIVar(
            dict(scalar=0, vector=1, vector_components=2, off=3),
            'How to control scaling of the glyph geometry.'
        )

    alg = Glyph3D()
    alg.scaling = True
    assert alg.scaling is True
    alg.scale_mode = 'vector'
    assert alg.scale_mode == 'vector' and alg.GetScaleMode() == 1


    class Connectivity(_vtk.vtkConnectivityFilter):
        scalar_range: IVar[Vector[float], Tuple[float, float]] = IVar(
            'The scalar range to use to extract cells based on scalar connectivity.')

        extraction_mode: EnumIVar = EnumIVar(
            dict(point_seeded=1, cell_seeded=2, specifed_regions=3,
                 largest_region=4, all_regions=5, closest_point_region=6),
            'Control the extraction of connected surfaces.',
        )

        closest_point: IVar[Vector[float], Tuple[float, float, float]] = IVar(
            'The x-y-z point coordinates when extracting the region closest to a specified point.'
        )

        n_extracted_regions: IVar[int, int] = IVar('The number of connected regions', setter=None)

    alg = Connectivity()
    alg.scalar_range = (1.0, 3.0)
    assert alg.GetScalarRange() == alg.scalar_range == (1.0, 3.0)
    assert alg.n_extracted_regions == 0
