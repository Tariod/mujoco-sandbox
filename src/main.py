import json
import mujoco
import numpy as np
import random
import threading
import time

from reactivex import create, interval, of
from reactivex import operators as ops
from reactivex.scheduler import ThreadPoolScheduler


def log(action, value, verbose):
    if verbose:
        print(
            f"{action}: {value}, Thread: {threading.current_thread().name}, Time: {time.time()}"
        )


xml = """
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


class RemoteSource:
    def __init__(self, rate, take, latency, latency_variance, verbose):
        self.__verbose = verbose
        self.__model = mujoco.MjModel.from_xml_string(xml)
        self.__model.opt.timestep = rate
        self.__model_data = mujoco.MjData(self.__model)
        self.__model_data.qpos = np.ones_like(self.__model_data.qpos) * np.pi / 2

        source_scheduler = ThreadPoolScheduler(1)
        self.__simulation = interval(rate, scheduler=source_scheduler).pipe(
            ops.map(lambda it: self.__mj_step(it)),
            ops.do_action(lambda it: log("Emitted", it, self.__verbose)),
            ops.take(take),
            ops.publish(),
        )
        self.__remote_simulation = self.__simulation.pipe(
            ops.flat_map(
                lambda it: of(it).pipe(
                    ops.delay(
                        max(0, random.normalvariate(mu=latency, sigma=latency_variance))
                    )
                )
            )
        )

    def __mj_step(self, index):
        qpos = self.__model_data.qpos.copy()
        qvel = self.__model_data.qvel.copy()
        mujoco.mj_step(self.__model, self.__model_data)
        return {
            "id": index,
            "qpos": qpos,
            "qvel": qvel,
            "qfrc_bias": self.__model_data.qfrc_bias.copy(),
            "time": time.time(),
        }

    def pipe(self, *operators):
        return self.__remote_simulation.pipe(*operators)

    def start(self):
        self.__simulation.connect()


class PhysicsEngine:
    def __init__(self, source, strategy, rate, verbose):
        self.__rate = rate
        self.__verbose = verbose
        self.results = []
        mujoco_scheduler = ThreadPoolScheduler(1)
        self.__physics_engine = source.pipe(
            ops.do_action(lambda it: log("Received", it, self.__verbose)),
            strategy(),
            ops.observe_on(mujoco_scheduler),
            ops.map(self.__calculate),
            ops.do_action(lambda it: self.results.append(it)),
        )

    def __calculate(self, value):
        model = mujoco.MjModel.from_xml_string(xml)
        model.opt.timestep = self.__rate
        model_data = mujoco.MjData(model)
        model_data.qpos = value["qpos"]
        model_data.qvel = value["qvel"]
        # model_data.qacc = value['qacc']

        mujoco.mj_inverse(model, model_data)

        return {
            "id": value["id"],
            "qfrc_bias": list(value["qfrc_bias"]),
            "qfrc_inverse": list(model_data.qfrc_inverse.copy()),
            "start_time": value["time"],
            "end_time": time.time(),
        }

    def __dump(self):
        print("Done!")
        with open("./sample.json", "w") as outfile:
            json.dump(self.results, outfile, indent=4)

    def subscribe(self):
        return self.__physics_engine.subscribe(
            on_next=lambda it: log("Calculated", it, self.__verbose),
            on_completed=lambda: self.__dump(),
        )


def default_strategy(key="id"):
    def default_strategy_inner(source):
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

    return default_strategy_inner


def run(
    rate=0.02,
    take=50,
    network_latency=0.005,
    network_latency_variance=0.005,
    verbose=False,
):
    remote_source = RemoteSource(
        rate, take, network_latency, network_latency_variance, verbose
    )
    physics_engine = PhysicsEngine(remote_source, default_strategy, rate, verbose)
    physics_engine.subscribe()
    if verbose:
        print(f"Start Thread: {threading.current_thread().name}, Time: {time.time()}")
    remote_source.start()


if __name__ == "__main__":
    run()
    input()
