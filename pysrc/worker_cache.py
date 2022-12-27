from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from typing import Iterator, Literal, Optional, TypeVar, Generic

from pipeman.utils import LogUtils

from pipeline import Component
import workerconn as wc


__all__ = ["LRUCache", "PACache"]

V = TypeVar("V")


class BaseCache(Generic[V], metaclass=ABCMeta):
    def __init__(self) -> None:
        super().__init__()
        self.logger = LogUtils.get_default_named_logger(type(self).__name__)

    @abstractmethod
    def get(self, key: str) -> Optional[V]:
        raise NotImplementedError

    def put(self, key: str, value: V) -> None:
        raise NotImplementedError

    def add(self, value: V) -> None:
        raise NotImplementedError

    def remove_end(self, component: Component) -> V:
        raise NotImplementedError

    def remove(self, value: V) -> None:
        raise NotImplementedError

    def __iter__(self) -> Iterator[V]:
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

    def __repr__(self):
        raise NotImplementedError

    def __str__(self):
        raise NotImplementedError


class LRUCache(BaseCache["wc.BaseWorkerConnection"]):
    # initialising capacity
    def __init__(self):
        super().__init__()
        self.cache = OrderedDict()

    # we return the value of the key
    # that is queried in O(1) and return -1 if we
    # don't find the key in out dict / cache.
    # And also move the key to the end
    # to show that it was recently used.
    def get(self, key: str) -> Optional["wc.BaseWorkerConnection"]:
        if key not in self.cache:
            return None
        else:
            self.cache.move_to_end(key)
            return self.cache[key]

    # first, we add / update the key by conventional methods.
    # And also move the key to the end to show that it was recently used.
    # But here we will also check whether the length of our
    # ordered dictionary has exceeded our capacity,
    # If so we remove the first key (least recently used)
    def put(self, value: "wc.BaseWorkerConnection") -> None:
        self.cache[value.id] = value
        self.cache.move_to_end(value.id)

    def add(self, value: "wc.BaseWorkerConnection") -> None:
        self.put(value)

    def remove_end(self, component: Component) -> "wc.BaseWorkerConnection":
        return self.cache.popitem(last=False)[1]

    def remove(self, value: "wc.BaseWorkerConnection") -> None:
        self.cache.pop(value.id)

    def __iter__(self) -> Iterator["wc.BaseWorkerConnection"]:
        return iter(self.cache.values())

    def __len__(self):
        return len(self.cache)

    def __repr__(self):
        return repr(self.cache.keys())

    def __str__(self):
        return str(self.cache.keys())


class PACache(BaseCache["wc.BaseWorkerConnection"]):
    def __init__(self, mode: Literal["normal", "aggressive"] = "normal") -> None:
        super().__init__()
        self._mode = mode
        self.cache: OrderedDict[str, "wc.BaseWorkerConnection"] = OrderedDict()

    def get(self, key: str) -> Optional["wc.BaseWorkerConnection"]:
        if key not in self.cache:
            return None
        else:
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, value: "wc.BaseWorkerConnection") -> None:
        self.cache[value.id] = value
        self.cache.move_to_end(value.id)

    def add(self, value: "wc.BaseWorkerConnection") -> None:
        self.put(value)

    def remove_end(self, component: Component) -> "wc.BaseWorkerConnection":
        for id, w in self.cache.items():
            if not w.manifest:
                continue
            self.logger.debug(
                f"{w.manifest.name}:{w.manifest.version.version_str} ==?== "
                + f"{component.get_manifest().name}:{component.get_manifest().version.version_str}"
            )
            if w.manifest.name == component.get_manifest().name:
                self.logger.debug(f"Select {w} to remove from submit locality")
                return self.cache.pop(id)

        self.logger.debug("Submit locality no effect")
        return self.cache.popitem(last=False)[1]

    def remove(self, value: "wc.BaseWorkerConnection") -> None:
        self.cache.pop(value.id)

    def __iter__(self) -> Iterator["wc.BaseWorkerConnection"]:
        return iter(self.cache.values())

    def __len__(self):
        return len(self.cache)

    def __repr__(self):
        return repr(self.cache.keys())

    def __str__(self):
        return str(self.cache.keys())
