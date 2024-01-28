import numpy as np


class ArrayLikeWrapper:
    """A class that implements the NumPy array protocol but isn't isinstance(np.ndarray)"""
    def __init__(self, arr):
        self._arr = np.asarray(arr)

    def __getattr__(self, item):
        return getattr(self.__getattribute__('_arr'), item)
