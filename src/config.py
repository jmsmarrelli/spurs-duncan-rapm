"""Paths, constants and the handful of knobs the pipeline exposes."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
FIG = ROOT / "figures"
OUT = ROOT / "output"

for d in (RAW, PROC, FIG, OUT):
    d.mkdir(parents=True, exist_ok=True)

# Season label is the year the season ends: 2016 == 2015-16.
#
# The sample is Tim Duncan's career as far back as the play-by-play mirror can
# see it. He arrived in 1997-98; the feed is essentially complete from 2003-04
# (2001-02 and 2002-03 carry 38% and 81% of the games, which is not enough to
# rebuild a season of lineups from). He retired after 2015-16, and that is the
# last season here.
FIRST_SEASON = 2004
LAST_SEASON = 2016
SEASONS = list(range(FIRST_SEASON, LAST_SEASON + 1))

TEAM_ABBREV = "SA"
SUBJECT = "Tim Duncan"
# The player whose arrival is the obvious alternative explanation for the end of
# the subject's, drawn on the same axes rather than argued about in prose.
FOIL = "Kawhi Leonard"

# A game is kept only if reconstructed floor time agrees with the box score.
MAX_MEAN_MINUTE_ERROR = 1.5     # minutes, averaged over players in the game
MAX_PLAYER_MINUTE_ERROR = 6.0   # minutes, worst single player

# Possessions to qualify. Fifty thousand is roughly six seasons of heavy minutes,
# which is what a *career* leaderboard over thirteen seasons ought to require.
# It is not load-bearing: output/floor_sensitivity.csv runs the same table from
# ten thousand up and the top of it barely moves.
MIN_POSS_PLAYER = 50000         # career leaderboard, roughly six seasons of heavy minutes
MIN_POSS_WINDOW = 12000         # three-season window, roughly one season of heavy minutes

SEED = 20240117
