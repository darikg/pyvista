import collections.abc
import warnings
from typing import Optional, Union, Dict, Tuple, TypeVar

from vtkmodules.vtkRenderingCore import vtkDistanceToCamera

import pyvista
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


class InputArray(AnnotatedIntEnum):
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


class Glyph3D(_vtk.vtkGlyph3D):
    def __init__(
            self,
            input_data: _Input,
            glyph: Optional[_Glyph],
            scaling: Optional[bool] = None,
            scale_mode: Optional[_IntoMode[ScaleMode]]= None,
            scale_factor: Optional[float] = None,
            clamp_range: Optional[_ClampRange] = None,
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

        if clamp_range is not None:
            self.clamp_range = clamp_range

        if index_mode is not None:
            self.index_mode = index_mode

        for (i, name) in enumerate((scalars_name, vectors_name, normals_name, color_scalars_name)):
            if name is not None:
                self.set_input_array_name(i, name)

    def set_input_array_name(self, typ: _IntoMode[InputArray], name: str) -> None:
        self.SetInputArrayToProcess(InputArray.from_any(typ).value, 0, 0, FieldAssociation.POINT.value, name)

    @property
    def scaling(self) -> bool:
        return bool(self.GetScaling())

    @scaling.setter
    def scaling(self, state: bool):
        self.SetScaling(state)

    @property
    def scale_factor(self) -> float:
        return self.GetScaleFactor()

    @scale_factor.setter
    def scale_factor(self, factor: float):
        self.SetScaleFactor(factor)

    @property
    def clamp_range(self) -> Optional[_ClampRange]:
        return self.GetRange() if self.GetClamping() else None

    @clamp_range.setter
    def clamp_range(self, rng: Optional[_ClampRange]):
        if rng is not None:
            self.SetRange(*rng)
            self.SetClamping(True)
        else:
            self.SetClamping(False)

    @property
    def scale_mode(self) -> ScaleMode:
        return ScaleMode(self.GetScaleMode())

    @scale_mode.setter
    def scale_mode(self, mode: _IntoMode[ScaleMode]):
        self.SetScaleMode(ScaleMode.from_any(mode).value)

    @property
    def orient(self) -> bool:
        return bool(self.GetOrient())

    @orient.setter
    def orient(self, state: bool):
        self.SetOrient(state)

    def set_glyph(self, glyphs: _Glyph):
        if isinstance(glyphs, collections.abc.Mapping):
            for index, glyph in glyphs.items():
                if isinstance(glyph, _vtk.vtkDataSet):
                    self.SetSourceData(index, glyph)
                else:
                    self.SetSourceConnection(index, glyph)
        else:
            if isinstance(glyphs, _vtk.vtkDataSet):
                self.SetSourceData(glyphs)
            else:
                self.SetSourceConnection(glyphs)

    @property
    def index_mode(self) -> IndexMode:
        return IndexMode(self.GetIndexMode())

    @index_mode.setter
    def index_mode(self, mode: _IntoMode[IndexMode]):
        self.SetIndexMode(IndexMode.from_any(mode).value)

    @property
    def color_mode(self) -> ColorMode:
        return ColorMode(self.GetColorMode())

    @color_mode.setter
    def color_mode(self, mode: _IntoMode[ColorMode]):
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
            clamp_range: Optional[_ClampRange] = False,
            progress_bar=False,
            **kwargs,
    ):
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
            clamp_range=clamp_range,
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
