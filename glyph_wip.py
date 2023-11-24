import collections.abc
import warnings
from typing import Optional, Union, Dict, Tuple, TypeVar

from vtkmodules.vtkRenderingCore import vtkDistanceToCamera

import pyvista
import numpy as np
import pyvista.core._vtk_core as _vtk
from pyvista import AnnotatedIntEnum
from pyvista.core.errors import (
    AmbiguousDataError,
    MissingDataError,
)
from pyvista.core.utilities.arrays import (
    FieldAssociation,
    set_default_active_scalars,
)

_ClampRange = Tuple[float, float]
_Input = Union[_vtk.vtkDataSet, _vtk.vtkAlgorithmOutput]
_Glyph = Union[_Input, Dict[int, _Input]]

# Advantages
# -- Allow algorithm inputs as well as datasets
# -- Set input variable names without setting active fields on the source dataset


class ScaleMode(AnnotatedIntEnum):
    SCALAR = (0, 'scalar')
    VECTOR = (1, 'vector')
    VECTOR_COMPONENTS = (2, 'vector_components')
    OFF = (3, 'off')


class ColorMode(AnnotatedIntEnum):
    SCALE = (0, 'scale')
    SCALAR = (1, 'scalar')
    VECTOR = (2, 'vector')


class VectorMode(AnnotatedIntEnum):
    VECTOR = (0, 'vector')
    NORMAL = (1, 'normal')
    ROTATION_OFF = (2, 'rotation_off')
    FOLLOW_CAMERA_DIRECTION = (3, 'follow_camera_direction')


class IndexMode(AnnotatedIntEnum):
    OFF = (0, 'off')
    SCALAR = (1, 'scalar')
    VECTOR = (2, 'vector')


class InputArrayType(AnnotatedIntEnum):
    # From the vtkGlyph3d docs: You can set what arrays to use for the
    # scalars, vectors, normals, and color scalars by using the
    # SetInputArrayToProcess methods in vtkAlgorithm. The first array is
    # scalars, the next vectors, the next normals and finally color scalars.
    SCALARS = (0, 'scalars')
    VECTORS = (1, 'vectors')
    NORMALS = (2, 'normals')
    COLOR_SCALARS = (3, 'color_scalars')


_T = TypeVar('_T', bound=AnnotatedIntEnum)
_IntoMode = Union[int, str, _T]


DataSource = Union[_vtk.vtkDataSet, _vtk.vtkAlgorithmOutput]


