from abc import ABCMeta, abstractmethod

from pipeman.config import default_config


__all__ = ["mem_profiler"]

IS_ENABLED = default_config.getboolean("profiler", "enable_memory_profiler")


class MemoryProfiler(metaclass=ABCMeta):
    @abstractmethod
    def profile(self) -> None:
        pass


class EmptyMemoryProfiler(MemoryProfiler):
    def profile(self) -> None:
        pass


class MemoryProfilerImpl(MemoryProfiler):
    def __init__(self) -> None:
        super().__init__()
        self._mode = default_config.get("profiler", "memory_profiler_mode")

    def profile_from_status(self):
        with open("/proc/self/status", "r") as f:
            stat = f.read()
        return stat

    def profile_from_statm(self):
        from resource import getpagesize

        def get_resident_set_size_kb(statm) -> int:
            # statm columns are: size resident shared text lib data dt
            fields = statm.split()
            return int(fields[1]) * getpagesize() // 1024

        with open("/proc/self/statm", "r") as f:
            stat = f.read()
        return get_resident_set_size_kb(stat)

    def profile_from_resource_getrusage(self):
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    def profile(self):
        if self._mode == "status":
            print(self.profile_from_status())
        elif self._mode == "statm":
            print(f"VmRSS: {self.profile_from_statm()}")
        elif self._mode == "resource.getrusage":
            print(f"Peak Memory Usage: {self.profile_from_resource_getrusage()}")
        else:
            raise ValueError("Invalid memory profiler mode")


mem_profiler: MemoryProfiler = (
    MemoryProfilerImpl() if IS_ENABLED else EmptyMemoryProfiler()
)
