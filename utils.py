from functools import reduce


def compose(*func):
    def compose_inner(f, g):
        return lambda it: f(g(it))

    return reduce(compose_inner, func, lambda it: it)


__all__ = ["compose"]
