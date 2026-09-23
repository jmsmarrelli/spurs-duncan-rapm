# Data

Two files per season, both from
[sportsdataverse/hoopR-data](https://github.com/sportsdataverse/hoopR-data), a
mirror of ESPN's public feeds:

* `data/raw/pbp/play_by_play_<season>.csv.gz` — every event, including the
  substitutions the lineups are rebuilt from.
* `data/raw/player_box/player_box_<season>.csv.gz` — the box score the
  reconstruction is checked against, and where the names come from.

`<season>` is the year the season ended: 2016 is 2015-16.

## Getting the files

```bash
git clone --filter=blob:none --no-checkout --depth 1 \
  https://github.com/sportsdataverse/hoopR-data.git /tmp/hoopR-data
cd /tmp/hoopR-data
git sparse-checkout set --no-cone "nba/pbp/csv/*" "nba/player_box/csv/*"
git checkout
cd -
mkdir -p data/raw/pbp data/raw/player_box
cp /tmp/hoopR-data/nba/pbp/csv/play_by_play_20*.csv.gz data/raw/pbp/
cp /tmp/hoopR-data/nba/player_box/csv/player_box_20*.csv.gz data/raw/player_box/
```

About 510 MB for the full span; this project reads 2003-04 to 2015-16. `data/raw/`
and `data/processed/` are gitignored; everything the analysis cites is written to
`output/` and committed.

## Why the sample starts at 2003-04

Tim Duncan arrived in 1997-98. The play-by-play mirror carries 2001-02 and
2002-03 at 38% and 81% of the games, which is not enough to rebuild a season of
lineups from, so his first six seasons are out of reach. This project covers the
last thirteen.

## The coverage cliff inside the sample

The substitution record is not equally good across the sample, and the
reconstruction audit says so plainly:

| Seasons | Games reconstructed |
|---|---|
| 2003-04 to 2005-06 | **76.3%** |
| 2006-07 to 2015-16 | **96.5%** |

The failures are almost all one reason — a substitution that leaves six players
on the floor, or five who do not match the box score — and they are dropped
rather than patched. `output/reconstruction_audit.csv` reports the count and the
reason for every season.

That is a real limitation on the early end of the sample and it points the wrong
way for this project's subject: the seasons with the worst coverage are the ones
in which Duncan was at his peak. It is not a bias in the estimate so much as
noise in it, since games fail for reasons that have nothing to do with who was
playing well, but the first three seasons carry a quarter less evidence than the
rest.

## Columns used

| Column | Used for |
|---|---|
| `game_id`, `season`, `season_type` | joining, and the regular-season filter |
| `period_number`, `start_game_seconds_remaining`, `game_play_number` | ordering events and timing the stints |
| `type_text`, `athlete_id_1/2/3`, `team_id` | substitutions, and who did what |
| `scoring_play`, `score_value`, `shooting_play` | points, and which team had the ball |
| `home_team_id`, `away_team_id` | sides |
| `athlete_id`, `starter`, `minutes`, `did_not_play` (box) | the period-one five, and the minutes check |
| `athlete_display_name`, `team_abbreviation` (box) | names |
