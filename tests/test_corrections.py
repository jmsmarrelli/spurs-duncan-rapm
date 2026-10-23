import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import possessions as p

def test_period_reset_even_when_same_team_has_ball():
    ids=p.possession_runs(pd.Series([1.,1.]),pd.Series([1,2]))
    assert ids.nunique()==2

def test_unmarked_period_does_not_inherit_previous_period():
    ids=p.possession_runs(pd.Series([1.,np.nan,1.]),pd.Series([1,2,2]))
    assert pd.isna(ids.iloc[1])
    assert ids.iloc[2] != ids.iloc[0]

def fixture(types,teams):
    return pd.DataFrame(dict(type_text=types,team_id=teams,home_team_id=1,
        away_team_id=2,shooting_play=True,period_number=1))

def test_technical_free_throw_does_not_switch_control():
    e=fixture(["Jump Shot","Free Throw Technical","Layup Shot"],[1,2,1])
    off=p.offensive_team(e)
    assert pd.isna(off.iloc[1])
    assert p.possession_runs(off,e.period_number).nunique()==1

def test_retained_ball_free_throws_not_control_markers():
    e=fixture(["Free Throw Flagrant - 1 of 2","Free Throw Clear Path - 1 of 2"],[2,2])
    assert p.offensive_team(e).isna().all()

def test_and_one_stays_one_marked_sequence():
    e=fixture(["Layup Shot","Free Throw - 1 of 1"],[1,1])
    assert p.possession_runs(p.offensive_team(e),e.period_number).nunique()==1



def test_older_mirror_made_free_throw_zero_value_is_repaired():
    e=pd.DataFrame(dict(type_text=["Free Throw - 1 of 2","Free Throw - 2 of 2","Jump Shot"],
        scoring_play=[True,False,True],score_value=[0,0,3]))
    assert p.scoring_points(e).tolist()==[1,0,3]
