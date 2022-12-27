from typing import List, Tuple, Union
import numpy as np
import vartypes as vt


class Pipeline:
    @staticmethod
    def from_version_list(p: List[vt.Version]) -> "Pipeline":
        return Pipeline(np.array(p, dtype=np.int32).transpose())

    def __init__(self, data: np.ndarray) -> None:
        self._data = data

    @property
    def array(self):
        return self._data[:, :, np.newaxis]

    @property
    def size(self):
        return self._data.shape[1]

    def __getitem__(self, key: int) -> Tuple[vt.Component, vt.Version]:
        return key, (self._data[0, key], self._data[1, key])

    def __iter__(self):
        self.n = 0
        return self

    def __next__(self):
        if self.n < self.size:
            self.n += 1
            return self[self.n - 1]
        else:
            raise StopIteration


class History:
    def __init__(self, capacity: int) -> None:
        self._data = -np.ones((2, vt.NUM_PIPELINE_LENGTH, 1), dtype=np.int32)
        self._capacity = capacity

    @property
    def value(self):
        return self._data[:, :, 1:]

    @property
    def size(self):
        return self._data.shape[2] - 1

    def __getitem__(self, key: int) -> Pipeline:
        return Pipeline(data=self._data[:, :, key + 1])

    def append(self, pipeline: Union[Pipeline, np.ndarray]) -> None:
        """
        Args:
            pipeline (Union[Pipeline, np.ndarray]): A `(2, pipeline_length)` sized `int32` numpy array
        
        Returns:
            None
        """
        if isinstance(pipeline, Pipeline):
            history = np.concatenate((self._data, pipeline.array), axis=2)
        else:
            history = np.concatenate((self._data, pipeline[:, :, np.newaxis]), axis=2)

        # time.sleep(1)
        # pprint(history)

        if history.shape[2] > self._capacity:
            history = np.delete(history, 1, 2)

        self._data = history
