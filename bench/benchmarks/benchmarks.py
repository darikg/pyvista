import inspect
from typing import Any

import numpy as np

import pyvista


# def generate_cells(n_cells: int) -> np.ndarray:
#     """Generate a random array of cells."""
#     cell_sz = 3
#     cells = np.zeros((n_cells, cell_sz + 1), dtype=pyvista.ID_TYPE)
#     cells[:, 0] = cell_sz
#     return cells.flatten()
#
#
# class ConstructCellArraySuite:
#     param_names = ['n_cells',]
#     params =  (10 ** np.linspace(4, 8, 10)).astype('int')
#
#     def __init__(self):
#         self.cells = np.zeros(0)
#
#     def setup(self, n_cells: int):
#         self.cells = generate_cells(n_cells)
#
#     def time_make_cells(self, n_cells: int):
#         _ = pyvista.CellArray(self.cells)


class LoadExamplesSuite:
    pass


def is_load_fn(obj: Any) -> bool:
    return inspect.isfunction(obj) and obj.__name__.startswith('load_')


for name, fn in inspect.getmembers(pyvista.examples, is_load_fn):
    setattr(LoadExamplesSuite, 'time_' + name, lambda self: fn())



