from typing import Sequence

from vtkmodules.vtkFiltersCore import vtkConnectivityFilter

from pyvista.core.filters.alg import AlgorithmWrapper, IVar, AlgorithmBase


@AlgorithmWrapper(
    ivars=[
        ('scalar_connectivity', bool,
         """Turn on/off connectivity based on scalar value.
            If on, cells are connected only if they share points AND 
            one of the cells scalar values falls in the scalar range specified."""),
        ('scalar_range', (float, float),
         'The scalar range to use to extract cells based on scalar connectivity.'),
        ('extraction_mode', ('point_seeded', 'cell_seeded', 'largest_region', 'closest_point', 'all_regions')),
        ('closest_point', (float, float, float),
         'The x-y-z point coordinates when extracting the region closest to a specified point.'),
        IVar('n_extracted_regions', int, 'The number of connected regions',
             init=False, setter=None, vtkname='NumberOfExtractedRegions'),
        ('color_regions', bool, 'Turn on/off the coloring of connected regions.'),
    ],
    init_args=[
        ('seed_list', Sequence[int], 'List of point ids/cell ids used to seed regions.')
    ]
)
class VertexConnectivity(vtkConnectivityFilter, AlgorithmBase):
    def set_seed_list(self, seed_list: Sequence[int]):
        self.InitializeSeedList()
        for seed in seed_list:
            self.AddSeed(seed)


if __name__ == '__main__':
    alg = VertexConnectivity(closest_point=[1, 2, 3])
    assert alg.GetClosestPoint() == tuple(alg.closest_point) == (1.0, 2.0, 3.0)


