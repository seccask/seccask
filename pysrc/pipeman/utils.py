import asyncio
import collections
import json
import logging
import re
import sys
import time
from typing import Dict, Callable, Union

log_store = collections.deque(maxlen=100)
log_queue = asyncio.Queue()


def first(iterable, condition: Callable[..., bool] = lambda _: True, default=None):
    """
    Returns the first item in the `iterable` that
    satisfies the `condition`.

    If the condition is not given, returns the first item of
    the iterable.

    If the `default` argument is given and the iterable is empty,
    or if it has no items matching the condition, the `default` argument
    is returned if it matches the condition.

    The `default` argument being None is the same as it not being given.

    Raises `StopIteration` if no item satisfying the condition is found
    and default is not given or doesn't satisfy the condition.

    >>> first( (1,2,3), condition=lambda x: x % 2 == 0)
    2
    >>> first(range(3, 100))
    3
    >>> first( () )
    Traceback (most recent call last):
    ...
    StopIteration
    >>> first([], default=1)
    1
    >>> first([], default=1, condition=lambda x: x % 2 == 0)
    Traceback (most recent call last):
    ...
    StopIteration
    >>> first([1,3,5], default=1, condition=lambda x: x % 2 == 0)
    Traceback (most recent call last):
    ...
    StopIteration
    
    Source: https://stackoverflow.com/a/35513376
    """

    try:
        return next(x for x in iterable if condition(x))
    except StopIteration:
        if default is not None and condition(default):
            return default
        else:
            raise


def notify(queue: asyncio.Queue) -> None:
    try:
        queue.put_nowait(True)
    except:
        pass


class JsonableObject:
    def to_json(self):
        return json.dumps(self, sort_keys=True, default=vars)


class PrintUtils:
    @staticmethod
    def format(x: Union[list, dict]):
        return json.dumps(x, indent=4, default=str)


class StringUtils:
    REGEX_REMOVE_COLOR_ANSI_ESCAPE = r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]"

    @staticmethod
    def remove_ansi_color_escape(text: str) -> str:
        """Remove all ANSI color escapes"""
        re_remove_ansi_escape = re.compile(StringUtils.REGEX_REMOVE_COLOR_ANSI_ESCAPE)
        return re_remove_ansi_escape.sub("", text)


class LogStoreHandler(logging.Handler):
    def emit(self, record):
        current_time = time.time()
        log_store.append(
            {
                "id": current_time,
                "time": int(current_time * 1000),
                "level": record.levelname,
                "module": record.name,
                "msg": StringUtils.remove_ansi_color_escape(record.message),
            }
        )
        log_queue.put_nowait(
            {
                "id": current_time,
                "time": int(current_time * 1000),
                "level": record.levelname,
                "module": record.name,
                "msg": StringUtils.remove_ansi_color_escape(record.message),
            }
        )


class LogUtils:
    loggers_lut: Dict[str, logging.Logger] = dict()

    @classmethod
    def get_default_named_logger(cls, name: str) -> logging.Logger:
        if name in cls.loggers_lut:
            return cls.loggers_lut[name]
        else:
            default_log_level = logging.DEBUG
            default_log_formatter = logging.Formatter(
                fmt=f"%(asctime)-15s %(levelname)-7s | %(name)s |> %(message)s"
            )
            # default_log_formatter = logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            default_log_Handler = logging.StreamHandler(stream=sys.stdout)
            default_log_Handler.setFormatter(default_log_formatter)
            default_log_Handler.setLevel(default_log_level)
            # default_file_Handler = logging.FileHandler(filename=os.path.join(Env().home, time.strftime("%Y-%m-%d-%H-%M-%S.log", time.localtime())))
            # default_file_Handler.setFormatter(default_log_formatter)
            # default_file_Handler.setLevel(default_log_level)

            logger = logging.getLogger(name)
            logger.addHandler(default_log_Handler)

            handler = LogStoreHandler(level=default_log_level)
            logger.addHandler(handler)

            # logger.addFilter(LogUtils.LastPartFilter())

            # logger.addHandler(default_file_Handler)

            logger.setLevel(default_log_level)
            # logger.propagate = False
            cls.loggers_lut[name] = logger
            # print(f"Created logger for {name}")

        return logger
