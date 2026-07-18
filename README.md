# 📊 GitHub Analytics Dashboard

A lightweight Streamlit dashboard that visualises GitHub repository activity:

| Metric | Description |
|---|---|
| **Commit % by contributor** | Pie chart + table showing each contributor's share of commits in the chosen date range |
| **Builds per day** | Stacked bar chart of GitHub Actions workflow-run conclusions (success / failure / other) per day |
| **Best contributor ranking** | Scored leaderboard combining commit volume, all-time share, and recency |

## Quick start

### 1 · Clone & install

```bash
git clone https://github.com/UshaAIDev/crispy.git
cd crispy
pip install -r requirements.txt
```

### 2 · (Optional) Set a GitHub token

Without a token the GitHub API is limited to **60 requests/hour**.  
With a token the limit rises to **5,000 requests/hour**.

```bash
export GITHUB_TOKEN=ghp_yourPersonalAccessToken
```

Alternatively, paste the token in the **GitHub Token** field in the dashboard sidebar.

### 3 · Run

```bash
streamlit run app.py
```

Open the URL shown in the terminal (default: `http://localhost:8501`).

---

## Configuration

All options are available in the sidebar at runtime:

| Setting | Default | Description |
|---|---|---|
| GitHub Token | *(env `GITHUB_TOKEN`)* | Optional PAT for higher rate limit |
| Repository Owner | `microsoft` | GitHub org / user |
| Repository Name | `vscode` | GitHub repo name |
| Date Range | Last 30 days | 7 / 30 / 90 days or custom |

---

## How the best-contributor score works

```
score = 0.5 × (commits_in_range / max_commits_in_range)
      + 0.3 × (all_time_commits  / total_all_time_commits)
      + 0.2 × recency_flag          # 1 if committed in last 7 days, 0 otherwise
```

Scores are normalised to **0–100**.  
The formula rewards consistent volume, long-term commitment, and recent activity equally.

---

## Limitations

* **GitHub Actions only** — the Builds per Day section relies on GitHub Actions workflow runs.  
  Repos without Actions (or with Actions disabled) will show no build data.
* **API pagination cap** — very large repos (e.g. `microsoft/vscode` over 90 days) may hit  
  rate limits before all commits are fetched.  Use a GitHub token to increase the limit.
* **Unauthenticated limit** — 60 API requests/hour.  Each section makes multiple paginated  
  calls, so a narrow date range is recommended without a token.
* **Contributor endpoint** — the `/contributors` endpoint returns all-time statistics and  
  does not support date filtering.  The "All-time commits" column therefore reflects the  
  full repository history, not just the selected range.
* **Anonymous commits** — commits without a linked GitHub account are grouped under their  
  Git author name and will not match the all-time contributor list.

---

## Dependencies

See [`requirements.txt`](requirements.txt):

```
streamlit>=1.35.0
requests>=2.31.0
pandas>=2.0.0
plotly>=5.20.0
```
