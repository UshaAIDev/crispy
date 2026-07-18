"""
GitHub Analytics Dashboard
---------------------------
Shows commit percentage by contributor, daily build success/failure counts,
and a best-contributor ranking for any public GitHub repository.

Usage:
    streamlit run app.py

Authentication (optional – raises API rate limit from 60 to 5,000 req/h):
    export GITHUB_TOKEN=ghp_...
"""

import os
import math
from datetime import date, timedelta, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="GitHub Analytics Dashboard",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
GITHUB_API = "https://api.github.com"


def _headers(token: str | None) -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = "Bearer " + token
    return h


def _get(url: str, params: dict, token: str | None) -> requests.Response:
    return requests.get(url, headers=_headers(token), params=params, timeout=20)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_commits(owner: str, repo: str, since_iso: str, until_iso: str, token: str | None) -> list[dict]:
    """Return a flat list of commit records for the date range."""
    commits = []
    page = 1
    while True:
        resp = _get(
            f"{GITHUB_API}/repos/{owner}/{repo}/commits",
            {"since": since_iso, "until": until_iso, "per_page": 100, "page": page},
            token,
        )
        if resp.status_code == 409:
            # empty repo
            break
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        commits.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return commits


@st.cache_data(ttl=300, show_spinner=False)
def fetch_workflow_runs(owner: str, repo: str, since_iso: str, until_iso: str, token: str | None) -> list[dict]:
    """Return workflow runs in the date range (created >= since, <= until)."""
    runs = []
    page = 1
    # GitHub query syntax for created range
    created_query = f"{since_iso[:10]}..{until_iso[:10]}"
    while True:
        resp = _get(
            f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs",
            {"created": created_query, "per_page": 100, "page": page, "status": "completed"},
            token,
        )
        if resp.status_code in (403, 404):
            break
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("workflow_runs", [])
        if not batch:
            break
        runs.extend(batch)
        total = data.get("total_count", 0)
        if len(runs) >= total or len(batch) < 100:
            break
        page += 1
    return runs


@st.cache_data(ttl=300, show_spinner=False)
def fetch_contributors(owner: str, repo: str, token: str | None) -> list[dict]:
    """Return the top contributors list (all-time) from GitHub."""
    contributors = []
    page = 1
    while True:
        resp = _get(
            f"{GITHUB_API}/repos/{owner}/{repo}/contributors",
            {"per_page": 100, "page": page, "anon": "false"},
            token,
        )
        if resp.status_code in (403, 404, 204):
            break
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        contributors.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return contributors


def rate_limit_info(token: str | None) -> dict:
    try:
        resp = requests.get(f"{GITHUB_API}/rate_limit", headers=_headers(token), timeout=10)
        if resp.ok:
            return resp.json().get("rate", {})
    except Exception:
        pass
    return {}


# ---------------------------------------------------------------------------
# Sidebar – controls
# ---------------------------------------------------------------------------
st.sidebar.title("⚙️ Settings")

token_env = os.environ.get("GITHUB_TOKEN", "")
token_input = st.sidebar.text_input(
    "GitHub Token (optional)",
    value=token_env,
    type="password",
    help="Personal access token to increase API rate limit from 60 → 5,000 req/h.",
)
token: str | None = token_input.strip() or None

st.sidebar.markdown("---")
owner = st.sidebar.text_input("Repository Owner", value="microsoft")
repo = st.sidebar.text_input("Repository Name", value="vscode")

st.sidebar.markdown("---")
range_opt = st.sidebar.selectbox(
    "Date Range",
    options=["Last 7 days", "Last 30 days", "Last 90 days", "Custom"],
    index=1,
)

today = date.today()
if range_opt == "Last 7 days":
    date_from = today - timedelta(days=7)
    date_to = today
elif range_opt == "Last 30 days":
    date_from = today - timedelta(days=30)
    date_to = today
elif range_opt == "Last 90 days":
    date_from = today - timedelta(days=90)
    date_to = today
