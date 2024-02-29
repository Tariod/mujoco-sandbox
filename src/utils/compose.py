from functools import reduce
from typing import Any, Callable, TypeVar, overload

_A = TypeVar("_A")
_B = TypeVar("_B")
_C = TypeVar("_C")

_T_out = TypeVar("_T_out", covariant=True)


@overload
def compose(self, __f1: Callable[[_T_out], _A]) -> _A: ...


@overload
def compose(self, __f1: Callable[[_T_out], _A], __f2: Callable[[_A], _B]) -> _B: ...
@overload
def compose(
    self,
    __f1: Callable[[_T_out], _A],
    __f2: Callable[[_A], _B],
    __f3: Callable[[_B], _C],
) -> _C: ...


def compose(*functions: Callable[[Any], Any]) -> Any:
    def compose_inner(f, g):
        return lambda it: f(g(it))

    return reduce(compose_inner, functions, lambda it: it)


__all__ = ["compose"]
