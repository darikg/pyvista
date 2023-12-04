import collections.abc
from enum import IntEnum
from typing import Optional, Union, Dict, Tuple

import numpy as np
from vtkmodules.vtkRenderingCore import vtkDistanceToCamera

import pyvista.core._vtk_core as _vtk
from pyvista import AnnotatedIntEnum
from pyvista.core.filters.alg import _Input, IVar, FilterWrapper, FilterBase, InitArg
from pyvista.core.utilities.arrays import (
    FieldAssociation,
)

# _Glyph = Union[_Input, Dict[int, _Input]]
_Glyph = _Input

# Glyph Advantages
# -- Allow algorithm inputs as well as datasets
# -- Set input variable names without setting active fields on the source dataset
# _IntoMode = Union[int, str, _T_Enum]
# Dispatch glyph and input array names uniformly


class Glyph3D(_vtk.vtkGlyph3D, FilterBase):
    """Copy oriented and scaled glyph geometry to every input point.

    Glyph3D is a filter that copies a geometric representation (called a glyph) to every point in the input dataset.
    The glyph is defined with polygonal data from a source filter input. The glyph may be oriented along the input
    vectors or normals, and it may be scaled according to scalar data or vector magnitude. More than one glyph may be
    used by creating a table of source objects, each defining a different glyph. If a table of glyphs is defined,
    then the table can be indexed into by using either scalar value or vector magnitude.

    To use this object you'll have to provide an input dataset and a source to define the glyph. Then decide whether
    you want to scale the glyph and how to scale the glyph (using scalar value or vector magnitude). Next decide
    whether you want to orient the glyph, and whether to use the vector data or normal data to orient it. Finally,
    decide whether to use a table of glyphs, or just a single glyph. If you use a table of glyphs, you'll have to
    decide whether to index into it with scalar value or with vector magnitude.

    """
    _wrapper = FilterWrapper(
        superclass=_vtk.vtkGlyph3D,
        input_data_desc='The input mesh to which the glyph geometry is copied to each point.',
        ivars=[
            ('scaling', bool, 'Turn on/off scaling of source geometry.'),
            ('scale_factor', float, 'Constant scaling factor.'),
            ('scale_mode', ('scalar', 'vector', 'vector_components', 'off'),
             'How to control scaling of the glyph geometry.'),
            IVar('range_', Tuple[float, float], vtkname='Range',
                 desc='Range to map scalar values into if a table of glyphs is supplied.'),
            ('clamping', bool, 'Range to map scalar values into if a table of glyphs is supplied.'),
            ('index_mode', ('off', 'scalar', 'vector'), [
                "Index into table of sources by scalar, by vector/normal magnitude, or no indexing.",
                "If indexing is turned off, then the first source glyph in the table of glyphs is used."]),
            ('orient', bool, 'Turn on/off orienting of input geometry along vector/normal.'),
            ('vector_mode', ('vector', 'normal', 'rotation_off', 'follow_camera_directrion'),
             'Specify how to use vectors.'),
            ('color_mode', ('scale', 'scalar', 'vector'),
             'Either color by scale, scalar or by vector/normal magnitude.'),
        ]
    )

    def __post_init__(
            self,
            glyph: Optional[_Glyph] = None,
            scalars_name: Optional[str] = None,
            vectors_name: Optional[str] = None,
            normals_name: Optional[str] = None,
            color_scalars_name: Optional[str] = None,
    ):
        """
        Parameters
        ----------
        glyph : DataSource, Sequence[DataSource], Dict[int, DataSource], optional
            The glyph geometry to be copied to each point of the input datasource.

        scalars_name, vectors_name, normals_name, color_scalars_name : str, optional
            The name of the point data arrays in the input data source to use for the corresponding operations.
        """
        if glyph is not None:
            self.set_glyph(glyph)

        for (i, name) in enumerate((scalars_name, vectors_name, normals_name, color_scalars_name)):
            if name is not None:
                self.set_input_array_to_process(i, name)

    def set_input_array_to_process(self, typ: str, name: str) -> None:
        """Set the name of a point data array in the input datasource to process.

        Parameters
        ----------
        typ : str
            The type of input array to specify.
            Allowable values are 'scalars', 'vectors', 'normals', or 'color_scalars'.

        name : str
            The name of the array.
        """
        if isinstance(typ, int):
            val = typ
        else:
            val = _InputArrayType.from_any(typ).value
        self.SetInputArrayToProcess(val, 0, 0, FieldAssociation.POINT.value, name)

    def set_glyph(self, geom: _Glyph) -> None:
        """Set the glyph data that is copied to every point in `input_data`.

        A table of glyph geometries can be supplied as a dict mapping values to glyph geometries,
        or a sequence of geometries where the indices are assumed to be range(len(geom)).

        Parameters
        ----------
        geom: DataSource | sequence[DataSource] | dict[int, DataSource]

        """
        if isinstance(geom, (np.ndarray, collections.abc.Sequence)):
            geom = dict(enumerate(geom))

        if isinstance(geom, collections.abc.Mapping):
            for index, glyph in geom.items():
                if isinstance(glyph, _vtk.vtkDataSet):
                    self.SetSourceData(index, glyph)
                else:
                    self.SetSourceConnection(index, glyph)
        else:
            if isinstance(geom, _vtk.vtkDataSet):
                self.SetSourceData(geom)
            else:
                self.SetSourceConnection(geom)


def _main():
    import pyvista as pv
    import numpy as np
    sphere = pv.Sphere(radius=3.14)
    sphere["direction"] = 0.3 * np.vstack((
        np.sin(sphere.points[:, 0]),
        np.cos(sphere.points[:, 1]),
        np.cos(sphere.points[:, 2]),
    )).T

    distanceToCamera = vtkDistanceToCamera()
    distanceToCamera.SetInputData(sphere)
    distanceToCamera.SetScreenSize(100.0)

    glyph = Glyph3D(
        input_data=distanceToCamera.GetOutputPort(),
        glyph=pv.Arrow(),
        scaling=True,
        scale_mode='scalar',
        scale_factor=0.5,
        orient=True,
        vector_mode='vector',
        vectors_name='direction',
        color_mode='vector',
        scalars_name='DistanceToCamera',
        color_scalars_name='direction',
    )

    assert glyph.scaling
    assert glyph.scale_mode == 'scalar'
    assert glyph.scale_factor == 0.5
    assert glyph.orient
    assert glyph.vector_mode == 'vector'
    assert glyph.color_mode == 'vector'

    pl = pv.Plotter()
    distanceToCamera.SetRenderer(pl.renderer)
    distanceToCamera.Update()
    # pl.add_mesh(sphere, color='grey', opacity=.3)
    pl.add_mesh(glyph)

    pl.show()


if __name__ == '__main__':
    _main()