else:
    date_from = st.sidebar.date_input("From", value=today - timedelta(days=30))
    date_to = st.sidebar.date_input("To", value=today)

since_iso = datetime.combine(date_from, datetime.min.time()).isoformat() + "Z"
until_iso = datetime.combine(date_to, datetime.max.time()).isoformat() + "Z"

fetch_btn = st.sidebar.button("🔄 Fetch / Refresh", type="primary", use_container_width=True)

# Show rate limit
rl = rate_limit_info(token)
if rl:
    st.sidebar.markdown("---")
    st.sidebar.caption(
        f"API rate limit: **{rl.get('remaining', '?')}/{rl.get('limit', '?')}** remaining  \n"
        f"Resets at {datetime.utcfromtimestamp(rl.get('reset', 0)).strftime('%H:%M UTC')}"
    )

# ---------------------------------------------------------------------------
# Main header
# ---------------------------------------------------------------------------
st.title("📊 GitHub Analytics Dashboard")
st.markdown(
    f"Analyzing **[{owner}/{repo}](https://github.com/{owner}/{repo})** "
    f"from **{date_from}** to **{date_to}**"
)

if not owner or not repo:
    st.warning("Enter a repository owner and name in the sidebar.")
    st.stop()

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
with st.spinner(f"Fetching data from GitHub for {owner}/{repo} …"):
    try:
        commits_raw = fetch_commits(owner, repo, since_iso, until_iso, token)
        runs_raw = fetch_workflow_runs(owner, repo, since_iso, until_iso, token)
        contributors_raw = fetch_contributors(owner, repo, token)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        if status == 404:
            st.error(f"Repository **{owner}/{repo}** not found. Check the owner/repo name in the sidebar.")
        elif status == 403:
            st.error(
                "GitHub API rate limit exceeded or access denied.  \n"
                "Add a **GitHub Token** in the sidebar to increase the limit."
            )
        else:
            st.error(f"GitHub API error {status}: {exc}")
        st.stop()
    except requests.RequestException as exc:
        st.error(f"Network error: {exc}")
        st.stop()

if not commits_raw and not runs_raw:
    st.info("No data found for the selected date range.  Try a wider range or check the repository name.")
    st.stop()

# ---------------------------------------------------------------------------
# Section 1 – Commit percentage by contributor
# ---------------------------------------------------------------------------
st.header("1 · Commit Percentage by Contributor")

if not commits_raw:
    st.info("No commits found in this date range.")
