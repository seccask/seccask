import itertools
import os
from typing import List
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def single_img(base_dir: str, start, end):
    lru_table = np.zeros((1, 1))

    for i in range(start, end):
        # plot the data
        fig = plt.figure(dpi=240)
        ax = fig.add_subplot(1, 1, 1)

        for j in range(start, end):
            filename = os.path.join(base_dir, f"slonly-h{j}w{i}.csv")
            df = pd.read_csv(filename).to_numpy()
            ax.plot(df[:, 0], df[:, 1], label=f"PAC:HistorySize={j}")
            ax.legend(loc=1, prop={"size": 6})
            lru_table = df[:, 0]

        filename = os.path.join(base_dir, f"lru-h1w{i}.csv")
        df = pd.read_csv(filename).to_numpy()
        lru_miss = np.repeat(df[0, 1], len(lru_table))[:, np.newaxis]
        lru_table = lru_table[:, np.newaxis]
        lru_table = np.concatenate((lru_table, lru_miss), axis=1)
        ax.plot(lru_table[:, 0], lru_table[:, 1], "--", label="LRU")
        ax.legend(loc=1, prop={"size": 6})

        plt.grid(True, ls="--", color="lightgray")
        plt.xlim(0.0, 0.6)
        plt.ylim(0, 4500)

        # display the plot
        # plt.show()

        plt.savefig(f"h{i}.png")
        plt.clf()
        plt.cla()
        plt.close()


def multi_img(base_dirs: List[str], prefixes: List[str], start, end):
    print(f"WS,LRU,LFU,FIFO")

    num_row = 1
    num_figure_per_row = 6

    start_history_size = 4
    end_history_size = 14

    params = {
        "font.size": 18,
        "xtick.labelsize": 18,
        "ytick.labelsize": 18,
        "axes.titlesize": 18,
    }
    plt.rcParams.update(params)

    lru_table = np.zeros((1, 1))

    total_fig = plt.figure(dpi=240)
    total_fig.set_figwidth(7.5 * num_figure_per_row)
    total_fig.set_figheight(5.5 * num_row * len(prefixes) + 0.5)

    titles = ["SLOnly", "ULOnly", "SL+UL"]

    bp = list(zip(base_dirs, prefixes))

    subfigs = total_fig.subfigures(nrows=len(prefixes), ncols=1)
    for row, subfig in enumerate(subfigs):
        axes = subfig.subplots(nrows=1, ncols=num_figure_per_row)

        subfig.suptitle(titles[row])

        base_dir, prefix = bp[row]

        plt.subplots_adjust(hspace=0.3, wspace=0.3)

        for i in range(start, end):
            if num_row == 1:
                id = (i - start) % num_figure_per_row
            else:
                id = (
                    (i - start) // num_figure_per_row,
                    (i - start) % num_figure_per_row,
                )

            ws_min = 9999

            for j in range(start_history_size, end_history_size):
                filename = os.path.join(base_dir, f"{prefix}-h{j}w{i}.csv")
                df = pd.read_csv(filename).to_numpy()
                # axes[id].set(aspect=1.0)
                axes[id].plot(df[:, 0], df[:, 1], label=f"PAC::HistorySize={j}")
                lru_table = df[:, 0]
                lfu_table = df[:, 0]
                fifo_table = df[:, 0]

                min = df[:, 1].min()
                if ws_min > min:
                    ws_min = min

            ### LRU
            filename = os.path.join(base_dir, f"lru-h1w{i}.csv")
            df = pd.read_csv(filename).to_numpy()

            lru_min = df[0, 1]
            print(f"{i},{(lru_min - ws_min) / lru_min * 100}", end="")

            lru_miss = np.repeat(df[0, 1], len(lru_table))[:, np.newaxis]
            lru_table = lru_table[:, np.newaxis]
            lru_table = np.concatenate((lru_table, lru_miss), axis=1)

            axes[id].plot(lru_table[:, 0], lru_table[:, 1], "--", label="LRU")

            ### LFU
            filename = os.path.join(base_dir, f"lfu-h1w{i}.csv")
            df = pd.read_csv(filename).to_numpy()

            lfu_min = df[0, 1]
            print(f",{(lfu_min - ws_min) / lfu_min * 100}", end="")

            lfu_miss = np.repeat(df[0, 1], len(lfu_table))[:, np.newaxis]
            lfu_table = lfu_table[:, np.newaxis]
            lfu_table = np.concatenate((lfu_table, lfu_miss), axis=1)

            axes[id].plot(lfu_table[:, 0], lfu_table[:, 1], "--", label="LFU")

            ### FIFO
            filename = os.path.join(base_dir, f"fifo-h1w{i}.csv")
            df = pd.read_csv(filename).to_numpy()

            fifo_min = df[0, 1]
            print(f",{(fifo_min - ws_min) / fifo_min * 100}")

            fifo_miss = np.repeat(df[0, 1], len(fifo_table))[:, np.newaxis]
            fifo_table = fifo_table[:, np.newaxis]
            fifo_table = np.concatenate((fifo_table, fifo_miss), axis=1)

            axes[id].plot(fifo_table[:, 0], fifo_table[:, 1], "--", label="FIFO")

            ### Figure config
            axes[id].grid(True, ls="--", color="lightgray")
            axes[id].set_xlim(0.0, 0.6)
            axes[id].set_ylim(0, 4500)
            axes[id].set_xlabel("PAC::\u03B1")
            axes[id].set_ylabel("Cache Miss / Cold Start No.")
            axes[id].title.set_text(f"WorkerSet={i}")

    def flip(items, ncol):
        return itertools.chain(*[items[i::ncol] for i in range(ncol)])

    handles, labels = plt.gca().get_legend_handles_labels()
    total_fig.legend(
        flip(handles, 5),
        flip(labels, 5),
        bbox_to_anchor=(0.5, 1),
        loc="lower center",
        bbox_transform=plt.gcf().transFigure,
        ncol=5,
    )

    print()

    # display the plot
    # plt.show()

    plt.savefig(os.path.join(f"plot_all.pdf"), bbox_inches="tight")
    # total_fig.clf()
    # total_fig.cla()
    plt.close()


if __name__ == "__main__":
    multi_img(
        base_dirs=["r0.8i200_slonly", "r0.8i200_ulonly", "r0.8i200_slul"],
        prefixes=["slonly", "ulonly", "slul"],
        start=8,
        end=14,
    )