class Glyph3D(_vtk.vtkGlyph3D):
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

    Parameters
    ----------
    input_data : DataSource
        The input data whose points the glyph geometry is copied to.

    glyph : DataSource | sequence[DataSource] | dict[int, DataSource], optional
        The glyph data that is copied to every point in `input_data`. A table
        of glyph geometries can be supplied as a dict mapping values to glyph geometries.

    scaling : bool, optional
        Turn on/off scaling of source geometry.

    scale_factor : float, optional
        Constant scaling factor.

    scale_mode : ScaleMode | str | int, optional
        How to control scaling of the glyph geometry.
        Allowable values are 'scalar', 'vector', 'vector_components', or 'off'.

    range_: Tuple[float, float], optional
        Range to map scalar values into if a table of glyphs is supplied.

    clamping : bool, optional
        Turn on/off clamping of "scalar" values to `range`.

    index_mode: IndexMode | str | int, optional
        Index into table of sources by scalar, by vector/normal magnitude, or no indexing.
        Allowable values are 'off', 'scalar', or 'vector'. If indexing is turned off, then
        the first source glyph in the table of glyphs is used.

    orient : bool, optional
        Turn on/off orienting of input geometry along vector/normal.

    vector_mode : VectorMode | str |int, optional
        Specify how to use vectors.
        Allowable values are 'vector', 'normal', 'rotation_off', 'follow_camera_direction'.

    color_mode : ColorMode | str | int, optional
        Either color by scale, scalar or by vector/normal magnitude.
        Allowable values are 'scale', 'scalar', 'vector'.

    scalars_name, vectors_name, normals_name, color_scalars_name : str | optional
        The name of the point data arrays in the input data source to use for the
        corresponding operations.
    """

    def __init__(
            self,
            input_data: _Input,
            glyph: Optional[_Glyph],
            scaling: Optional[bool] = None,
            scale_mode: Optional[_IntoMode[ScaleMode]] = None,
            scale_factor: Optional[float] = None,
            clamping: Optional[bool] = None,
            range_: Optional[_ClampRange] = None,
            orient: Optional[bool] = None,
            vector_mode: Optional[_IntoMode[VectorMode]] = None,
            color_mode: Optional[_IntoMode[ColorMode]] = None,
            index_mode: Optional[_IntoMode[IndexMode]] = None,
            scalars_name: Optional[str] = None,
            vectors_name: Optional[str] = None,
            normals_name: Optional[str] = None,
            color_scalars_name: Optional[str] = None,
    ):
        super().__init__()

        if isinstance(input_data, _vtk.vtkDataSet):
            self.SetInputData(input_data)
        else:
            self.SetInputConnection(input_data)

        if glyph is not None:
            self.set_glyph(glyph)

        if scaling is not None:
            self.scaling = scaling

        if scale_factor is not None:
            self.scale_factor = scale_factor

        if scale_mode is not None:
            self.scale_mode = scale_mode

        if color_mode is not None:
            self.color_mode = color_mode

        if orient is not None:
            self.orient = orient

        if vector_mode is not None:
            self.vector_mode = vector_mode

        if clamping is not None:
            self.clamping = clamping

        if range_ is not None:
            self.range_ = range_

        if index_mode is not None:
            self.index_mode = index_mode

        for (i, name) in enumerate((scalars_name, vectors_name, normals_name, color_scalars_name)):
            if name is not None:
                self.set_input_array_to_process(i, name)

    def set_input_array_to_process(self, typ: _IntoMode[InputArrayType], name: str) -> None:
        """Set the name of a point data array in the input datasource to process.
        
        Parameters
        ----------
        typ : InputArrayType | str | int
            The type of input array to specify. 
            Allowable values are 'scalars', 'vectors', 'normals', or 'color_scalars'.
            
        name : str
            The name of the array.
        """
        self.SetInputArrayToProcess(InputArrayType.from_any(typ).value, 0, 0, FieldAssociation.POINT.value, name)

    @property
    def scaling(self) -> bool:
        """Turn on/off scaling of source geometry."""
        return bool(self.GetScaling())

    @scaling.setter
    def scaling(self, state: bool):
        """Turn on/off scaling of source geometry."""
        self.SetScaling(state)

    @property
    def scale_factor(self) -> float:
        """Constant scaling factor."""
        return self.GetScaleFactor()

    @scale_factor.setter
    def scale_factor(self, factor: float):
        """Constant scaling factor."""
        self.SetScaleFactor(factor)

    @property
    def clamping(self) -> bool:
        """Turn on/off clamping of "scalar" values to `range`."""
        return bool(self.GetClamping())

    @clamping.setter
    def clamping(self, state: bool):
        """Turn on/off clamping of "scalar" values to `range`."""
        self.SetClamping(state)

    @property
    def range_(self) -> Tuple[float, float]:
        """Range to map scalar values into if a table of glyphs is supplied."""
        return self.GetRange()

    @range_.setter
    def range_(self, rng: Tuple[float, float]):
        """Range to map scalar values into if a table of glyphs is supplied."""
        self.SetRange(*rng)

    @property
    def scale_mode(self) -> ScaleMode:  # numpydoc ignore=RT01
        """How to control scaling of the glyph geometry."""
        return ScaleMode(self.GetScaleMode())

    @scale_mode.setter
    def scale_mode(self, mode: _IntoMode[ScaleMode]):
        """How to control scaling of the glyph geometry."""
        self.SetScaleMode(ScaleMode.from_any(mode).value)

    @property
    def orient(self) -> bool:
        """Turn on/off orienting of input geometry along vector/normal."""
        return bool(self.GetOrient())

    @orient.setter
    def orient(self, state: bool):
        """Turn on/off orienting of input geometry along vector/normal."""
        self.SetOrient(state)

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

    @property
    def index_mode(self) -> IndexMode:  # numpydoc ignore=RT01
        """Index into table of sources by scalar, by vector/normal magnitude, or no indexing."""
        return IndexMode(self.GetIndexMode())

    @index_mode.setter
    def index_mode(self, mode: _IntoMode[IndexMode]):  # numpydoc ignore=RT01
        """Index into table of sources by scalar, by vector/normal magnitude, or no indexing."""
        self.SetIndexMode(IndexMode.from_any(mode).value)

    @property
    def color_mode(self) -> ColorMode:
        """Either color by scale, scalar or by vector/normal magnitude."""
        return ColorMode(self.GetColorMode())

    @color_mode.setter
    def color_mode(self, mode: _IntoMode[ColorMode]):
        """Either color by scale, scalar or by vector/normal magnitude."""
        self.SetColorMode(ColorMode.from_any(mode).value)

    @classmethod
    def for_dataset(
            cls,
            dataset: pyvista.DataSet,
            orient: bool = True,
            scale: Union[str, bool] = True,
            scale_factor: float = 1.0,
            glyph: Optional[_Glyph] = None,
            tolerance: Optional[float] = None,
            absolute: bool = False,
            range_: Optional[_ClampRange] = False,
            progress_bar=False,
            **kwargs,
    ):
        """Construct a Glyph3D algorithm for a source `pyvista.DataSet`."""

        if isinstance(scale, str):
            dataset.set_active_scalars(scale, preference='cell')
            scale = True
        elif isinstance(scale, bool) and scale:
            try:
                set_default_active_scalars(dataset)
            except MissingDataError:
                warnings.warn("No data to use for scale. scale will be set to False.")
                scale = False
            except AmbiguousDataError as err:
                warnings.warn(f"{err}\nIt is unclear which one to use. scale will be set to False.")
                scale = False

        scale_mode = None
        if scale:
            if dataset.active_scalars is not None:
                scale_mode = 'vector' if dataset.active_scalars.ndim > 1 else 'scalar'
        else:
            scale_mode = 'off'

        if isinstance(orient, str):
            if scale and dataset.active_scalars_info.association == FieldAssociation.CELL:
                prefer = 'cell'
            else:
                prefer = 'point'
            dataset.set_active_vectors(orient, preference=prefer)
            orient = True

        if orient:
            try:
                pyvista.set_default_active_vectors(dataset)
            except MissingDataError:
                warnings.warn("No vector-like data to use for orient. orient will be set to False.")
                orient = False
            except AmbiguousDataError as err:
                warnings.warn(
                    f"{err}\nIt is unclear which one to use. orient will be set to False."
                )
                orient = False

        # If a table of geometries was passed
        index_mode = None
        if isinstance(glyph, collections.abc.Mapping):
            if dataset.active_scalars is not None:
                index_mode = 'vector' if dataset.active_scalars.ndim > 1 else 'scalar'
            else:
                index_mode = 'off'

        if isinstance(orient, str):
            if scale and dataset.active_scalars_info.association == FieldAssociation.CELL:
                prefer = 'cell'
            else:
                prefer = 'point'
            dataset.set_active_vectors(orient, preference=prefer)
            orient = True

        if orient:
            try:
                pyvista.set_default_active_vectors(dataset)
            except MissingDataError:
                warnings.warn("No vector-like data to use for orient. orient will be set to False.")
                orient = False
            except AmbiguousDataError as err:
                warnings.warn(
                    f"{err}\nIt is unclear which one to use. orient will be set to False."
                )
                orient = False

        if scale and orient:
            if dataset.active_vectors_info.association != dataset.active_scalars_info.association:
                raise ValueError("Both ``scale`` and ``orient`` must use point data or cell data.")

        source_data = dataset
        set_actives_on_source_data = False

        if (scale and dataset.active_scalars_info.association == FieldAssociation.CELL) or (
                orient and dataset.active_vectors_info.association == FieldAssociation.CELL
        ):
            source_data = dataset.cell_centers()
            set_actives_on_source_data = True

        # Clean the points before glyphing
        if tolerance is not None:
            small = pyvista.PolyData(source_data.points)
            small.point_data.update(source_data.point_data)
            source_data = small.clean(
                point_merging=True,
                tolerance=tolerance,
                lines_to_points=False,
                polys_to_lines=False,
                strips_to_polys=False,
                inplace=False,
                absolute=absolute,
                progress_bar=progress_bar,
            )
            set_actives_on_source_data = True

        # upstream operations (cell to point conversion, point merging) may have unset the correct active
        # scalars/vectors, so set them again
        if set_actives_on_source_data:
            if scale:
                source_data.set_active_scalars(dataset.active_scalars_name, preference='point')
            if orient:
                source_data.set_active_vectors(dataset.active_vectors_name, preference='point')

        return cls(
            input_data=source_data,
            glyph=glyph,
            scaling=scale,
            scale_mode=scale_mode,
            scale_factor=scale_factor,
            range_=range_,
            orient=orient,
            index_mode=index_mode,
            **kwargs
        )


def main():
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

    print(glyph.GetColorModeAsString(), glyph.color_mode)

    pl = pv.Plotter()
    distanceToCamera.SetRenderer(pl.renderer)
    distanceToCamera.Update()
    pl.add_mesh(sphere, color='grey', opacity=.3)
    pl.add_mesh(glyph)

    pl.show()


if __name__ == '__main__':
    main()
