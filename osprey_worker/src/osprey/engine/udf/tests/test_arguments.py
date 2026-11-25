from typing import Any, Dict, List, Optional, Union
from unittest import mock

from osprey.engine.udf.arguments import ArgumentsBase, ConstExpr

StrConstExpr = ConstExpr[str]  # This being inside the below function is causing mypy to crash


def test_arguments_items() -> None:
    class Arguments(ArgumentsBase):
        foo: str
        bar: StrConstExpr

    items = Arguments.items()

    assert list(items) == ['foo', 'bar']
    assert items['foo'] is str
    assert items['bar'] is StrConstExpr


def test_arguments_can_be_none() -> None:
    class Arguments(ArgumentsBase):
        optional: Optional[str]
        union: Union[str, int, None]
        none: None
        obj: object
        string: str
        integer: int

    assert Arguments.kwarg_can_be_none('optional')
    assert Arguments.kwarg_can_be_none('union')
    assert Arguments.kwarg_can_be_none('none')
    assert Arguments.kwarg_can_be_none('obj')
    assert not Arguments.kwarg_can_be_none('string')
    assert not Arguments.kwarg_can_be_none('integer')


def test_arguments_caches_hold_every_class() -> None:
    class FirstArguments(ArgumentsBase):
        foo: str
        extra_arguments: Dict[str, int]

    class SecondArguments(ArgumentsBase):
        bar: int
        extra_arguments: Dict[str, str]

    class ThirdArguments(ArgumentsBase):
        baz: bool

    # classmethod hides the lru_cache wrapper; __func__ is the wrapper with cache_info()
    caches: List[Any] = [
        getattr(ArgumentsBase.items, '__func__'),
        getattr(ArgumentsBase.is_extra_arguments_allowed, '__func__'),
        getattr(ArgumentsBase.get_extra_arguments_values_type, '__func__'),
    ]
    assert all(cache.cache_parameters()['maxsize'] is None for cache in caches)

    def warm() -> None:
        assert list(FirstArguments.items()) == ['foo', 'extra_arguments']
        assert list(SecondArguments.items()) == ['bar', 'extra_arguments']
        assert list(ThirdArguments.items()) == ['baz']
        assert FirstArguments.is_extra_arguments_allowed()
        assert SecondArguments.is_extra_arguments_allowed()
        assert not ThirdArguments.is_extra_arguments_allowed()
        assert FirstArguments.get_extra_arguments_values_type() is int
        assert SecondArguments.get_extra_arguments_values_type() is str

    warm()
    misses_before = [cache.cache_info().misses for cache in caches]

    with mock.patch('osprey.engine.udf.arguments.get_type_hints', side_effect=AssertionError('cache miss')):
        for _ in range(3):
            warm()

    assert [cache.cache_info().misses for cache in caches] == misses_before
