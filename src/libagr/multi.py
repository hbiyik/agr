import multiprocessing
import threading
import sys
import time
import traceback
import collections

from libagr import log
from libagr import defs


class Worker(multiprocessing.Process):
    def __init__(self, pipe, wid, callback, *args, **kwargs):
        self.w_pipe = pipe
        self.w_id = wid
        self.w_callback = callback
        self.w_args = args
        self.w_kwargs = kwargs
        self.retval = None
        super().__init__(name=f"Worker-{self.w_id}")

    def run(self):
        if self.w_id == 377:
            pass
        log.logger.debug(f"Worker {self.w_id} started")
        try:
            retval = self.w_callback(*self.w_args, **self.w_kwargs)
        except KeyboardInterrupt as err:
            retval = err
        except Exception as err:
            log.logger.debug(f"Worker {self.w_id} error")
            print(err, file=sys.stderr)
            traceback.print_tb(err.__traceback__)
            retval = err
        self.retval = retval
        self.w_pipe.send(retval)
        self.w_pipe.close()
        log.logger.debug(f"Worker {self.w_id} ended")


class ProcMan:
    def __init__(self, numworkers=None, waittime=0.1, stoponexc=False):
        self.numworkers = numworkers or defs.NUMCORES
        self.workers = {}
        self.workers_backlog = {}
        self.waittime = waittime
        self.workerid = 0
        self.stoponexc = stoponexc
        self._returns = {}
        self._backlog = None
        log.logger.debug(f"started process manager with {self.numworkers} workers")

    @property
    def returns(self):
        return collections.OrderedDict(sorted(self._returns.items()))

    def add(self, callback, *args, **kwargs):
        self.popworker()
        pipe_recv, pipe_send = multiprocessing.Pipe(True)
        w = Worker(pipe_send, self.workerid, callback, *args, **kwargs)
        self.workerid += 1
        self.workers[w] = pipe_recv
        w.start()
        return self.workerid

    def backlog(self, callback, *args, **kwargs):
        pipe_recv, pipe_send = multiprocessing.Pipe(True)
        w = Worker(pipe_send, self.workerid, callback, *args, **kwargs)
        self.workerid += 1
        self.workers_backlog[w] = pipe_recv
        return self.workerid

    def popworker(self):
        while len(self.workers) >= self.numworkers:
            for dropworker in self.joinnext():
                dropworker.close()
                self.workers.pop(dropworker)
                break

    def _start(self):
        for worker, pipe_recv in self.workers_backlog.items():
            self.popworker()
            self.workers[worker] = pipe_recv
            worker.start()

    def start(self):
        self._backlog = threading.Thread(target=self._start)
        self._backlog.daemon = True
        self._backlog.start()

    def joinnext(self):
        for worker, pipe_recv in self.workers.items():
            if worker.exitcode is not None and worker.w_id not in self._returns:
                retval = pipe_recv.recv()
                self._returns[worker.w_id] = retval, worker.w_args, worker.w_kwargs
                if self.stoponexc and isinstance(retval, Exception):
                    for subworker, _ in self.workers.items():
                        if subworker.exitcode is None:
                            worker.terminate()
                    raise(retval)
                yield worker
            time.sleep(self.waittime)

    def join(self):
        if self._backlog:
            self._backlog.join()
        for workerid in range(self.workerid):
            while workerid not in self._returns:
                list(self.joinnext())
