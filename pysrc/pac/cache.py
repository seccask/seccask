from typing import Callable, List, Tuple
import numpy as np
import vartypes as vt
from vsm import VSM
from history import History


class BaseCache:
    def __init__(self, worker_set_size: int) -> None:
        self._worker_set: List[Tuple[vt.Component, vt.Version]] = []
        self._num_cold_start = 0
        self._worker_set_size = worker_set_size

    @property
    def num_cold_start(self):
        return self._num_cold_start

    @property
    def worker_set(self):
        return self._worker_set


class LRUCache(BaseCache):
    def __init__(self, worker_set_size: int) -> None:
        super().__init__(worker_set_size)

    def get(self, component: int, version: vt.Version) -> bool:
        for w in self._worker_set:
            f, v = w
            if f == component and v == version:
                self._worker_set.remove(w)
                self._worker_set.append(w)
                return True

        self._num_cold_start += 1

        if len(self._worker_set) > self._worker_set_size:
            self._worker_set.pop(0)

        self._worker_set.append((component, version))
        return False


class LFUCache(BaseCache):
    def __init__(self, worker_set_size: int) -> None:
        super().__init__(worker_set_size)
        self._frequency_table: List[int] = []
        self._time: List[int] = []

    def get(self, component: int, version: vt.Version) -> bool:
        self._time = list(map(lambda x: x + 1, self._time))

        for i, w in enumerate(self._worker_set):
            f, v = w
            if f == component and v == version:
                self._frequency_table[i] += 1
                return True

        self._num_cold_start += 1

        if len(self._worker_set) > self._worker_set_size:
            i_min, freq_min = -1, 9999
            for i, freq in enumerate(self._frequency_table):
                if freq / self._time[i] <= freq_min:
                    i_min = i
                    freq_min = freq / self._time[i]
            # print(i_min, freq_min)
            self._worker_set.pop(i_min)
            self._frequency_table.pop(i_min)
            self._time.pop(i_min)

        self._worker_set.append((component, version))
        self._frequency_table.append(1)
        self._time.append(1)

        return False


class FIFOCache(BaseCache):
    def __init__(self, worker_set_size: int) -> None:
        super().__init__(worker_set_size)

    def get(self, component: int, version: vt.Version) -> bool:
        for w in self._worker_set:
            f, v = w
            if f == component and v == version:
                return True

        self._num_cold_start += 1

        if len(self._worker_set) > self._worker_set_size:
            self._worker_set.pop(0)

        self._worker_set.append((component, version))
        return False


class PACache(BaseCache):
    """Pipeline-aware Caching

    IPA = Intra-pipeline Allocation
    """

    def __init__(
        self, worker_set_size: int, history_capacity: int, alpha: float
    ) -> None:
        super().__init__(worker_set_size)
        self._history = History(capacity=history_capacity)
        self._alpha = alpha
        self._vsms = self._generate_score_matrices()

    def _generate_score_matrices(self) -> List[VSM]:
        vsms = []
        for i in range(vt.NUM_PIPELINE_LENGTH):
            vsms.append(VSM(component_id=i, alpha=self._alpha))
        return vsms

    def get(self, component: int, version: vt.Version) -> bool:
        for w in self._worker_set:
            f, v = w
            if f == component and v == version:
                return True

        self._num_cold_start += 1
        if len(self._worker_set) > self._worker_set_size:
            w = self._least_possible_worker()
            self._worker_set.remove(w)

        self._worker_set.append((component, version))

        return False

    def _least_possible_worker(self):
        pipeline_length = vt.NUM_PIPELINE_LENGTH

        ids = []
        for vsm in self._vsms:
            argsort_f = np.unravel_index(
                np.argsort(vsm.value, axis=None), vsm.value.shape
            )
            ids.append(argsort_f)

        pointers = [0] * pipeline_length
        num_workers = [0] * pipeline_length
        for w in self._worker_set:
            f, v = w
            num_workers[f] += 1

        while True:
            values = [
                self._vsms[f][ids[f][0][pointers[f]], ids[f][1][pointers[f]]]
                for f in range(pipeline_length)
            ]
            for i in range(pipeline_length):
                if num_workers[i] == 0:
                    # invalidate the comparison of non-existing component
                    values[i] = 9999

            f_min = values.index(min(values))
            i_min = pointers[f_min]

            min_value_version = (
                ids[f_min][0][i_min],
                ids[f_min][1][i_min],
            )

            for w in self._worker_set:
                f, v = w
                if f == f_min and v == min_value_version:
                    return f, v

            pointers[f_min] += 1

    def update(
        self, transformer: Callable[[List[VSM], History], List[VSM]],
    ):
        self._vsms = transformer(self._vsms, self._history)
