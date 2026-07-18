"""
tests/test_scorer.py
--------------------
Unit tests for the scorer module.
"""

from datetime import date
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scorer import build_commit_counts, compute_scores, extract_author, find_recent_authors


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_commit(login=None, name="Test User", date_str="2024-05-10T10:00:00Z"):
    author_obj = {"login": login} if login else None
    return {
        "author": author_obj,
        "commit": {
            "author": {"name": name, "date": date_str}
        },
    }


# ---------------------------------------------------------------------------
# extract_author
# ---------------------------------------------------------------------------

def test_extract_author_prefers_login():
    c = _make_commit(login="alice", name="Alice Smith")
    assert extract_author(c) == "alice"


def test_extract_author_falls_back_to_name():
    c = _make_commit(login=None, name="Bob Jones")
    assert extract_author(c) == "Bob Jones"


def test_extract_author_unknown():
    c = {"author": None, "commit": {"author": None}}
    assert extract_author(c) == "unknown"


# ---------------------------------------------------------------------------
# build_commit_counts
# ---------------------------------------------------------------------------

def test_build_commit_counts_basic():
    commits = [
        _make_commit(login="alice"),
        _make_commit(login="alice"),
        _make_commit(login="bob"),
    ]
    df = build_commit_counts(commits)
    assert df.loc[df["contributor"] == "alice", "commits"].iloc[0] == 2
    assert df.loc[df["contributor"] == "bob", "commits"].iloc[0] == 1


def test_build_commit_counts_percentage_sums_to_100():
    commits = [_make_commit(login="alice"), _make_commit(login="bob"), _make_commit(login="carol")]
    df = build_commit_counts(commits)
    assert abs(df["percentage"].sum() - 100.0) < 0.1  # rounding to 2dp may cause small drift


def test_build_commit_counts_sorted_descending():
    commits = [_make_commit(login="low")] + [_make_commit(login="high")] * 5
    df = build_commit_counts(commits)
    assert df.iloc[0]["contributor"] == "high"


# ---------------------------------------------------------------------------
# find_recent_authors
# ---------------------------------------------------------------------------

def test_find_recent_authors_includes_recent():
    reference = date(2024, 5, 15)
    commits = [_make_commit(login="alice", date_str="2024-05-12T00:00:00Z")]
    recent = find_recent_authors(commits, reference)
    assert "alice" in recent


def test_find_recent_authors_excludes_old():
    reference = date(2024, 5, 15)
    commits = [_make_commit(login="old_dev", date_str="2024-04-01T00:00:00Z")]
    recent = find_recent_authors(commits, reference)
    assert "old_dev" not in recent


# ---------------------------------------------------------------------------
# compute_scores
# ---------------------------------------------------------------------------

def test_compute_scores_returns_correct_columns():
    df_commits = pd.DataFrame([
        {"contributor": "alice", "commits": 10, "percentage": 100.0}
    ])
    all_time = [{"login": "alice", "contributions": 100}]
    df_score = compute_scores(df_commits, all_time, {"alice"})
    expected_cols = {"Rank", "Contributor", "Commits (range)", "All-time commits", "Recent (7d)", "Score (0–100)"}
    assert expected_cols.issubset(set(df_score.columns))


def test_compute_scores_rank_1_highest():
    df_commits = pd.DataFrame([
        {"contributor": "alice", "commits": 10, "percentage": 67.0},
        {"contributor": "bob", "commits": 5, "percentage": 33.0},
    ])
    all_time = [
        {"login": "alice", "contributions": 200},
        {"login": "bob", "contributions": 50},
    ]
    df_score = compute_scores(df_commits, all_time, {"alice"})
    assert df_score.iloc[0]["Contributor"] == "alice"
    assert df_score.iloc[0]["Rank"] == 1


def test_compute_scores_max_score_lte_100():
    df_commits = pd.DataFrame([
        {"contributor": "alice", "commits": 100, "percentage": 100.0}
    ])
    all_time = [{"login": "alice", "contributions": 100}]
    df_score = compute_scores(df_commits, all_time, {"alice"})
    assert df_score.iloc[0]["Score (0–100)"] <= 100.0
