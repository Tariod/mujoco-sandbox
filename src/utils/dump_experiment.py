import os
import threading

from reactivex import create


def dump_experiment(file_path):
    parent_folder_path, _ = os.path.split(file_path)
    if not os.path.exists(parent_folder_path):
        os.makedirs(parent_folder_path)

    def dump_experiment_inner(source):
        def subscribe(observer, scheduler=None):
            file = open(file_path, "a")
            lock = threading.RLock()

            def on_next(it):
                with lock:
                    row = ""
                    for index, key in enumerate(sorted(it.keys())):
                        value = it[key]
                        if index != 0:
                            row += ","
                        row += (
                            ",".join(str(i) for i in value)
                            if type(value) is list
                            else str(value)
                        )
                    file.write(row + "\n")
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

    return dump_experiment_inner
