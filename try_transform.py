import inspect

from pyvista.core import _vtk_core as _vtk
from typing import Iterator, Type, Tuple, TypeVar

from typing_extensions import dataclass_transform

from pyvista.core._typing_core import Vector
from pyvista.core.ivars import IVar, BoolIVar, FloatIVar, EnumIVar


@dataclass_transform(field_specifiers=(IVar,))
class VtkWrapper:
    @classmethod
    def _iter_ivars(cls) -> Iterator[IVar]:
        for _name, ivar in inspect.getmembers(cls, lambda x: hasattr(x, '_is_ivar')):
            yield ivar

    def __init_subclass__(cls, **kwargs):
        pass


class Glyph3d(_vtk.vtkGlyph3D, VtkWrapper):
    scaling: BoolIVar = BoolIVar()
    """Turn on/off scaling of source geometry.xxx"""

    scale_factor: FloatIVar = FloatIVar('Constant scaling factor.')
    scale_mode: EnumIVar = EnumIVar.from_dict(
        dict(scalar=0, vector=1, vector_components=2, off=3),
        'How to control scaling of the glyph geometry.'
    )
    range_: IVar[Tuple[float, float], Vector] = IVar(
        'Range to map scalar values into if a table of glyphs is supplied.',
        vtkname='Range',
    )


if __name__ == '__main__':
    g = Glyph3d(scaling=True)


