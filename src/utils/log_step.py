import json
import threading
import time


def log_step(step, value):
    print(
        f"{time.time_ns()} \t-\t [{step}]({threading.current_thread().name}):\n    {value}"
    )
