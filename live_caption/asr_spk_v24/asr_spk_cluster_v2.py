"""asr_spk_cluster_v2.py — diart-style incremental speaker clustering (reviewer, 2026-11-07).

Why (failure seen on SPE mix 3303-3603 s):
  v1 = cosine thr 0.35 + centroid EMA alpha 0.5.  A segment containing the end of a
  woman's question + the start of a man's answer matched the woman's cluster at 0.38,
  moved its centroid half-way to the man, the next male segment matched at 0.40 and
  moved it again => one label ("S2") ended up covering two people.  The same woman
  was also split into S1/S2 because S1's first centroid came from 2.5 s only.

What v2 does (ideas from diart, Coria et al. 2021 — delta_new / rho_update):
  * centroid = normalised SUM of unit embeddings weighted by clean speech seconds
    => a speaker's identity is the accumulated evidence, not the last two segments;
  * update only when the segment is HOMOGENEOUS (no speaker change inside, judged by
    the caller from sub-window embeddings) and the match is confident (>= rho_update);
  * gray zone: delta_new <= sim < rho_update => label = best match, NO update;
  * new speaker only if sim < delta_new AND the segment is homogeneous and long enough;
    otherwise gray-assign (never create speakers from mixed / short audio);
  * merge: a young cluster (< young_s of evidence) that becomes very similar to an
    older one (>= merge_sim) is merged into it; its label is aliased to the old one.
"""
from __future__ import annotations

import numpy as np


class DiartStyleCluster:
    def __init__(self, delta_new: float = 0.30, rho_update: float = 0.55,
                 merge_sim: float = 0.70, young_s: float = 8.0,
                 min_new_s: float = 2.0, max_speakers: int = 6):
        self.delta_new = float(delta_new)
        self.rho_update = float(rho_update)
        self.merge_sim = float(merge_sim)
        self.young_s = float(young_s)
        self.min_new_s = float(min_new_s)
        self.max_speakers = int(max_speakers)
        self._sum = []          # weighted sums of unit vectors
        self._w = []            # accumulated weight (clean seconds)
        self._ids = []          # label number for each live cluster
        self._next = 1
        self.alias = {}         # merged label -> surviving label
        self.n_overflow = 0
        self.n_gray = 0
        self.n_mixed = 0
        self.n_merge = 0

    # v1-compatible attribute used by stats()
    @property
    def centroids(self):
        return [self._unit(s) for s in self._sum]

    @staticmethod
    def _unit(v):
        v = np.asarray(v, dtype=np.float64).reshape(-1)
        n = float(np.linalg.norm(v))
        return v / n if n > 1e-9 else v

    def _label(self, k: int) -> str:
        return 'S%d' % self._ids[k]

    def _new(self, u, weight):
        self._sum.append(u * weight)
        self._w.append(weight)
        self._ids.append(self._next)
        self._next += 1
        return len(self._sum) - 1

    def _merge_pass(self):
        changed = True
        while changed and len(self._sum) > 1:
            changed = False
            C = [self._unit(s) for s in self._sum]
            best = None
            for i in range(len(C)):
                for j in range(len(C)):
                    if i == j:
                        continue
                    # j = young cluster merged into i (older / heavier)
                    if self._w[j] >= self.young_s or self._w[j] > self._w[i]:
                        continue
                    s = float(np.dot(C[i], C[j]))
                    if s >= self.merge_sim and (best is None or s > best[0]):
                        best = (s, i, j)
            if best:
                _s, i, j = best
                self._sum[i] = self._sum[i] + self._sum[j]
                self._w[i] += self._w[j]
                self.alias['S%d' % self._ids[j]] = 'S%d' % self._ids[i]
                for a, b in list(self.alias.items()):
                    if b == 'S%d' % self._ids[j]:
                        self.alias[a] = 'S%d' % self._ids[i]
                del self._sum[j], self._w[j], self._ids[j]
                self.n_merge += 1
                changed = True

    def resolve(self, label):
        """Current label for an older label (after merges)."""
        while label in self.alias:
            label = self.alias[label]
        return label

    def assign(self, x_raw, *, homogeneous: bool = True, weight: float = 1.0):
        """Return (label, sim, action).  `weight` = clean speech seconds of the segment."""
        u = self._unit(x_raw)
        weight = max(0.1, float(weight))
        if not self._sum:
            if not homogeneous:
                self.n_mixed += 1
            k = self._new(u, weight)
            return self._label(k), 1.0, 'init'
        C = [self._unit(s) for s in self._sum]
        sims = np.array([float(np.dot(u, c)) for c in C])
        k = int(np.argmax(sims))
        s = float(sims[k])
        if not homogeneous:
            self.n_mixed += 1
            return self._label(k), s, 'mixed_no_update'
        if s >= self.rho_update:
            self._sum[k] = self._sum[k] + u * weight
            self._w[k] += weight
            lab = self._label(k)
            self._merge_pass()
            return self.resolve(lab), s, 'update'
        if s >= self.delta_new or weight < self.min_new_s:
            self.n_gray += 1
            return self._label(k), s, 'gray_no_update'
        if len(self._sum) < self.max_speakers:
            k2 = self._new(u, weight)
            return self._label(k2), s, 'new_speaker'
        self.n_overflow += 1
        return self._label(k), s, 'overflow_no_update'
