"""Stage 2 - fit RAPM across Tim Duncan's career and read the defensive column.

    python src/run_02_rapm.py

Two fits. A pooled one over all thirteen seasons, which is the career number and
the one with enough possessions behind it to rank players. And a rolling
three-season window, which is the career *arc* - noisier by construction, and the
only way to see a player change.

Writes output/cv_curve.csv, output/career.csv, output/windows.csv,
output/floor_sensitivity.csv, output/subject_path.csv, output/foil_path.csv
and figures 01-03.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (FIG, FOIL, MIN_POSS_PLAYER, MIN_POSS_WINDOW, OUT, PROC,  # noqa: E402
                    RAW, SEASONS, SEED, SUBJECT)
import rapm as R  # noqa: E402
import style as S  # noqa: E402

S.apply()

ALPHAS = [500, 1000, 2000, 3000, 4000, 6000, 9000, 14000, 20000]
WINDOW = 3
CV_WINDOW = (2009, 2011)     # the middle of the sample, where the feed is complete


def load_stints(seasons) -> pd.DataFrame:
    frames = []
    for s in seasons:
        path = PROC / f"stints_{s}.csv.gz"
        if not path.exists():
            raise SystemExit(f"missing {path}. Run src/run_01_stints.py first.")
        frames.append(pd.read_csv(path))
    return pd.concat(frames, ignore_index=True)


def name_maps() -> tuple[pd.Series, pd.Series]:
    """athlete_id -> name and team_id -> abbreviation, from the box scores."""
    players, teams = [], []
    for s in SEASONS:
        b = pd.read_csv(RAW / "player_box" / f"player_box_{s}.csv.gz",
                        usecols=["athlete_id", "athlete_display_name", "team_id",
                                 "team_abbreviation"], low_memory=False)
        players.append(b[["athlete_id", "athlete_display_name"]].dropna())
        teams.append(b[["team_id", "team_abbreviation"]].dropna())
    p = pd.concat(players).drop_duplicates("athlete_id")
    t = pd.concat(teams).drop_duplicates("team_id")
    return (p.set_index(p["athlete_id"].astype("int64"))["athlete_display_name"],
            t.set_index(t["team_id"].astype("int64"))["team_abbreviation"])


def season_label(season: int) -> str:
    return f"{season - 1}-{str(season)[2:]}"


def fig_cv(cv: pd.DataFrame, best: float) -> None:
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    ax.plot(cv["alpha"], cv["cv_mse"], color=S.SERIES[0], lw=2, zorder=3)
    ax.scatter(cv["alpha"], cv["cv_mse"], s=22, color=S.SERIES[0], zorder=4,
               edgecolors=S.SURFACE, lw=1.1)
    ax.axvline(best, color=S.SPURS, lw=1.4, ls=(0, (4, 3)), zorder=2)
    ax.annotate(f"chosen: {best:,.0f}", (best, cv["cv_mse"].max()),
                xytext=(8, -4), textcoords="offset points", fontsize=9,
                color=S.SPURS, fontweight="semibold")
    ax.set_xscale("log")
    ax.set_xlabel("Ridge penalty")
    ax.set_ylabel("Out-of-sample error\n(possession-weighted, folds by game)")
    ax.set_title("The penalty is chosen, not picked", loc="left")
    S.strip(ax)
    S.caption(fig, f"Five-fold cross-validation on {season_label(CV_WINDOW[0])} to "
                   f"{season_label(CV_WINDOW[1])}, with folds split by game so no stint is ever "
                   "scored by a model that saw its own game. The same penalty is then used for "
                   "every window, which is what makes the career arc comparable across seasons.")
    fig.tight_layout()
    fig.savefig(FIG / "01_cv_curve.png")
    plt.close(fig)


def fig_leaderboard(career: pd.DataFrame) -> None:
    d = career.nlargest(20, "d_rapm").sort_values("d_rapm").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8.8, 6.6))
    colours = [S.SPURS if p == SUBJECT else S.SILVER for p in d["player"]]
    ax.barh(d.index, d["d_rapm"], color=colours, height=0.64, zorder=2)
    for i, r in d.iterrows():
        ax.text(r["d_rapm"] + 0.03, i, f"{r['d_rapm']:+.2f}", va="center", fontsize=8.8,
                color=S.INK if r["player"] == SUBJECT else S.INK_2,
                fontweight="semibold" if r["player"] == SUBJECT else "normal")
    ax.set_yticks(d.index, d["player"])
    ax.set_ylim(-0.75, len(d) - 0.25)
    ax.set_xlim(0, d["d_rapm"].max() * 1.2)
    ax.grid(axis="y", visible=False)
    S.strip(ax, keep=("bottom",))
    ax.tick_params(axis="y", labelsize=8.8)
    ax.set_xlabel("Defensive RAPM, points saved per 100 marked sequences")
    ax.set_title("Thirteen seasons pooled, defence only", loc="left")
    S.caption(fig, f"One fit over {season_label(SEASONS[0])} to {season_label(SEASONS[-1])}, "
                   f"{MIN_POSS_PLAYER:,}+ possessions to qualify - about six seasons of heavy "
                   f"minutes. The model is told who was on "
                   "the floor and what happened next, and nothing else - no position, no blocks, "
                   "no rebounds, no reputation.")
    fig.tight_layout()
    fig.savefig(FIG / "02_leaderboard.png")
    plt.close(fig)


def fig_arc(path: pd.DataFrame, foil: pd.DataFrame, windows: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9.6, 5.2))
    band = (windows.groupby("centre")["d_rapm"]
            .quantile([0.5, 0.9, 0.99]).unstack())
    ax.fill_between(band.index, band[0.5], band[0.9], color=S.NEUTRAL, alpha=0.35,
                    zorder=1, linewidth=0)
    ax.plot(band.index, band[0.99], color=S.SILVER, lw=1.6, zorder=2)
    ax.annotate("99th percentile of qualified players", (band.index[-1], band[0.99].iloc[-1]),
                xytext=(8, 0), textcoords="offset points", va="center",
                fontsize=8.8, color=S.INK_3)
    ax.annotate("median to 90th", (band.index[0], band.loc[band.index[0], 0.9]),
                xytext=(4, 6), textcoords="offset points", fontsize=8.8, color=S.INK_3)
    ax.plot(path["centre"], path["d_rapm"], color=S.SPURS, lw=2.4, zorder=4)
    ax.scatter(path["centre"], path["d_rapm"], s=28, color=S.SPURS, zorder=5,
               edgecolors=S.SURFACE, lw=1.2)
    ax.annotate(SUBJECT, (path["centre"].iloc[-1], path["d_rapm"].iloc[-1]),
                xytext=(8, -4), textcoords="offset points", va="center",
                fontsize=9.6, color=S.SPURS, fontweight="semibold")
    if len(foil):
        ax.plot(foil["centre"], foil["d_rapm"], color=S.SERIES[1], lw=2.0, zorder=4)
        ax.scatter(foil["centre"], foil["d_rapm"], s=24, color=S.SERIES[1], zorder=5,
                   edgecolors=S.SURFACE, lw=1.1)
        ax.annotate(FOIL, (foil["centre"].iloc[-1], foil["d_rapm"].iloc[-1]),
                    xytext=(8, 6), textcoords="offset points", va="center",
                    fontsize=9.6, color=S.SERIES[1], fontweight="semibold")
    ax.axhline(0, color=S.INK_3, lw=0.9, zorder=2)
    S.strip(ax)
    ax.set_xlim(path["centre"].min() - 0.4, path["centre"].max() + 3.4)
    ax.set_xticks(path["centre"], [season_label(int(v)) for v in path["centre"]])
    ax.tick_params(axis="x", labelsize=8.4, rotation=0)
    ax.set_ylabel("Defensive RAPM, points saved per 100 marked sequences")
    ax.set_title(f"{SUBJECT}, thirteen seasons of it", loc="left")
    S.caption(fig, 'Overlapping three-season windows, centered on the displayed season. Values are retrospective adjusted associations per 100 marked offensive sequences. Teammate dependence, coverage differences and changing roles limit comparisons across windows.')
    fig.tight_layout()
    fig.savefig(FIG / "03_career_arc.png")
    plt.close(fig)


def main() -> None:
    t0 = time.time()
    names, teams = name_maps()

    # --- choose the penalty ------------------------------------------------
    cv_stints = load_stints(range(CV_WINDOW[0], CV_WINDOW[1] + 1))
    cv_design = R.Design(cv_stints)
    cv = R.cross_validate(cv_design, ALPHAS, n_folds=5, seed=SEED)
    best = float(cv.loc[cv["cv_mse"].idxmin(), "alpha"])
    cv.round(4).to_csv(OUT / "cv_curve.csv", index=False)
    fig_cv(cv, best)
    print(f"penalty chosen by cross-validation: {best:,.0f}")
    print(cv.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    # --- the career fit ----------------------------------------------------
    stints = load_stints(SEASONS)
    design = R.Design(stints)
    coef = R.fit(design, best)
    career = design.coefficients(coef)
    career["poss"] = design.possessions_by_player().reindex(career["player_id"]).to_numpy()
    career["player"] = career["player_id"].map(names)
    everyone = career.copy()
    career = career[career["poss"] >= MIN_POSS_PLAYER].sort_values("d_rapm",
                                                                   ascending=False)
    career.round(4).to_csv(OUT / "career.csv", index=False)
    fig_leaderboard(career)

    # The floor is a judgement call, so its consequences are printed rather than
    # buried: below about fifty thousand possessions the leaderboard fills with
    # players whose offensive and defensive coefficients are large and cancel.
    floors = []
    subj_id = everyone.loc[everyone["player"] == SUBJECT, "player_id"]
    for floor in (10_000, 20_000, 30_000, 50_000, 75_000, 100_000):
        sub = everyone[everyone["poss"] >= floor].sort_values("d_rapm", ascending=False)
        top10 = sub.head(10)
        row = {"floor": floor, "players": len(sub),
               "leader": sub["player"].iloc[0],
               "leader_d_rapm": float(sub["d_rapm"].iloc[0]),
               "leader_poss": int(sub["poss"].iloc[0]),
               "median_poss_of_top10": int(top10["poss"].median()),
               "sd_d_rapm": float(sub["d_rapm"].std())}
        # Only meaningful when the subject clears the floor himself; at a
        # hundred thousand possessions he is ten short of qualifying.
        if len(subj_id) and (sub["player"] == SUBJECT).any():
            v = everyone.loc[everyone["player"] == SUBJECT, "d_rapm"].iloc[0]
            row["subject_rank"] = int((sub["d_rapm"] > v).sum()) + 1
        else:
            row["subject_rank"] = None
        floors.append(row)
    floors = pd.DataFrame(floors)
    floors.round(4).to_csv(OUT / "floor_sensitivity.csv", index=False)

    print(f"\n{len(stints):,} stint-sides, {design.n_players:,} players, "
          f"{int(design.poss.sum()):,} possessions")
    print(f"{len(career):,} players with {MIN_POSS_PLAYER:,}+ possessions")
    print("\n--- how the leaderboard depends on that floor ---")
    print(floors.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    print("\n--- defensive RAPM, thirteen seasons pooled ---")
    print(career.head(12)[["player", "poss", "o_rapm", "d_rapm", "rapm"]]
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print("\n--- and by total, offence plus defence ---")
    print(career.nlargest(10, "rapm")[["player", "poss", "o_rapm", "d_rapm", "rapm"]]
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    iron = everyone[everyone["poss"] >= 100_000].sort_values("d_rapm", ascending=False)
    print(f"\n--- the {len(iron)} players with 100,000+ possessions in the era ---")
    print(iron[["player", "poss", "o_rapm", "d_rapm", "rapm"]].head(6)
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    subj = career[career["player"] == SUBJECT]
    if len(subj):
        rank = int((career["d_rapm"] > subj["d_rapm"].iloc[0]).sum()) + 1
        print(f"\n{SUBJECT}: defensive {subj['d_rapm'].iloc[0]:+.3f}, "
              f"offensive {subj['o_rapm'].iloc[0]:+.3f}, total {subj['rapm'].iloc[0]:+.3f}, "
              f"{int(subj['poss'].iloc[0]):,} possessions, rank {rank} of {len(career)}")

    # --- the career arc ----------------------------------------------------
    rows = []
    centres = [s for s in SEASONS if s - 1 >= SEASONS[0] and s + 1 <= SEASONS[-1]]
    for centre in centres:
        w = load_stints(range(centre - 1, centre + 2))
        d = R.Design(w)
        c = R.fit(d, best)
        tab = d.coefficients(c)
        tab["poss"] = d.possessions_by_player().reindex(tab["player_id"]).to_numpy()
        tab = tab[tab["poss"] >= MIN_POSS_WINDOW]
        tab["player"] = tab["player_id"].map(names)
        tab["centre"] = centre
        rows.append(tab)
        print(f"  window centred on {season_label(centre)}: {len(tab):,} qualified players",
              flush=True)
    windows = pd.concat(rows, ignore_index=True)
    windows.round(4).to_csv(OUT / "windows.csv", index=False)

    path = windows[windows["player"] == SUBJECT].sort_values("centre")
    path.round(4).to_csv(OUT / "subject_path.csv", index=False)
    foil = windows[windows["player"] == FOIL].sort_values("centre")
    foil.round(4).to_csv(OUT / "foil_path.csv", index=False)
    fig_arc(path, foil, windows)

    print(f"\n--- {SUBJECT}, three-season windows ---")
    print(path[["centre", "poss", "o_rapm", "d_rapm", "rapm"]]
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"\n--- {FOIL}, the same windows ---")
    print(foil[["centre", "poss", "o_rapm", "d_rapm", "rapm"]]
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"\n{time.time() - t0:.0f} seconds")


if __name__ == "__main__":
    main()
