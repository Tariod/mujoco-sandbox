from reactivex import operators as ops

default_strategy = lambda: ops.map(lambda it: it)
