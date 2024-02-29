import multiprocessing as mp

from reactivex import abc, concat, create, interval
from reactivex import operators as ops
from reactivex import scheduler as schedulers
from reactivex import subject as subjects
from time import sleep, time
from typing import Any, Optional


def init_worker(read_connection, calculate_latency):
    source = subjects.Subject()

    def calculate(it):
        sleep(calculate_latency)
        return {'id': it['id'], 'start_time': it['start_time'], 'end_time': time()}

    worker = source.pipe(ops.map(calculate))

    worker.subscribe(lambda it: print("Worker: ", it))

    msg = read_connection.recv()
    while msg is not None:
        source.on_next(msg)
        msg = read_connection.recv()
    source.on_completed()


if __name__ == '__main__':
    RATE = 0.1
    TAKE = 10
    GENERATE_LATENCY = 0.05
    CALCULATE_LATENCY = 0.05

    ctx = mp.get_context('spawn')
    read_connection, write_connection = ctx.Pipe(duplex=False)


    def init_value(id):
        return {'id': id, 'start_time': time()}


    def generate(it):
        sleep(GENERATE_LATENCY)
        return it


    generate_scheduler = schedulers.ThreadPoolScheduler(5)
    source = interval(RATE).pipe(ops.take(TAKE), ops.map(init_value), ops.observe_on(generate_scheduler),
                                 ops.map(generate))
    worker = ctx.Process(target=init_worker, args=(read_connection, CALCULATE_LATENCY))


    def send_value(it):
        write_connection.send(it)
        return it


    def close_write_connection(observer: abc.ObserverBase[Any], scheduler: Optional[abc.SchedulerBase] = None):
        _scheduler = scheduler or schedulers.ImmediateScheduler.singleton()

        def action(_: abc.SchedulerBase, __: Any) -> None:
            write_connection.send(None)
            write_connection.close()
            observer.on_completed()

        return _scheduler.schedule(action)


    simulation = concat(source.pipe(ops.map(send_value)), create(close_write_connection))

    worker.start()
    simulation.pipe(ops.do_action(lambda it: print("Source: ", it))).run()
