"""Stage 3 - was there a Spurs defense, or only Spurs defenders?

    python src/run_03_system.py

The question everyone asks about that team is whether the whole was worth more
than the parts. It is answerable, but not in the way it is usually posed.

Adding a defensive effect per team-season to the RAPM design is easy. Getting a
number out of it that means something is not: a team-season effect is nearly
collinear with the defensive coefficients of the players who made up that roster,
so the split between them is decided by which block carries the ridge penalty
rather than by the data.

So the project does two things instead of one. First it asks a question the data
*can* answer - does knowing which team a lineup belonged to help predict what
happened, once you already know the five defenders? That is a held-out prediction
test and it comes back yes or no. Then, and only then, it reports the size of the
effect under both penalty conventions, which brackets it.

Writes output/system_cv.csv, output/team_defence.csv, output/spurs_system.csv,
output/player_bracket.csv and figures 04-05.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import FIG, OUT, PROC, RAW, SEASONS, SEED, SUBJECT, TEAM_ABBREV  # noqa: E402
import rapm as R  # noqa: E402
import style as S  # noqa: E402

S.apply()

N_FOLDS = 5


def season_label(season: int) -> str:
    return f"{season - 1}-{str(season)[2:]}"


def player_names() -> pd.Series:
    frames = []
    for s in SEASONS:
        b = pd.read_csv(RAW / "player_box" / f"player_box_{s}.csv.gz",
                        usecols=["athlete_id", "athlete_display_name"], low_memory=False)
        frames.append(b.dropna())
    p = pd.concat(frames).drop_duplicates("athlete_id")
    return p.set_index(p["athlete_id"].astype("int64"))["athlete_display_name"]


def load_stints() -> pd.DataFrame:
    return pd.concat([pd.read_csv(PROC / f"stints_{s}.csv.gz") for s in SEASONS],
                     ignore_index=True)


def team_map() -> pd.Series:
    frames = []
    for s in SEASONS:
        b = pd.read_csv(RAW / "player_box" / f"player_box_{s}.csv.gz",
                        usecols=["team_id", "team_abbreviation"], low_memory=False)
        frames.append(b.dropna())
    t = pd.concat(frames).drop_duplicates("team_id")
    return t.set_index(t["team_id"].astype("int64"))["team_abbreviation"]


def cv_model(design, penalised: np.ndarray, alpha: float,
             fold: np.ndarray) -> tuple[float, np.ndarray]:
    """Possession-weighted held-out error, folds split by game.

    The per-fold values come back too, because the differences between these
    models are small next to the noise in a single fold and the reader should be
    able to see whether the sign is the same in all five.
    """
    errs = []
    for k in range(N_FOLDS):
        tr = np.flatnonzero(fold != k)
        te = np.flatnonzero(fold == k)
        beta = R.partial_ridge(design.X[tr], design.y[tr], design.poss[tr],
                               penalised, alpha)
        err = design.y[te] - design.X[te] @ beta
        w = design.poss[te]
        errs.append(float((w * err ** 2).sum() / w.sum()))
    return float(np.mean(errs)), np.array(errs)


def fig_cv(cv: pd.DataFrame) -> None:
    d = cv.sort_values("cv_mse", ascending=False).reset_index(drop=True)
    base = d["cv_mse"].max()
    fig, ax = plt.subplots(figsize=(9.0, 3.9))
    ax.barh(d.index, base - d["cv_mse"], color=S.SILVER, height=0.5, zorder=2)
    for i, r in d.iterrows():
        ax.text(base - r["cv_mse"] + 0.02, i,
                f"{base - r['cv_mse']:+.2f}" if i else "reference",
                va="center", fontsize=9, color=S.INK_2)
    ax.set_yticks(d.index, d["model"])
    ax.set_ylim(-0.7, len(d) - 0.3)
    ax.set_xlim(-0.05, max(0.3, (base - d["cv_mse"]).max() * 1.5))
    ax.grid(axis="y", visible=False)
    S.strip(ax, keep=("bottom",))
    ax.tick_params(axis="y", labelsize=9.2)
    ax.set_xlabel("Reduction in held-out error against the players-only model")
    ax.set_title("Does knowing the team help, once you know the five defenders?",
                 loc="left")
    S.caption(fig, f"Five-fold cross-validation with folds split by game, over "
                   f"{season_label(SEASONS[0])} to {season_label(SEASONS[-1])}. The units are "
                   "squared points per 100 possessions, so the numbers are small by "
                   "construction; what matters is the sign and whether it is stable across "
                   "folds.")
    fig.tight_layout()
    fig.savefig(FIG / "04_system_cv.png")
    plt.close(fig)


def fig_team_defence(td: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9.6, 5.2))
    others = td[td["team"] != TEAM_ABBREV]
    ax.scatter(others["season"], others["team_d"], s=17, color=S.NEUTRAL,
               linewidths=0, zorder=2)
    sa = td[td["team"] == TEAM_ABBREV].sort_values("season")
    ax.plot(sa["season"], sa["team_d"], color=S.SPURS, lw=2.2, zorder=4)
    ax.scatter(sa["season"], sa["team_d"], s=32, color=S.SPURS, zorder=5,
               edgecolors=S.SURFACE, lw=1.2)
    ax.annotate("San Antonio", (sa["season"].iloc[-1], sa["team_d"].iloc[-1]),
                xytext=(8, 0), textcoords="offset points", va="center",
                fontsize=9.6, color=S.SPURS, fontweight="semibold")
    ax.axhline(0, color=S.INK_3, lw=0.9, zorder=3)
    S.strip(ax)
    ax.set_xlim(SEASONS[0] - 0.5, SEASONS[-1] + 3.4)
    ax.set_xticks(range(SEASONS[0], SEASONS[-1] + 1, 2),
                  [season_label(v) for v in range(SEASONS[0], SEASONS[-1] + 1, 2)])
    ax.tick_params(axis="x", labelsize=8.6)
    ax.set_ylabel("Team-season defensive effect,\npoints per 100 beyond the five on the floor")
    ax.set_title("What is left over when the players are already in the model", loc="left")
    S.caption(fig, "Every team-season, with the defensive effect estimated alongside penalized "
                   "player coefficients. Positive is good defense. This is the convention that "
                   "gives the team block as much of the credit as the data will allow, so these "
                   "are upper bounds on 'system' and should be read that way.")
    fig.tight_layout()
    fig.savefig(FIG / "05_team_defence.png")
    plt.close(fig)


def main() -> None:
    t0 = time.time()
    cv_curve = pd.read_csv(OUT / "cv_curve.csv")
    alpha = float(cv_curve.loc[cv_curve["cv_mse"].idxmin(), "alpha"])
    teams = team_map()

    stints = load_stints()
    design = R.TeamDesign(stints)
    fold = R.game_folds(design, N_FOLDS, SEED)
    n_p, n_ts = design.n_players, design.n_team_seasons
    print(f"{len(stints):,} stint-sides, {n_p:,} players, {n_ts} team-seasons, "
          f"penalty {alpha:,.0f}")

    # Three penalty conventions over the same design: teams effectively removed,
    # teams shrunk like players, teams free to take whatever the players leave.
    players_only = design.penalty(1e9)     # the team block removed
    teams_shrunk = design.penalty(1.0)     # shrunk exactly as hard as a player
    teams_free = design.penalty(1e-6)      # free to take whatever players leave

    rows, per_fold = [], {}
    for label, pen in (("Players only", players_only),
                       ("Players, plus team-season defense (shrunk)", teams_shrunk),
                       ("Players, plus team-season defense (free)", teams_free)):
        mse, folds_mse = cv_model(design, pen, alpha, fold)
        per_fold[label] = folds_mse
        rows.append({"model": label, "cv_mse": mse, "cv_sd": float(folds_mse.std())})
        print(f"  {label:44s} held-out MSE {mse:.3f}", flush=True)
    cv = pd.DataFrame(rows)
    cv["vs_players_only"] = cv.loc[0, "cv_mse"] - cv["cv_mse"]
    base = per_fold["Players only"]
    cv["folds_improved"] = [int((base - per_fold[m] > 0).sum()) for m in cv["model"]]
    cv.round(5).to_csv(OUT / "system_cv.csv", index=False)
    fig_cv(cv)

    # The bracket: team effects under both conventions.
    beta_free = R.partial_ridge(design.X, design.y, design.poss, teams_free, alpha)
    beta_shrunk = R.partial_ridge(design.X, design.y, design.poss, teams_shrunk, alpha)
    td = design.team_effects(beta_free).rename(columns={"team_d": "team_d_free"})
    td["team_d_shrunk"] = design.team_effects(beta_shrunk)["team_d"]
    td["team"] = td["team_id"].map(teams)
    td["rank_free"] = td.groupby("season")["team_d_free"].rank(ascending=False,
                                                              method="min")
    td = td.sort_values(["season", "team"])
    td.round(4).to_csv(OUT / "team_defence.csv", index=False)
    fig_team_defence(td.assign(team_d=td["team_d_free"]))

    sa = td[td["team"] == TEAM_ABBREV].sort_values("season")
    sa.round(4).to_csv(OUT / "spurs_system.csv", index=False)

    # The same bracket, seen from the player side: what happens to a defender's
    # own coefficient when the team block is allowed to take the credit.
    names = player_names()
    beta_players = R.partial_ridge(design.X, design.y, design.poss,
                                   players_only, alpha)
    who = design.coefficients(beta_players)[["player_id", "d_rapm"]]
    who = who.rename(columns={"d_rapm": "d_no_team"})
    who["d_team_shrunk"] = design.coefficients(beta_shrunk)["d_rapm"]
    who["d_team_free"] = design.coefficients(beta_free)["d_rapm"]
    who["poss"] = design.possessions_by_player().reindex(who["player_id"]).to_numpy()
    who["player"] = who["player_id"].map(names)
    who = who[who["poss"] >= 50_000].sort_values("d_no_team", ascending=False)
    who.round(4).to_csv(OUT / "player_bracket.csv", index=False)

    print("\n--- team-season defensive effects, both conventions ---")
    print(f"spread across team-seasons: free SD {td['team_d_free'].std():.2f}, "
          f"shrunk SD {td['team_d_shrunk'].std():.2f}")
    print(f"correlation between the two: "
          f"{np.corrcoef(td['team_d_free'], td['team_d_shrunk'])[0, 1]:+.3f}")

    print(f"\n--- {TEAM_ABBREV} ---")
    print(sa[["season", "team_d_free", "team_d_shrunk", "rank_free"]]
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"\nmean over the era: free {sa['team_d_free'].mean():+.2f}, "
          f"shrunk {sa['team_d_shrunk'].mean():+.2f}")

    print("\n--- what the same players are worth under each convention ---")
    print(who.head(10)[["player", "poss", "d_no_team", "d_team_shrunk", "d_team_free"]]
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    subj = who[who["player"] == SUBJECT]
    if len(subj):
        r = subj.iloc[0]
        print(f"\n{SUBJECT}: {r['d_no_team']:+.2f} with no team block, "
              f"{r['d_team_shrunk']:+.2f} shrunk, {r['d_team_free']:+.2f} free")

    best = td.groupby("team")["team_d_free"].mean().sort_values(ascending=False)
    print("\n--- best team defensive effect, averaged over the era ---")
    print(best.head(8).round(3).to_string())
    print(f"\n{time.time() - t0:.0f} seconds")


if __name__ == "__main__":
    main()
