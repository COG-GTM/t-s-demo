from typing import Optional, Union
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


def test_arguments_items_cached_per_class() -> None:
    class FirstArguments(ArgumentsBase):
        foo: str

    class SecondArguments(ArgumentsBase):
        bar: int

    FirstArguments.items()
    SecondArguments.items()

    with mock.patch('osprey.engine.udf.arguments.get_type_hints', side_effect=AssertionError('cache miss')):
        for _ in range(3):
            assert list(FirstArguments.items()) == ['foo']
            assert list(SecondArguments.items()) == ['bar']
            assert not FirstArguments.is_extra_arguments_allowed()
            assert not SecondArguments.is_extra_arguments_allowed()
