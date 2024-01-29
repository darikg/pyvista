from typing import TypeVar, Generic, Callable, Dict, Any, Optional

import numpy as np
import pytest

T = TypeVar('T')


class ParametrizedMappings(Generic[T]):
    """Parametrize a test function over mappings of some original value

    e.g. given the function

        from decimal import Decimal

        def convert_to_int(x: str | float | Decimal) -> int:
            return int(x)

    instead of the test

        @pytest.mark.parametrize(
            ('val', 'expected'),
            [('3', 3), (3.0, 3), (Decimal(3), 3)],
        )
        def test_convert_to_int(val, expected):
            assert convert_to_int(val) == expected

    write

        parametrize_number_types = ParametrizedMappings(
            dict(string=str, float=float, decimal=Decimal)
        )

        @paremetrize_number_types('val', 'expected', 3)
        def test_convert_to_int(val, expected):
            assert convert_to_int(val) == expected
    """
    def __init__(
            self,
            mappings: Dict[str, Callable[[T], Any]],
    ):
        self.mappings = mappings

    def __call__(
            self,
            var_name: str,
            expected_var_name: str,
            orig_val: T,
            expected_mapping: Optional[Callable[[T], Any]] = None,
    ):
        expected_val = expected_mapping(orig_val) if expected_mapping else orig_val
        vals = [(fn(orig_val), expected_val) for fn in self.mappings.values()]
        test_names = [f'{var_name}: {fn_name}' for fn_name in self.mappings.keys()]

        def wrapper(test_fn):
            return pytest.mark.parametrize(
                (var_name, expected_var_name), vals, ids=test_names
            )(test_fn)

        return wrapper


class ArrayLikeWrapper:
    """A class that implements the NumPy array protocol but isn't isinstance(np.ndarray)"""
    def __init__(self, arr):
        self._arr = np.asarray(arr)

    def __getattr__(self, item):
        return getattr(self.__getattribute__('_arr'), item)
