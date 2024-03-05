import mujoco
import multiprocessing as mp
import numpy as np
import random
import time

from reactivex import concat, create, interval, of
from reactivex import operators as ops
from reactivex import scheduler as schedulers
from reactivex import subject as subjects
from strategies import strategies, Strategy
from utils import dump_experiment, log_step


class Simulation:
    def __init__(self, model_xml, init_model_state, rate, take, verbose):
        self.__model = mujoco.MjModel.from_xml_string(model_xml)
        self.__model.opt.timestep = rate
        self.__model_data = mujoco.MjData(self.__model)
        init_model_state(self.__model_data)
        self.__simulation = interval(rate).pipe(
            ops.take(take),
            ops.map(self.__mj_step),
            ops.do_action(lambda it: log_step("Emitted", it) if verbose else None),
        )

    def __mj_step(self, id):
        qpos = list(self.__model_data.qpos.copy())
        qvel = list(self.__model_data.qvel.copy())
        mujoco.mj_step(self.__model, self.__model_data)
        qfrc_bias = list(self.__model_data.qfrc_bias.copy())
        start_time = time.time_ns()
        return {
            "id": id,
            "qpos": qpos,
            "qvel": qvel,
            "qfrc_bias": qfrc_bias,
            "start_time": start_time,
        }

    def pipe(self, *operators):
        return self.__simulation.pipe(*operators)

    def run(self):
        return self.__simulation.run()


class NetworkSimulation:
    def __init__(self, source, connection, latency, latency_variance):
        self.__simulation = concat(
            source.pipe(
                self.__delay(latency, latency_variance), self.__send(connection)
            ),
            self.__close_connection(connection),
        )

    def __delay(self, latency, latency_variance):
        return ops.flat_map(
            lambda it: of(it).pipe(
                ops.delay(
                    max(0, random.normalvariate(mu=latency, sigma=latency_variance))
                )
            )
        )

    def __send(self, connection):
        def send_inner(value):
            connection.send(value)
            return value

        return ops.map(send_inner)

    def __close_connection(self, connection):
        def close_connection_inner(observer, scheduler=None):
            _scheduler = scheduler or schedulers.ImmediateScheduler.singleton()

            def handle_close(_, __) -> None:
                connection.send(None)
                connection.close()
                observer.on_completed()

            return _scheduler.schedule(handle_close)

        return create(close_connection_inner)

    def run(self):
        return self.__simulation.run()


class PhysicsEngine:
    def __init__(self, source, model, strategy, verbose):
        self.__model = model
        self.__physics_engine = source.pipe(
            ops.map(lambda it: {**it, "received_time": time.time_ns()}),
            ops.do_action(lambda it: log_step("Received", it) if verbose else None),
            strategy(),
            ops.map(self.__calculate),
            ops.do_action(lambda it: log_step("Calculated", it) if verbose else None),
        )

    def __calculate(self, value):
        model = mujoco.MjModel.from_xml_string(self.__model["xml"])
        model.opt.timestep = self.__model["rate"]
        model_data = mujoco.MjData(model)

        model_data.qpos = value["qpos"]
        model_data.qvel = value["qvel"]
        # model_data.qacc = value['qacc']

        mujoco.mj_inverse(model, model_data)

        qfrc_inverse = list(model_data.qfrc_inverse.copy())
        end_time = time.time_ns()
        return {**value, "qfrc_inverse": qfrc_inverse, "end_time": end_time}

    def pipe(self, *operators):
        return self.__physics_engine.pipe(*operators)

    def subscribe(self):
        return self.__physics_engine.subscribe()


def init_physics_engine_worker(
    connection, model, strategy_name, dump_file_path, verbose
):
    source = subjects.Subject()

    strategy = strategies[strategy_name]
    physics_engine = PhysicsEngine(source, model, strategy, verbose)
    physics_engine = physics_engine.pipe(dump_experiment(dump_file_path))

    physics_engine.subscribe()

    msg = connection.recv()
    while msg is not None:
        source.on_next(msg)
        msg = connection.recv()
    source.on_completed()


def run(
    rate=0.025,
    take=100,
    network_latency=0.01,
    network_latency_variance=0.01,
    strategy=Strategy.DEFAULT,
    verbose=True,
):
    pendulum_xml = """
    <mujoco>
      <worldbody>
        <body name='box_and_sphere' euler='0 0 -30'>
          <joint name='swing' type='hinge' axis='0 1 0' pos='0 0 1' />
          <geom name='cord' type='cylinder' size='.02 1' mass='0' />
          <geom name='bob' type='sphere' pos='0 0 -1' mass='1' size='.1' />
        </body>
      </worldbody>
    </mujoco>
    """

    dump_file_path = f"./data/pendulum_exp_{time.time_ns()}_rate_{rate}_latency_{network_latency}_variance_{network_latency_variance}_strategy_{strategy.value}.csv"

    def init_model_state(model_data):
        model_data.qpos = np.ones_like(model_data.qpos) * np.pi / 2

    simulation = Simulation(pendulum_xml, init_model_state, rate, take, verbose)

    ctx = mp.get_context("spawn")
    consumer_connection, producer_connection = ctx.Pipe(duplex=False)

    delayed_simulation = NetworkSimulation(
        simulation, producer_connection, network_latency, network_latency_variance
    )

    physics_engine_process = ctx.Process(
        target=init_physics_engine_worker,
        args=(
            consumer_connection,
            {"xml": pendulum_xml, "rate": rate},
            strategy,
            dump_file_path,
            verbose,
        ),
    )

    physics_engine_process.start()
    delayed_simulation.run()


if __name__ == "__main__":
    run()
