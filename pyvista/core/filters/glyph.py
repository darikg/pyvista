import collections.abc
import inspect
from typing import Optional, Union, Dict, Tuple, TypeVar, Any, List, Type, Callable

import numpy as np
from numpydoc import docscrape
from vtkmodules.vtkRenderingCore import vtkDistanceToCamera

import pyvista.core._vtk_core as _vtk
from pyvista import AnnotatedIntEnum
from pyvista.core.utilities.arrays import (
    FieldAssociation,
)

_ClampRange = Tuple[float, float]
_Input = Union[_vtk.vtkDataSet, _vtk.vtkAlgorithmOutput]
_Glyph = Union[_Input, Dict[int, _Input]]

# Advantages
# -- Allow algorithm inputs as well as datasets
# -- Set input variable names without setting active fields on the source dataset


class _ScaleMode(AnnotatedIntEnum):
    SCALAR = (0, 'scalar')
    VECTOR = (1, 'vector')
    VECTOR_COMPONENTS = (2, 'vector_components')
    OFF = (3, 'off')


class _ColorMode(AnnotatedIntEnum):
    SCALE = (0, 'scale')
    SCALAR = (1, 'scalar')
    VECTOR = (2, 'vector')


class _VectorMode(AnnotatedIntEnum):
    VECTOR = (0, 'vector')
    NORMAL = (1, 'normal')
    ROTATION_OFF = (2, 'rotation_off')
    FOLLOW_CAMERA_DIRECTION = (3, 'follow_camera_direction')


class _IndexMode(AnnotatedIntEnum):
    OFF = (0, 'off')
    SCALAR = (1, 'scalar')
    VECTOR = (2, 'vector')


class _InputArrayType(AnnotatedIntEnum):
    # From the vtkGlyph3d docs: You can set what arrays to use for the
    # scalars, vectors, normals, and color scalars by using the
    # SetInputArrayToProcess methods in vtkAlgorithm. The first array is
    # scalars, the next vectors, the next normals and finally color scalars.
    SCALARS = (0, 'scalars')
    VECTORS = (1, 'vectors')
    NORMALS = (2, 'normals')
    COLOR_SCALARS = (3, 'color_scalars')


_T_Enum = TypeVar('_T_Enum', bound=AnnotatedIntEnum)
_IntoMode = Union[int, str, _T_Enum]
_T_Alg = TypeVar('_T_Alg', bound=_vtk.vtkAlgorithm)
DataSource = Union[_vtk.vtkDataSet, _vtk.vtkAlgorithmOutput]


def snake_to_camel_case(name: str) -> str:
    return ''.join(word.title() for word in name.split('_'))


class IVar:
    def __init__(
            self, pvname: str, typ: Any, desc: Optional[Union[str, List[str]]] = None, vtkname: Optional[str] = None):
        self.pvname = pvname
        self.vtkname = vtkname or snake_to_camel_case(pvname)
        self.typ = typ
        self.is_annotated_int_enum = False
        if isinstance(typ, type):
            if issubclass(typ, AnnotatedIntEnum):
                self.is_annotated_int_enum = True
                self.typestr = 'str'
            else:
                self.typestr = typ.__name__
        elif isinstance(typ, tuple):  # e.g. (float, float)
            self.typestr = f"({', '.join(str(el.__name__) for el in typ)})"
        else:
            self.typestr = str(typ)
        self.desc = desc

    def property_desc(self):
        if isinstance(self.desc, str):
            return self.desc
        else:
            return '\n'.join(self.desc)

    def install(self, cls: _T_Alg):
        name, typ = self.vtkname, self.typ

        if self.is_annotated_int_enum:
            def fget(alg) -> str:
                return typ(getattr(alg, f'Get{name}')()).annotation

            def fset(alg, val: str):
                getattr(alg, f'Set{name}')(typ.from_str(val).value)
        else:
            def fget(alg):
                return getattr(alg, f'Get{name}')()

            def fset(alg, val):
                getattr(alg, f'Set{name}')(val)

            _set_in_out_types(fget, out_type=self.typestr)
            _set_in_out_types(fset, in_type=self.typestr)

        setattr(cls, self.pvname, property(fget, fset, doc=self.property_desc()))

    @classmethod
    def from_any(cls, alg: _T_Alg, obj: Any):
        if isinstance(obj, IVar):
            return obj
        elif isinstance(obj, tuple):
            return IVar(*obj)
        else:
            raise NotImplementedError(f"Can't construct IVar from {obj}")

    def numpydoc_name(self, optional=True) -> str:
        typestr = self.typestr.replace('typing.', '')
        out = self.pvname + ' : ' + typestr
        if optional:
            out += ', optional'
        return out

    def numpydoc_desc(self) -> List[str]:
        if isinstance(self.desc, list):
            out = self.desc
        else:
            out = [self.desc]

        if self.is_annotated_int_enum:
            allowable = ', '.join(f"'{v.annotation.lower()}'" for v in self.typ)
            out.append(f"Allowable values are {allowable}.")

        return out


_SENTINEL = object()


