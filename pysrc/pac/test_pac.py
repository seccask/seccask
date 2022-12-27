import os
from pprint import pprint

from pac.cache import *
from pac.history import *
from pac.vartypes import *
from pac.vsm import *


def test_submit_pipeline(max_history):
    h = History(capacity=max_history)
    h.append(np.ones((2, NUM_PIPELINE_LENGTH), dtype=np.int32))
    pprint(h.value.shape)
    pprint(h.value)
    h.append(2 * np.ones((2, NUM_PIPELINE_LENGTH), dtype=np.int32))
    pprint(h.value.shape)
    pprint(h.value)
    h.append(3 * np.ones((2, NUM_PIPELINE_LENGTH), dtype=np.int32))
    pprint(h.value.shape)
    pprint(h.value)


def test_vsm_scaling_entry():
    s = VSM(0, alpha=0.1)
    pprint(s)

    for i in range(5):
        s.scale_entry((i, i))
        pprint(s.value)


def test_vsm_scaling_batch():
    s = VSM(0, alpha=0.1)
    pprint(s)

    s.scale_batch(set([(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)]))
    pprint(s)


def get_test_workspace() -> List[List[Version]]:
    return [
        [(0, 0), (0, 0), (0, 0), (0, 0), (0, 0)],
        [(0, 0), (1, 0), (1, 0), (0, 0), (0, 1)],
        [(0, 1), (2, 0), (2, 0), (0, 1), (0, 0)],
        [(0, 1), (3, 0), (3, 0), (0, 1), (0, 1)],
        [(0, 0), (0, 0), (3, 0), (1, 0), (0, 0)],
        [(0, 0), (1, 0), (2, 0), (1, 0), (0, 1)],
        [(0, 1), (2, 0), (1, 0), (1, 1), (0, 0)],
        [(0, 1), (3, 0), (0, 0), (1, 1), (0, 1)],
    ]


def get_test_workspace_rand():
    np.random.seed(3407)
    return np.random.randint(4, size=(800, 5, 2)).tolist()


def test_vsm_transform(
    max_history, worker_set_size, iter, max_alpha, enable_sl, enable_ul
):
    def pipeline_iter(cache: PACache, pipeline: Pipeline):
        # p = np.array(pipeline, dtype=np.int32)
        # versions = list(zip(*p))
        # print(f"new pipeline: {versions}")
        for f, v in pipeline:
            # print(f, v)
            cache.get(f, v)

        # print(f"worker_set:")
        # pprint(pac.worker_set)

        cache._history.append(pipeline)
        if enable_sl:
            cache.update(vsm_transform_sl)
        if enable_ul:
            cache.update(vsm_transform_ul)

        # print(f"vsms:")
        # pprint(pac._vsms)

    result_table = []

    for i in range(iter):
        alpha = 1e-10 + max_alpha * (i / iter)
        alpha = float("{:.4f}".format(alpha))
        pac = PACache(
            worker_set_size=worker_set_size, history_capacity=max_history, alpha=alpha
        )
        for _ in range(1):
            for p in get_test_workspace_rand():
                pipeline_iter(pac, Pipeline.from_version_list(p))

        print(f"alpha: {alpha}, cache miss: {pac.num_cold_start}")
        result_table.append((alpha, pac.num_cold_start))

    return result_table


def test_traditional(cache_cls, worker_set_size):
    cache = cache_cls(worker_set_size=worker_set_size)

    def pipeline_iter(cache, pipeline: Pipeline):
        # p = np.array(pipeline, dtype=np.int32)
        # versions = list(zip(*p))
        # print(f"new pipeline: {versions}")
        for f, v in enumerate(pipeline):
            cache.get(f, v)  # type: ignore

    for _ in range(1):
        for p in get_test_workspace_rand():
            pipeline_iter(cache, Pipeline.from_version_list(p))

    print(f"cache miss: {cache.num_cold_start}")

    return cache.num_cold_start


def output_to_csv(
    data: List[Tuple[float, int]],
    prefix: str,
    worker_set_size,
    max_history=None,
    base_dir=".",
):
    import csv

    if not os.path.exists(base_dir):
        os.mkdir(base_dir)

    if max_history is not None:
        filename = f"{prefix}-h{max_history}w{worker_set_size}"
    else:
        filename = f"{prefix}-h1w{worker_set_size}"

    if base_dir is not None:
        filename = os.path.join(base_dir, f"{filename}.csv")
    else:
        filename = f"{filename}.csv"

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["alpha", "cache_miss"])
        writer.writerows(data)


if __name__ == "__main__":
    # worker_set_size = 8
    # max_history = 8
    # print(f"----- H{max_history}W{worker_set_size} -----")
    # print("=== PAC:ULOnly ===")
    # output_to_csv(
    #     test_vsm_transform(max_history=max_history, worker_set_size=worker_set_size),
    #     prefix="ulonly",
    #     base_dir=".",
    #     max_history=max_history,
    #     worker_set_size=worker_set_size,
    # )

    # sys.exit(0)

    configs = [
        {
            "prefix": "slonly",
            "base_dir": "rand_r0.8i200_slonly",
            "enable_sl": True,
            "enable_ul": False,
        },
        {
            "prefix": "ulonly",
            "base_dir": "rand_r0.8i200_ulonly",
            "enable_sl": False,
            "enable_ul": True,
        },
        {
            "prefix": "slul",
            "base_dir": "rand_r0.8i200_slul",
            "enable_sl": True,
            "enable_ul": True,
        },
    ]

    for config in configs:
        print(f"=== config: {config} ===")
        for i in range(4, 14):
            worker_set_size = i
            for j in range(4, 14):
                max_history = j

                print(f"----- H{max_history}W{worker_set_size} -----")
                print(f"=== PAC ===")
                output_to_csv(
                    test_vsm_transform(
                        max_history=max_history,
                        worker_set_size=worker_set_size,
                        iter=200,
                        max_alpha=0.8,
                        enable_sl=config["enable_sl"],
                        enable_ul=config["enable_ul"],
                    ),
                    prefix=config["prefix"],
                    base_dir=config["base_dir"],
                    max_history=max_history,
                    worker_set_size=worker_set_size,
                )

        for i in range(4, 14):
            worker_set_size = i

            print("=== LRU ===")
            output_to_csv(
                [
                    (
                        -1,
                        test_traditional(
                            cache_cls=LRUCache, worker_set_size=worker_set_size
                        ),
                    )
                ],
                prefix="lru",
                base_dir=config["base_dir"],
                worker_set_size=worker_set_size,
            )

            print("=== FIFO ===")
            output_to_csv(
                [
                    (
                        -1,
                        test_traditional(
                            cache_cls=FIFOCache, worker_set_size=worker_set_size
                        ),
                    )
                ],
                prefix="fifo",
                base_dir=config["base_dir"],
                worker_set_size=worker_set_size,
            )

            print("=== LFU ===")
            worker_set_size = i
            output_to_csv(
                [
                    (
                        -1,
                        test_traditional(
                            cache_cls=LFUCache, worker_set_size=worker_set_size
                        ),
                    )
                ],
                prefix="lfu",
                base_dir=config["base_dir"],
                worker_set_size=worker_set_size,
            )

    # UnitTest.test_vsm_scaling_batch()
    # UnitTest.test_vsm_scaling_entry()
    # UnitTest.test_submit_pipeline()
