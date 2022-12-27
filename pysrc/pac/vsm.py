"""VSM - Version Score Matrix

a 2D `version score matrix` (VSM) assigned to each component $f_j$ in a 
specific pipeline $p$. $\vb{S}_j$ covers *all* possible versions for 
component $f_j$, including those may not be legal (i.e. a version which 
does not exist in the system). Each element $s_{mn}^{j}$ in $\vb{S}_j$ 
denotes the probability that the next occurrence of $f$ in a new 
user-submitted pipeline has version $<m.n>$.
"""
from typing import Set, List
import numpy as np
import vartypes as vt
from vsm import VSM
from history import History

MAX_MAJOR_VERSION = 3
MAX_MINOR_VERSION = 3
DEFAULT_ALPHA = 0.2


class VSM:
    def __init__(
        self,
        component_id: vt.Component,
        major_size: vt.Major = MAX_MAJOR_VERSION + 1,
        minor_size: vt.Minor = MAX_MINOR_VERSION + 1,
        alpha: float = DEFAULT_ALPHA,
    ) -> None:
        self._alpha = alpha
        s = np.ones((major_size, minor_size), dtype=np.float64)
        s /= s.shape[0] * s.shape[1]  # ensure grand sum = 1
        self._data = s
        self._component_id = component_id

    @staticmethod
    def get_all_version_set():
        result = set()
        for i in range(MAX_MAJOR_VERSION + 1):
            for j in range(MAX_MINOR_VERSION + 1):
                result.add((i, j))
        return result

    @property
    def value(self):
        return self._data

    def __getitem__(self, v: vt.Version) -> float:
        return self._data[v[0], v[1]]

    @property
    def snapshot(self):
        return self._snapshot

    def take_snapshot(self) -> None:
        self._snapshot = self._data.copy()

    def scale_entry(self, v: vt.Version) -> None:
        """
        Args:
            v (Version): Version to be scaled
            
        Returns:
            None
        """
        e_mn = np.zeros(self._data.shape)
        e_mn[v[0], v[1]] = 1
        self._data = (1 - self._alpha) * self._data + self._alpha * e_mn

    def scale_batch(self, v: Set[vt.Version]) -> None:
        """
        Args:
            v (Set[Version]): A set of versions to be scaled
            
        Returns:
            None
        """
        if len(v) <= 0:
            return

        e_mn = np.zeros(self._data.shape)
        for (m, n) in v:
            e_mn[m, n] = 1
        self._data = (1 - self._alpha) * self._data + self._alpha * e_mn / len(v)


def vsm_transform_sl(last_vsms: List[VSM], history: History) -> List[VSM]:
    if history.size <= 1:
        return last_vsms

    # pprint(history.value)

    last_history_id = history.size - 1
    p = history[last_history_id]
    for k in range(p.size):
        f_1, (m_1, n_1) = p[k]
        V_c = set()
        for i in range(last_history_id):
            _, (m_2, n_2) = history[i][f_1]
            if m_1 != m_2 or n_1 != n_2:
                V_c.add((m_2, n_2))

        # print(k)
        # pprint(last_vsms[f_1].value)
        # time.sleep(1)

        last_vsms[f_1].scale_batch(VSM.get_all_version_set().difference(V_c))
    return last_vsms


def vsm_transform_ul(last_vsms: List[VSM], history: History) -> List[VSM]:
    if history.size <= 2:
        return last_vsms

    last_history_id = history.size - 1
    p_t = history[last_history_id]
    p_t_m_1 = history[last_history_id - 1]

    for k in range(p_t.size):
        (f_1, (m_1, n_1)), (f_2, (m_2, n_2)) = p_t[k], p_t_m_1[k]

        if (m_1 == m_2 and n_1 != n_2) or (m_1 != m_2 and n_1 == n_2):
            for f_i, (m_i, n_i) in [p_t[i] for i in range(0, k - 1)]:
                last_vsms[f_i].scale_batch(
                    VSM.get_all_version_set().difference(set([(m_i, n_i)]))
                )

            if m_1 != m_2 and n_1 == n_2:
                if 0 <= (2 * n_2 - n_1) <= MAX_MINOR_VERSION:
                    last_vsms[f_1].scale_entry((m_1, 2 * n_2 - n_1))

            if m_1 == m_2 and n_1 != n_2:
                if 0 <= (2 * m_2 - m_1) <= MAX_MAJOR_VERSION:
                    last_vsms[f_1].scale_entry((2 * m_2 - m_1, n_1))

    return last_vsms
