"""
scorer.py
---------
Contributor scoring logic for the GitHub Analytics Dashboard.

Score formula
~~~~~~~~~~~~~
Each contributor receives a weighted score from three signals:

    score = 0.50 × volume_signal
          + 0.30 × all_time_signal
          + 0.20 × recency_signal

- **volume_signal** — commits in the selected range ÷ maximum commits in range
- **all_time_signal** — contributor's all-time commits ÷ total all-time commits
- **recency_signal** — 1 if the contributor pushed within the last 7 days, else 0

The raw score (0–1) is multiplied by 100 before display.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd


def extract_author(commit: dict) -> str:
    """Return the GitHub login (or git author name) for a raw commit object."""
    return (
        (commit.get("author") or {}).get("login")
        or (commit.get("commit", {}).get("author") or {}).get("name")
        or "unknown"
    )


def build_commit_counts(commits: list[dict]) -> pd.DataFrame:
    """
    Aggregate commit counts per author.

    Returns a DataFrame with columns: contributor, commits, percentage.
    """
    counts: dict[str, int] = {}
    for c in commits:
        author = extract_author(c)
        counts[author] = counts.get(author, 0) + 1

    df = (
        pd.DataFrame(list(counts.items()), columns=["contributor", "commits"])
        .sort_values("commits", ascending=False)
        .reset_index(drop=True)
    )
    total = df["commits"].sum()
    df["percentage"] = (df["commits"] / total * 100).round(2) if total else 0.0
    return df


def find_recent_authors(commits: list[dict], reference_date: date) -> set[str]:
    """Return the set of author logins who committed within the last 7 days."""
    cutoff = (reference_date - timedelta(days=7)).isoformat()
    recent: set[str] = set()
    for c in commits:
        committed_at = (c.get("commit", {}).get("author") or {}).get("date", "")
        if committed_at[:10] >= cutoff[:10]:
            recent.add(extract_author(c))
    return recent


def compute_scores(
    df_commits: pd.DataFrame,
    all_time_contributors: list[dict],
    recent_authors: set[str],
) -> pd.DataFrame:
    """
    Build the leaderboard DataFrame.

    Parameters
    ----------
    df_commits:
        Output of :func:`build_commit_counts`.
    all_time_contributors:
        Raw list returned by :func:`github_api.fetch_contributors`.
    recent_authors:
        Output of :func:`find_recent_authors`.

    Returns
    -------
    DataFrame with columns:
        Rank, Contributor, Commits (range), All-time commits, Recent (7d),
        Score (0–100)
    """
    all_time_map: dict[str, int] = {
        c["login"]: c["contributions"]
        for c in all_time_contributors
        if "login" in c
    }
    total_all_time = sum(all_time_map.values()) or 1
    max_commits = df_commits["commits"].max() or 1

    rows = []
    for _, row in df_commits.iterrows():
        login = str(row["contributor"])
        vol = row["commits"] / max_commits
        at = all_time_map.get(login, 0) / total_all_time
        recency = 1 if login in recent_authors else 0
        raw_score = 0.5 * vol + 0.3 * at + 0.2 * recency
        rows.append(
            {
                "Rank": 0,
                "Contributor": login,
                "Commits (range)": int(row["commits"]),
                "All-time commits": all_time_map.get(login, "N/A"),
                "Recent (7d)": "✅" if recency else "—",
                "Score (0–100)": round(raw_score * 100, 1),
            }
        )

    df = (
        pd.DataFrame(rows)
        .sort_values("Score (0–100)", ascending=False)
        .reset_index(drop=True)
    )
    df["Rank"] = range(1, len(df) + 1)
    return df[["Rank", "Contributor", "Commits (range)", "All-time commits", "Recent (7d)", "Score (0–100)"]]