class FilterDecorator:
    def __init__(self, ivars: Optional[List] = None):
        self._ivars = ivars

    def _install_ivars(self, cls: Type[_T_Alg]) -> List[IVar]:
        """Add properties to the filter class converting from {Get/Set}Property to .property"""
        ivars = []
        for spec in self._ivars:
            ivar = IVar.from_any(cls, spec)
            ivar.install(cls)
            ivars.append(ivar)
        return ivars

    def _install_init(self, cls: _T_Alg, ivars: List[IVar]):
        """Add the default __init__ to the filter class"""
        ivar_names = frozenset(iv.pvname for iv in ivars)
        cls.__doc__ = cls.__doc__ or cls.__name__
        cls.__doc__ += """            
            Parameters
            ----------
            input_data: DataSource, optional
                The input mesh to which the glyph geometry is copied to each point.
            """

        def __init__(alg: _T_Alg, input_data: Optional[_Input] = None, **kwargs):
            super(cls, alg).__init__()

            if isinstance(input_data, _vtk.vtkDataSet):
                alg.SetInputData(input_data)
            else:
                alg.SetInputConnection(input_data)

            for name in ivar_names:
                if (val := kwargs.pop(name, _SENTINEL)) is not _SENTINEL:
                    setattr(alg, name, val)

            if hasattr(alg, '__post_init__'):
                alg.__post_init__(**kwargs)

        # Update the __init__ signature
        sig = inspect.signature(__init__)
        sig_params = [param for (name, param) in sig.parameters.items() if name != 'kwargs']
        sig_params.extend(
            inspect.Parameter(
                name=iv.pvname,
                annotation=f'Optional[{iv.typestr}]',
                default=None,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
            for iv in ivars
        )

        # Update the docstr
        docstr = docscrape.NumpyDocString(cls.__doc__)
        docstr['Parameters'].extend(
            docscrape.Parameter(name=iv.numpydoc_name(optional=True), type='', desc=iv.numpydoc_desc())
            for iv in ivars
        )

        if hasattr(cls, '__post_init__'):
            # Merge signature params and docstr
            sig_params.extend(
                param for (name, param) in inspect.signature(cls.__post_init__).parameters.items()
                if name != 'self'
            )
            if cls.__post_init__.__doc__:
                for (section, contents) in docscrape.FunctionDoc(cls.__post_init__).items():
                    if section == 'index':
                        continue  # docstr['index'].update(contents)?
                    docstr[section] += contents

        __init__.__signature__ = sig.replace(parameters=sig_params)
        cls.__doc__ = str(docstr)
        cls.__init__ = __init__

    def __call__(self, cls: Type[_T_Alg]) -> _T_Alg:
        ivars = self._install_ivars(cls)
        self._install_init(cls, ivars)
        return cls


def _set_in_out_types(fn: Callable, in_type: Optional[str] = None, out_type: Optional[str] = None):
    sig = inspect.signature(fn)
    if in_type:
        params = list(sig.parameters.values())
        assert len(params) == 2  # self, val
        params = [params[0], params[1].replace(annotation=in_type)]
        sig = sig.replace(parameters=params)
    if out_type:
        sig = sig.replace(return_annotation=out_type)
    fn.__signature__ = sig


@FilterDecorator(
    ivars=[
        ('scaling', bool, 'Turn on/off scaling of source geometry.'),
        ('scale_factor', float, 'Constant scaling factor.'),
        ('scale_mode', _ScaleMode, 'How to control scaling of the glyph geometry.'),
        IVar('range_', Tuple[float, float], vtkname='Range',
             desc='Range to map scalar values into if a table of glyphs is supplied.'),
        ('clamping', bool, 'Range to map scalar values into if a table of glyphs is supplied.'),
        ('index_mode', _IndexMode, [
            "Index into table of sources by scalar, by vector/normal magnitude, or no indexing.",
            "If indexing is turned off, then the first source glyph in the table of glyphs is used."]),
        ('orient', bool, 'Turn on/off orienting of input geometry along vector/normal.'),
        ('vector_mode', _VectorMode, 'Specify how to use vectors.'),
        ('color_mode', _ColorMode, 'Either color by scale, scalar or by vector/normal magnitude.'),
    ]
)
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

    """

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

    def set_input_array_to_process(self, typ: _IntoMode[_InputArrayType], name: str) -> None:
        """Set the name of a point data array in the input datasource to process.
        
        Parameters
        ----------
        typ : str
            The type of input array to specify. 
            Allowable values are 'scalars', 'vectors', 'normals', or 'color_scalars'.
            
        name : str
            The name of the array.
        """
        self.SetInputArrayToProcess(_InputArrayType.from_any(typ).value, 0, 0, FieldAssociation.POINT.value, name)

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

    pl = pv.Plotter()
    distanceToCamera.SetRenderer(pl.renderer)
    distanceToCamera.Update()
    # pl.add_mesh(sphere, color='grey', opacity=.3)
    pl.add_mesh(glyph)

    pl.show()


if __name__ == '__main__':
    main()
