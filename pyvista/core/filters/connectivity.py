from typing import Sequence

from numpy import ndarray
from vtkmodules.vtkFiltersCore import vtkConnectivityFilter

from pyvista.core.filters.alg import FilterWrapper, IVar


class VertexConnectivity(vtkConnectivityFilter):
    _wrapper = FilterWrapper(
        superclass=vtkConnectivityFilter,
        ivars=[
            ('scalar_connectivity', bool,
             """Turn on/off connectivity based on scalar value.
                If on, cells are connected only if they share points AND 
                one of the cells scalar values falls in the scalar range specified."""),
            ('scalar_range', (float, float),
             'The scalar range to use to extract cells based on scalar connectivity.'),
            ('extraction_mode', ('point_seeded', 'cell_seeded', 'largest_region', 'closest_point', 'all_regions')),
            ('closest_point', ndarray,
             'The x-y-z point coordinates when extracting the region closest to a specified point.'),
            IVar('n_extracted_regions', int, 'The number of connected regions',
                 init=False, setter=None, vtkname='NumberOfExtractedRegions'),
            ('color_regions', bool, 'Turn on/off the coloring of connected regions.'),

        ],
        init_args=[
            ('seed_list', Sequence[int], 'List of point ids/cell ids used to seed regions.')
        ]
    )

    def set_seed_list(self, seed_list: Sequence[int]):
        self.InitializeSeedList()
        for seed in seed_list:
            self.AddSeed(seed)
