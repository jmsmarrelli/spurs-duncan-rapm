# Method notes

The reconstruction, the two things that had to be added before the ratings made
sense, and what the team-versus-player bracket does and does not establish.

## Rebuilding the lineups

The feed records substitutions and never records who is on the floor. The walk is
the obvious one — start each period with five, apply every substitution in order,
carry the set forward — and the difficulty is entirely in the failures.

Period-opening fives are the hard part. The box score marks the starters, which
gives period one. For periods two onward the five is inferred from the first
events of the period and the substitutions around them, and when that inference
is inconsistent the game is dropped.

The check is arithmetic and external: total each player's seconds on the floor
and compare with the minutes in the box score. A game is kept only if the mean
absolute error across its players is under 1.5 minutes and no single player is
off by more than 6. **14,332 of 15,611 games pass, at a mean error of 0.35
minutes.**

`output/reconstruction_audit.csv` gives the count and the reason for every
season. Almost all failures are `lineup` — a substitution that leaves six players
on the floor or five who cannot be reconciled — and they concentrate in the first
three seasons, where the feed is worse.

## Possessions, counted rather than estimated

The usual FGA + 0.44×FTA − OREB + TOV is a decent season-level approximation and
a poor stint-level one, because the 0.44 is a league-average guess about which
free throws end a trip and stints are short enough for the guess to matter.

Since the log is right there, possessions are counted from it: mark every event
that unambiguously identifies which team has the ball, compress the marks into
runs, and call each run a possession. Ambiguous events — fouls, timeouts, jump
balls, substitutions — are skipped rather than guessed at, which is safe, because
dropping a marker can only merge two possessions that were already adjacent and
identical. And-ones fall out correctly: the made shot and the free throw are
marked to the same team, are adjacent, and collapse into the one possession they
were.

## Two things that had to be in the model

Both were absent from the first version of this, and both changed the answer
enough to be worth naming.

**An intercept.** Without one, a penalized coefficient is pulled toward *zero
points per 100*, not toward league average, and the player block has to carry the
league's scoring level. Every coefficient inflates to cover it.

**An unpenalized effect per season.** Thirteen seasons of a league whose scoring
level moved by several points per 100. Without season effects that movement also
lands in the player coefficients, and players whose careers sit in high-scoring
years are systematically mis-rated.

The first version I ran had Nick Calathes third in defensive RAPM on 7,400
possessions and Bradley Beal fifth, and I spent an hour looking for a bug in the
lineup reconstruction before finding it in the design matrix. With the intercept and the season
effects in, the top of the same table is Garnett, Bogut, Duncan, Ben Wallace and
Tony Allen, and `output/floor_sensitivity.csv` shows the ranking barely moves as
the possession floor goes from ten thousand to a hundred thousand. That
stability is the evidence that the fix was a fix and not a preference.

## The penalty

Five-fold cross-validation with folds split by game, on the middle three seasons
of the sample. It lands at 3,000 and the curve is shallow: 2,000 and 4,000 are
within 0.5 of it on a held-out error of 3,581. The same penalty is then used for
every window, which is what makes the career arc comparable season to season —
re-tuning per window would mix a change in the player with a change in the
instrument.

The scale of a RAPM rating is set by the penalty, so a rating is only meaningful
against the distribution it came from. That is why figure 03 draws the percentile
band and why the leaderboards quote ranks as well as values.

## Team against player: what the bracket is for

Adding a defensive effect per team-season is easy. Interpreting it is not, because
a team-season effect is nearly collinear with the defensive coefficients of the
players who filled that roster. The split between them is decided by which block
carries the ridge penalty, not by the data.

So two things are reported, and only one of them is an estimate.

**The test.** Does the team block improve *held-out* prediction? Folds by game,
same as everywhere else. This is a real question with a real answer, and the
answer is 0.79 of 3,650 — consistent in sign across five folds, and two
hundredths of one per cent.

**The bracket.** With the team block removed, shrunk exactly as hard as a player,
and effectively free, the same player's rating is read off all three. The two ends
bound the answer and nothing in between is estimable. For Duncan the bracket is
+4.59 to +4.28; for Roy Hibbert it is +2.07 to +0.34.

A note on "effectively free": the team dummies sum to the intercept, so with no
penalty at all the normal equations are exactly singular. The free convention
uses a token multiplier of 1e-6 on the same ridge, which is what unpenalized
means in practice.

`partial_ridge` exists because scikit-learn's Ridge penalises every column
identically, which is precisely the thing this model must not do. At a few
thousand columns the normal equations are cheap to form and solve directly.

## Where this is weakest

**The first six seasons of the career are not here**, and they are the ones with
the two Defensive Player of the Year awards in them. The mirror cannot see before
2003-04.

**The early seasons that are here are the thinnest.** 76% coverage in 2003-04 to
2005-06 against 96% afterwards. Games fail for reasons unrelated to who was
playing well, so this is noise rather than bias, but the peak of the career is
measured with a quarter less evidence than the decline.

**No intervals.** Ridge coefficients do not come with honest standard errors, and
a bootstrap over 762,000 stints was out of budget for this project. The
percentile band and the floor sensitivity are what stand in for them, and neither
is a substitute. Nothing here should be read to a third decimal place.

**A marginal contribution is not an ability.** Figure 03 is the illustration and
it is not a solvable problem: when Kawhi Leonard becomes the Defensive Player of
the Year beside a 38-year-old Duncan, Duncan's marginal contribution falls
because the counterfactual improved. Any rating built on on-court/off-court
variation has this property.

**Thirteen seasons pooled into one coefficient** means the career leaderboard
mixes a player's peak and decline. It is the right object for "who was the best
defender of the era" and the wrong one for "who was the best defender", and the
rolling windows are there for the second question.

**Regular season only.** The postseason is a different sample against different
opposition and there is not enough of it to fit this model on.