else:
    commit_authors: dict[str, int] = {}
    for c in commits_raw:
        author = (
            (c.get("author") or {}).get("login")
            or (c.get("commit", {}).get("author") or {}).get("name")
            or "unknown"
        )
        commit_authors[author] = commit_authors.get(author, 0) + 1

    df_commits = (
        pd.DataFrame(list(commit_authors.items()), columns=["contributor", "commits"])
        .sort_values("commits", ascending=False)
        .reset_index(drop=True)
    )
    df_commits["percentage"] = (df_commits["commits"] / df_commits["commits"].sum() * 100).round(2)

    col1, col2 = st.columns([1, 1])

    with col1:
        # Pie – top 10, rest grouped
        top_n = 10
        if len(df_commits) > top_n:
            top = df_commits.head(top_n).copy()
            others_count = df_commits.iloc[top_n:]["commits"].sum()
            others_pct = df_commits.iloc[top_n:]["percentage"].sum()
            others_row = pd.DataFrame(
                [{"contributor": f"Others ({len(df_commits) - top_n})", "commits": others_count, "percentage": round(others_pct, 2)}]
            )
            pie_df = pd.concat([top, others_row], ignore_index=True)
        else:
            pie_df = df_commits.copy()

        fig_pie = px.pie(
            pie_df,
            names="contributor",
            values="commits",
            title=f"Commit share — {date_from} → {date_to}",
            hole=0.35,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        fig_pie.update_layout(showlegend=False, margin=dict(t=40, b=10, l=10, r=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.subheader("Contributor table")
        st.dataframe(
            df_commits.rename(columns={"contributor": "Contributor", "commits": "Commits", "percentage": "%"}),
            hide_index=True,
            use_container_width=True,
        )
        st.caption(f"Total commits in range: **{df_commits['commits'].sum()}**")

# ---------------------------------------------------------------------------
# Section 2 – Builds per day (success / failure)
# ---------------------------------------------------------------------------
st.header("2 · Builds per Day")

if not runs_raw:
    st.info("No completed workflow runs found for this date range (or Actions not enabled for this repo).")
else:
    build_rows = []
    for r in runs_raw:
        created = r.get("created_at", "")[:10]
        conclusion = r.get("conclusion") or "other"
        build_rows.append({"date": created, "conclusion": conclusion})

    df_runs = pd.DataFrame(build_rows)
    df_runs["date"] = pd.to_datetime(df_runs["date"])

    # Pivot: one row per day, columns per conclusion
    df_pivot = (
        df_runs.groupby(["date", "conclusion"])
        .size()
        .reset_index(name="count")
        .pivot(index="date", columns="conclusion", values="count")
        .fillna(0)
        .astype(int)
        .reset_index()
    )

    # Ensure success/failure columns exist
    for col in ("success", "failure"):
        if col not in df_pivot.columns:
            df_pivot[col] = 0

    # All-dates spine so gaps show as zero
    all_dates = pd.date_range(date_from, date_to, freq="D")
    df_spine = pd.DataFrame({"date": all_dates})
    df_pivot = df_spine.merge(df_pivot, on="date", how="left").fillna(0)

    # Build stacked bar
    other_cols = [c for c in df_pivot.columns if c not in ("date", "success", "failure")]
    color_map = {"success": "#2ecc71", "failure": "#e74c3c"}
    for c in other_cols:
        color_map[c] = "#95a5a6"

    fig_bar = go.Figure()
    for conclusion in ["success", "failure"] + other_cols:
        if conclusion in df_pivot.columns:
            fig_bar.add_trace(
                go.Bar(
                    x=df_pivot["date"],
                    y=df_pivot[conclusion],
                    name=conclusion.capitalize(),
                    marker_color=color_map.get(conclusion, "#95a5a6"),
                )
            )
    fig_bar.update_layout(
        barmode="stack",
        title="Workflow run conclusions per day",
        xaxis_title="Date",
        yaxis_title="Runs",
        legend_title="Conclusion",
        margin=dict(t=50, b=10),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # Summary metrics
    total_runs = len(runs_raw)
    successes = sum(1 for r in runs_raw if r.get("conclusion") == "success")
    failures = sum(1 for r in runs_raw if r.get("conclusion") == "failure")
    success_rate = successes / total_runs * 100 if total_runs else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total runs", total_runs)
    m2.metric("✅ Successful", successes)
    m3.metric("❌ Failed", failures)
    m4.metric("Success rate", f"{success_rate:.1f}%")

# ---------------------------------------------------------------------------
# Section 3 – Best Contributor Ranking
# ---------------------------------------------------------------------------
st.header("3 · Best Contributor Ranking")

with st.expander("ℹ️ How the score is calculated", expanded=False):
    st.markdown(
        """
        The **Best Contributor Score** combines three signals:

        | Signal | Weight | Description |
        |--------|--------|-------------|
        | Commit volume (in range) | 50% | Number of commits in the selected date range |
        | All-time contribution share | 30% | Contributor's share of total all-time commits (from `/contributors` API) |
        | Recency bonus | 20% | Whether the contributor committed in the last 7 days |

        **Formula (per contributor)**

        ```
        score = 0.5 × (commits_in_range / max_commits_in_range)
              + 0.3 × (all_time_commits / total_all_time_commits)
              + 0.2 × recency_flag          # 1 if committed in last 7 days, else 0
        ```

        Scores are normalized to **0–100**.
        """
    )

if not commits_raw:
    st.info("No commits available to rank contributors.")
else:
    # --- recent-7-days flag ---
    seven_days_ago = (today - timedelta(days=7)).isoformat()  # YYYY-MM-DD string
    recent_authors: set[str] = set()
    for c in commits_raw:
        committed_at = (c.get("commit", {}).get("author") or {}).get("date", "")
        # committed_at is ISO 8601 (e.g. "2024-05-01T12:00:00Z"); slice to YYYY-MM-DD for comparison
        if committed_at[:10] >= seven_days_ago[:10]:
            author = (
                (c.get("author") or {}).get("login")
                or (c.get("commit", {}).get("author") or {}).get("name")
                or "unknown"
            )
            recent_authors.add(author)

    # --- All-time commits map ---
    all_time_map: dict[str, int] = {c["login"]: c["contributions"] for c in contributors_raw if "login" in c}
    total_all_time = sum(all_time_map.values()) or 1

    # --- Build score dataframe ---
    if "df_commits" not in dir():
        # Rebuild if section 1 was skipped
        commit_authors_local: dict[str, int] = {}
        for c in commits_raw:
            author = (
                (c.get("author") or {}).get("login")
                or (c.get("commit", {}).get("author") or {}).get("name")
                or "unknown"
            )
            commit_authors_local[author] = commit_authors_local.get(author, 0) + 1
        df_commits = pd.DataFrame(
            list(commit_authors_local.items()), columns=["contributor", "commits"]
        ).sort_values("commits", ascending=False).reset_index(drop=True)

    max_commits = df_commits["commits"].max() or 1

    score_rows = []
    for _, row in df_commits.iterrows():
        login = row["contributor"]
        vol_score = row["commits"] / max_commits
        at_score = all_time_map.get(login, 0) / total_all_time
        recency = 1 if login in recent_authors else 0
        raw = 0.5 * vol_score + 0.3 * at_score + 0.2 * recency
        score_rows.append(
            {
                "Rank": 0,
                "Contributor": login,
                "Commits (range)": int(row["commits"]),
                "All-time commits": all_time_map.get(login, "N/A"),
                "Recent (7d)": "✅" if recency else "—",
                "Score (0–100)": round(raw * 100, 1),
            }
        )

    df_score = (
        pd.DataFrame(score_rows)
        .sort_values("Score (0–100)", ascending=False)
        .reset_index(drop=True)
    )
    df_score["Rank"] = range(1, len(df_score) + 1)
    cols_order = ["Rank", "Contributor", "Commits (range)", "All-time commits", "Recent (7d)", "Score (0–100)"]
    df_score = df_score[cols_order]

    # Top-3 callout
    if len(df_score) >= 1:
        medals = ["🥇", "🥈", "🥉"]
        callout_cols = st.columns(min(3, len(df_score)))
        for i, col in enumerate(callout_cols):
            r = df_score.iloc[i]
            col.metric(
                label=f"{medals[i]} #{r['Rank']} {r['Contributor']}",
                value=f"{r['Score (0–100)']} pts",
                delta=f"{r['Commits (range)']} commits",
            )

    st.dataframe(df_score, hide_index=True, use_container_width=True)

    # Horizontal bar chart of top-20
    top20 = df_score.head(20).sort_values("Score (0–100)")
    fig_rank = px.bar(
        top20,
        x="Score (0–100)",
        y="Contributor",
        orientation="h",
        color="Score (0–100)",
        color_continuous_scale="Blues",
        title="Top contributors by score",
        text="Score (0–100)",
    )
    fig_rank.update_traces(texttemplate="%{text:.1f}", textposition="outside")
    fig_rank.update_layout(showlegend=False, coloraxis_showscale=False, margin=dict(l=10, r=40, t=50, b=10))
    st.plotly_chart(fig_rank, use_container_width=True)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.caption(
    "Data sourced from the [GitHub REST API](https://docs.github.com/en/rest). "
    "Unauthenticated requests are limited to 60/h — add a token for 5,000/h. "
    "Large repos may take a few seconds to load; results are cached for 5 minutes."
)
