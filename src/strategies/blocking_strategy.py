import threading
from reactivex import create


def blocking_strategy(key="id"):
    def blocking_strategy_inner(source):
        def subscribe(observer, scheduler=None):
            lock = threading.RLock()
            current_index, buffer = 0, {}

            def on_next(value):
                nonlocal current_index, buffer
                index = value[key]
                with lock:
                    if index != current_index:
                        buffer[index] = value
                    else:
                        current_index += 1
                        observer.on_next(value)
                        while len(buffer) > 0 and current_index in buffer:
                            observer.on_next(buffer.pop(current_index))
                            current_index += 1

            return source.subscribe(
                on_next, observer.on_error, observer.on_completed, scheduler=scheduler
            )

        return create(subscribe)

    return blocking_strategy_inner
