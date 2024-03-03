import multiprocessing as mp
import random
import threading

from reactivex import abc, concat, create, interval, of
from reactivex import operators as ops
from reactivex import scheduler as schedulers
from reactivex import subject as subjects
from time import sleep, time_ns
from typing import Any, Optional


def init_worker(connection, calculate_latency, filename, verbose):
    source = subjects.Subject()

    strategy = lambda: ops.compose(ops.map(lambda it: it))

    def calculate(it):
        sleep(calculate_latency)
        return {"id": it["id"], "start_time": it["start_time"], "end_time": time_ns()}

    def dump(filename):
        def dump_inner(source):
            def subscribe(observer, scheduler=None):
                file = open(filename, "a")
                lock = threading.RLock()

                def on_next(value):
                    with lock:
                        file.write(
                            f'{value["id"]},{value["start_time"]},{value["end_time"]}\n'
                        )
                        observer.on_next(value)

                def on_error(error):
                    file.close()
                    observer.on_error(error)

                def on_completed():
                    file.close()
                    observer.on_completed()

                return source.subscribe(
                    on_next, on_error, on_completed, scheduler=scheduler
                )

            return create(subscribe)

        return dump_inner

    worker = source.pipe(strategy(), ops.map(calculate), dump(filename))

    worker.subscribe(lambda it: print("Worker: ", it) if verbose else None)

    msg = connection.recv()
    while msg is not None:
        source.on_next(msg)
        msg = connection.recv()
    source.on_completed()


if __name__ == "__main__":
    VERBOSE = False
    RATE = 0.1
    TAKE = 10
    GENERATE_LATENCY = 0.02
    NETWORK_LATENCY = 0.02
    NETWORK_LATENCY_VARIANCE = 0.04
    CALCULATE_LATENCY = 0.05

    ctx = mp.get_context("spawn")
    worker_connection, producer_connection = ctx.Pipe(duplex=False)

    def init_value(id: int):
        return {"id": id, "start_time": time_ns()}

    def generate(it):
        sleep(GENERATE_LATENCY)
        return it

    generate_scheduler = schedulers.ThreadPoolScheduler(2)
    source = interval(RATE).pipe(
        ops.take(TAKE),
        ops.map(init_value),
        ops.observe_on(generate_scheduler),
        ops.map(generate),
    )
    worker = ctx.Process(
        target=init_worker,
        args=(
            worker_connection,
            CALCULATE_LATENCY,
            f"results_{time_ns()}.csv",
            VERBOSE,
        ),
    )

    def send_value(it):
        producer_connection.send(it)
        return it

    def close_write_connection(
        observer: abc.ObserverBase[Any], scheduler: Optional[abc.SchedulerBase] = None
    ):
        _scheduler = scheduler or schedulers.ImmediateScheduler.singleton()

        def action(_: abc.SchedulerBase, __: Any) -> None:
            producer_connection.send(None)
            producer_connection.close()
            observer.on_completed()

        return _scheduler.schedule(action)

    def delay_messages(delay: float, variance: float):
        return ops.flat_map(
            lambda it: of(it).pipe(
                ops.delay(max(0, random.normalvariate(mu=delay, sigma=variance)))
            )
        )

    delayed_source = source.pipe(
        delay_messages(NETWORK_LATENCY, NETWORK_LATENCY_VARIANCE)
    )

    simulation = concat(
        delayed_source.pipe(ops.map(send_value)), create(close_write_connection)
    )

    worker.start()
    simulation.pipe(
        ops.do_action(lambda it: print("Source: ", it) if VERBOSE else None)
    ).run()
