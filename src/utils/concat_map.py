from asyncio import Future
from typing import Any, Callable, List, Optional, TypeVar, Union, cast

from reactivex import Observable, abc, from_, from_future, typing
from reactivex.disposable import CompositeDisposable, SingleAssignmentDisposable
from reactivex.internal import synchronized
from reactivex.internal.basic import identity
from reactivex import operators as ops
from reactivex.typing import Mapper

_T = TypeVar("_T")


def concat_all() -> Callable[[Observable[Observable[_T]]], Observable[_T]]:
    def concat_all_inner(source: Observable[Observable[_T]]) -> Observable[_T]:
        def subscribe(
            observer: abc.ObserverBase[_T],
            scheduler: Optional[abc.SchedulerBase] = None,
        ):
            group = CompositeDisposable()
            is_stopped = [False]

            initial_assignment = SingleAssignmentDisposable()
            queue: List[Observable[_T]] = []

            def subscribe(inner_source: Observable[_T]):
                inner_subscription = SingleAssignmentDisposable()
                group.add(inner_subscription)

                inner_source = (
                    from_future(inner_source)
                    if isinstance(inner_source, Future)
                    else inner_source
                )

                @synchronized(source.lock)
                def on_completed():
                    group.remove(inner_subscription)
                    if queue:
                        subscribe(queue.pop(0))
                    else:
                        if is_stopped[0] and len(group) == 1:
                            observer.on_completed()

                on_next: typing.OnNext[_T] = synchronized(source.lock)(observer.on_next)
                on_error = synchronized(source.lock)(observer.on_error)
                inner_subscription.disposable = inner_source.subscribe(
                    on_next, on_error, on_completed, scheduler=scheduler
                )

            def on_next(inner_source: Union[Observable[_T], "Future[_T]"]):
                if len(group) == 1:
                    subscribe(inner_source)
                else:
                    queue.append(inner_source)

            def on_completed():
                is_stopped[0] = True
                if len(group) == 1:
                    observer.on_completed()

            group.add(initial_assignment)
            initial_assignment.disposable = source.subscribe(
                on_next, observer.on_error, on_completed, scheduler=scheduler
            )
            return group

        return Observable(subscribe)

    return concat_all_inner


_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")


def _concat_map_internal(
    source: Observable[_T1], mapper: Optional[Mapper[_T1, Any]] = None
) -> Observable[Any]:
    def projection(x: _T1) -> Observable[Any]:
        mapper_result: Any = mapper(x) if mapper else identity
        if isinstance(mapper_result, Future):
            result: Observable[Any] = from_future(cast("Future[Any]", mapper_result))
        elif isinstance(mapper_result, Observable):
            result = mapper_result
        else:
            result = from_(mapper_result)
        return result

    return source.pipe(ops.map(projection), concat_all())


def concat_map(
    mapper: Optional[Mapper[_T1, Observable[_T2]]] = None
) -> Callable[[Observable[_T1]], Observable[_T2]]:
    def concat_map_inner(source: Observable[_T1]) -> Observable[_T2]:
        if callable(mapper):
            ret = _concat_map_internal(source, mapper=mapper)
        else:
            ret = _concat_map_internal(source, mapper=lambda _: mapper)

        return ret

    return concat_map_inner


__all__ = ["concat_map", "concat_all"]
