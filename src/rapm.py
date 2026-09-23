"""Regularized adjusted plus-minus.

The idea is old and simple. Every stint is an observation of ten players and a
result. Regress the result on who was out there and the coefficients are each
player's effect, adjusted for everyone else on the floor.

Done as plain least squares this is adjusted plus-minus, and it does not work.
Teammates share almost all of their minutes, so the design matrix is close to
singular and the fit answers with enormous, unstable, obviously wrong numbers -
a backup center with 300 possessions ends up at plus forty per hundred because
he happened to share them with a good starting five. The problem is not the idea.
It is that the data cannot separate players who are never apart, and least
squares does not know that it is guessing.

Ridge fixes it by refusing to make a large claim without a large amount of
evidence. The penalty pulls every coefficient toward zero, and pulls hardest on
exactly the players the data cannot pin down. The penalty strength is not a taste
parameter - it is chosen by cross-validation on held-out games, and
`run_02_rapm.py` shows the curve.

Two columns per player: one for what happens when he is on offense, one for when
he is on defense. Defensive coefficients are reported with the sign flipped so
that positive is good on both sides.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse


def parse_lineups(col: pd.Series) -> np.ndarray:
    """'(1, 2, 3, 4, 5)' -> an (n, 5) integer array, without literal_eval."""
    stripped = col.str.strip("()")
    return np.array([[int(v) for v in s.split(",")] for s in stripped], dtype=np.int64)


class Design:
    """Sparse design matrix plus the bookkeeping to read coefficients back."""

    def __init__(self, stints: pd.DataFrame):
        off = parse_lineups(stints["off_lineup"])
        dfn = parse_lineups(stints["def_lineup"])
        self.players = np.unique(np.concatenate([off.ravel(), dfn.ravel()]))
        self.index = {p: i for i, p in enumerate(self.players)}
        n_p = len(self.players)

        lookup = np.full(self.players.max() + 1, -1, dtype=np.int64)
        lookup[self.players] = np.arange(n_p)
        oi, di = lookup[off], lookup[dfn]

        n = len(stints)
        rows = np.repeat(np.arange(n), 10)
        cols = np.concatenate([oi, di + n_p], axis=1).ravel()
        data = np.ones(len(rows))

        home = sparse.csr_matrix(stints["off_home"].to_numpy(dtype=float).reshape(-1, 1))
        body = sparse.csr_matrix((data, (rows, cols)), shape=(n, 2 * n_p))

        # An unpenalised effect per season and an intercept. The intercept is
        # what makes shrinkage mean the right thing: a penalised coefficient is
        # pulled toward league average, not toward zero points per 100. The
        # season effects keep the league's scoring level out of the player
        # coefficients, which matters over thirteen seasons in which it moved.
        self.seasons = pd.Index(sorted(stints["season"].unique()))
        sidx = self.seasons.get_indexer(stints["season"])
        season_block = sparse.csr_matrix((np.ones(n), (np.arange(n), sidx)),
                                         shape=(n, len(self.seasons)))
        ones = sparse.csr_matrix(np.ones((n, 1)))
        self.X = sparse.hstack([body, home, season_block, ones], format="csr")
        self.n_seasons = len(self.seasons)

        self.poss = stints["poss"].to_numpy(dtype=float)
        self.y = 100.0 * stints["pts"].to_numpy(dtype=float) / self.poss
        self.games = stints["game_id"].to_numpy()
        self.n_players = n_p

    def coefficients(self, beta: np.ndarray) -> pd.DataFrame:
        n_p = self.n_players
        return pd.DataFrame({
            "player_id": self.players,
            "o_rapm": beta[:n_p],
            "d_rapm": -beta[n_p:2 * n_p],   # sign flipped: positive is good defence
        }).assign(rapm=lambda d: d["o_rapm"] + d["d_rapm"])

    def possessions_by_player(self) -> pd.Series:
        n_p = self.n_players
        counts = self.X[:, :2 * n_p].T @ self.poss
        return pd.Series(counts[:n_p] + counts[n_p:], index=self.players, name="poss")

    def penalty(self) -> np.ndarray:
        """Per-column penalty multipliers: the players, and nothing else."""
        return np.r_[np.ones(2 * self.n_players), np.zeros(1),
                     np.zeros(self.n_seasons), np.zeros(1)]


class TeamDesign(Design):
    """The same design with a defensive effect per team-season on the end.

    Adding it turns the model into a question about attribution. A team-season
    effect is nearly collinear with the defensive coefficients of the players who
    filled that roster, so the split between them is decided by which block
    carries the ridge penalty rather than by the data.

    `penalty(team_alpha)` is therefore the whole interface. A huge value removes
    the team block; 1.0 shrinks it exactly as hard as the players; a token 1e-6
    lets it take everything the players do not insist on. The last of those is
    not zero on purpose: the team dummies sum to the intercept, so with no
    penalty at all the normal equations are exactly singular.

    `run_03_system.py` reports all three. The two ends bracket the answer, and
    nothing in between is estimable from this data.
    """

    def __init__(self, stints: pd.DataFrame):
        super().__init__(stints)
        key = (stints["def_team"].astype("int64").astype(str) + "_"
               + stints["season"].astype(str))
        self.team_seasons = pd.Index(sorted(key.unique()))
        idx = self.team_seasons.get_indexer(key)
        n = len(stints)
        block = sparse.csr_matrix((np.ones(n), (np.arange(n), idx)),
                                  shape=(n, len(self.team_seasons)))
        self.n_base = self.X.shape[1]
        self.X = sparse.hstack([self.X, block], format="csr")
        self.n_team_seasons = len(self.team_seasons)

    def penalty(self, team_alpha: float = 1e-6) -> np.ndarray:
        return np.r_[super().penalty(), np.full(self.n_team_seasons, team_alpha)]

    def team_effects(self, beta: np.ndarray) -> pd.DataFrame:
        keys = [k.split("_") for k in self.team_seasons]
        return pd.DataFrame({
            "team_id": [int(a) for a, _ in keys],
            "season": [int(b) for _, b in keys],
            # sign flipped so that positive is good defence, as everywhere else
            "team_d": -beta[self.n_base:self.n_base + self.n_team_seasons],
        })


def partial_ridge(X, y, w, penalised: np.ndarray, alpha: float) -> np.ndarray:
    """Ridge on some coefficients and plain least squares on the rest.

    scikit-learn penalises every column the same way, which is not what this
    model wants. The normal equations take a diagonal penalty instead, and at
    a few thousand columns they are cheap to solve directly.
    """
    W = sparse.diags(w)
    xtx = (X.T @ W @ X).toarray()
    xty = np.asarray(X.T @ (w * y)).ravel()
    xtx[np.diag_indices_from(xtx)] += alpha * penalised + 1e-8
    return np.linalg.solve(xtx, xty)


def fit(design: Design, alpha: float, rows: np.ndarray | None = None,
        penalty: np.ndarray | None = None) -> np.ndarray:
    X = design.X if rows is None else design.X[rows]
    y = design.y if rows is None else design.y[rows]
    w = design.poss if rows is None else design.poss[rows]
    pen = design.penalty() if penalty is None else penalty
    return partial_ridge(X, y, w, pen, alpha)


def weighted_mse(design: Design, beta, rows: np.ndarray) -> float:
    err = design.y[rows] - design.X[rows] @ beta
    w = design.poss[rows]
    return float((w * err ** 2).sum() / w.sum())


def game_folds(design: Design, n_folds: int, seed: int) -> np.ndarray:
    """Fold assignment by game, so a stint is never scored by a model that saw
    its own game and the two sides of a stint never land on opposite sides."""
    rng = np.random.default_rng(seed)
    games = np.unique(design.games)
    fold_of_game = pd.Series(rng.integers(0, n_folds, len(games)), index=games)
    return fold_of_game.reindex(design.games).to_numpy()


def cross_validate(design: Design, alphas, n_folds: int = 5, seed: int = 0,
                   penalty: np.ndarray | None = None) -> pd.DataFrame:
    fold = game_folds(design, n_folds, seed)
    rows = []
    for alpha in alphas:
        errs = []
        for k in range(n_folds):
            tr = np.flatnonzero(fold != k)
            te = np.flatnonzero(fold == k)
            beta = fit(design, alpha, tr, penalty)
            errs.append(weighted_mse(design, beta, te))
        rows.append({"alpha": alpha, "cv_mse": float(np.mean(errs)),
                     "cv_sd": float(np.std(errs))})
    return pd.DataFrame(rows)
