from typing import Tuple, Optional

import numpy as np
import pytest
from vtkmodules.vtkCommonDataModel import vtkIncrementalPointLocator, vtkMergePoints

from pyvista.core import _vtk_core as _vtk
from pyvista.core._typing_core import Vector, Number
from pyvista.core.ivars import BoolIVar, FloatIVar, EnumIVar, IVar


class Glyph3d(_vtk.vtkGlyph3D):
    scaling: BoolIVar = BoolIVar('Turn on/off scaling of source geometry.')
    scale_factor: FloatIVar = FloatIVar('Constant scaling factor.')
    scale_mode: EnumIVar = EnumIVar.from_dict(
        dict(scalar=0, vector=1, vector_components=2, off=3),
        'How to control scaling of the glyph geometry.'
    )
    range_: IVar[Vector, Tuple[float, float]] = IVar(
        'Range to map scalar values into if a table of glyphs is supplied.',
        vtkname='Range',
    )


from sphinx.util.inspect import signature
sig = signature(Glyph3d.range_.fget)
print(sig.return_annotation)  # ~_T_Get