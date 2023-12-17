from typing import Tuple, Optional

import numpy as np
import pytest
from vtkmodules.vtkCommonDataModel import vtkIncrementalPointLocator, vtkMergePoints

from pyvista.core import _vtk_core as _vtk
from pyvista.core._typing_core import Vector, Number
from pyvista.core.ivars import BoolIVar, FloatIVar, EnumIVar, IVar, SimpleIVar


class Glyph3d(_vtk.vtkGlyph3D):
    scaling: BoolIVar = BoolIVar('Turn on/off scaling of source geometry.')
    scale_factor: FloatIVar = FloatIVar('Constant scaling factor.')
    scale_mode: EnumIVar = EnumIVar.from_dict(
        dict(scalar=0, vector=1, vector_components=2, off=3),
        'How to control scaling of the glyph geometry.'
    )
    range_: IVar[Tuple[float, float], Vector] = IVar(
        'Range to map scalar values into if a table of glyphs is supplied.',
        vtkname='Range',
    )


@pytest.fixture
def glyph():
    return Glyph3d()


@pytest.mark.parametrize('val', [True, False])
def test_bool_ivar(glyph, val):
    glyph.scaling = val
    assert glyph.scaling is val is bool(glyph.GetScaling())


@pytest.mark.parametrize('val', [1.0, 2.0, 1, 2, np.array(1), np.array(2), np.array(1.0), np.array(2.0)])
def test_float_ivar(glyph, val):
    glyph.scale_factor = val
    assert glyph.scale_factor == val == glyph.GetScaleFactor()


@pytest.mark.parametrize(('name', 'val'), [('scalar', 0), ('vector', 1), ('vector_components', 2), ('off', 3)])
def test_enum_ivar(glyph, name, val):
    glyph.scale_mode = name
    assert glyph.scale_mode == name
    assert glyph.GetScaleMode() == val


def test_enum_ivar_illegal_value(glyph):
    with pytest.raises(ValueError, match="Unrecognized mode 'unknown' for property scale_mode in class Glyph3d"):
        glyph.scale_mode = 'unknown'


def test_custom_vtkname(glyph):
    glyph.range_ = (3.0, 4.0)
    assert glyph.range_ == glyph.GetRange()


def test_glyph_type_reflection():
    assert Glyph3d.scaling.types() == (bool, bool)
    assert Glyph3d.scale_factor.types() == (float, Number)
    assert Glyph3d.scale_mode.types() == (str, str)
    assert Glyph3d.range_.types() == (Tuple[float, float], Vector)


class Connectivity(_vtk.vtkConnectivityFilter):
    scalar_range: IVar[Tuple[float, float], Vector] = IVar(
        'The scalar range to use to extract cells based on scalar connectivity.')

    n_extracted_regions: SimpleIVar[int] = SimpleIVar('The number of connected regions', fset=None)

    seed_list: IVar[Tuple[int, ...], Vector] = IVar(
        'List of point ids/cell ids used to seed regions.', fget=None)

    @seed_list.setter
    def seed_list(self, seed_list: Vector):
        self.InitializeSeedList()
        for seed in seed_list:
            self.AddSeed(seed)


@pytest.fixture
def connectivity():
    return Connectivity()


@pytest.mark.parametrize('val', [(1, 2), (3.0, 4.0), np.array([5, 6])])
def test_tuple_ivar(connectivity, val):
    connectivity.scalar_range = val
    assert connectivity.scalar_range == connectivity.GetScalarRange() == tuple(val)


@pytest.mark.parametrize('val', [(), (1,), (3, 4, 5)])
def test_tuple_ivar_wrong_length(connectivity, val):
    with pytest.raises(TypeError):
        connectivity.scalar_range = val


def test_ivar_custom_setter(connectivity):
    connectivity.seed_list = [1, 2, 3]


def test_ivar_no_getter(connectivity):
    with pytest.raises(TypeError):
        _ = connectivity.seed_list


def test_ivar_no_setter(connectivity):
    assert connectivity.n_extracted_regions == 0
    with pytest.raises(TypeError):
        connectivity.n_extracted_regions = 8


def test_connectivity_type_reflection():
    assert Connectivity.scalar_range.types() == (Tuple[float, float], Vector)
    assert Connectivity.n_extracted_regions.types() == (int, int)
    assert Connectivity.seed_list.types() == (Tuple[int, ...], Vector)


class BoxClip(_vtk.vtkBoxClipDataSet):
    locator: IVar[vtkIncrementalPointLocator, Optional[vtkIncrementalPointLocator]] = IVar(
        'Specify a spatial locator for merging points.'
    )


@pytest.fixture()
def box_clip():
    return BoxClip()


def test_point_locator_ivar(box_clip):
    assert box_clip.locator is None
    box_clip.CreateDefaultLocator()
    assert isinstance(box_clip.locator, vtkMergePoints)
    box_clip.locator = _vtk.vtkNonMergingPointLocator()
    assert isinstance(box_clip.locator, _vtk.vtkNonMergingPointLocator)


def test_box_clip_type_reflection():
    assert BoxClip.locator.types() == (vtkIncrementalPointLocator, Optional[vtkIncrementalPointLocator])

