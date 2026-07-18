"""
github_api.py
-------------
Thin wrapper around the GitHub REST API.

All functions are decorated with @st.cache_data so repeated calls within
the same Streamlit session are served from cache (TTL = 5 minutes).
"""

from __future__ import annotations

import streamlit as st
import requests

GITHUB_API = "https://api.github.com"


def build_headers(token: str | None) -> dict:
    """Return request headers, optionally including a ******"""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    return headers


def _get(url: str, params: dict, token: str | None) -> requests.Response:
    return requests.get(url, headers=build_headers(token), params=params, timeout=20)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_commits(
    owner: str,
    repo: str,
    since_iso: str,
    until_iso: str,
    token: str | None,
) -> list[dict]:
    """Return all commits between *since_iso* and *until_iso* (ISO 8601)."""
    commits: list[dict] = []
    page = 1
    while True:
        resp = _get(
            f"{GITHUB_API}/repos/{owner}/{repo}/commits",
            {"since": since_iso, "until": until_iso, "per_page": 100, "page": page},
            token,
        )
        if resp.status_code == 409:
            break  # empty repository
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
def fetch_workflow_runs(
    owner: str,
    repo: str,
    since_iso: str,
    until_iso: str,
    token: str | None,
) -> list[dict]:
    """Return completed workflow runs created within the given date range."""
    runs: list[dict] = []
    page = 1
    created_query = f"{since_iso[:10]}..{until_iso[:10]}"
    while True:
        resp = _get(
            f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs",
            {
                "created": created_query,
                "per_page": 100,
                "page": page,
                "status": "completed",
            },
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
def fetch_contributors(
    owner: str,
    repo: str,
    token: str | None,
) -> list[dict]:
    """Return all-time contributor list from GitHub (sorted by contributions desc)."""
    contributors: list[dict] = []
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


def fetch_rate_limit(token: str | None) -> dict:
    """Return current API rate-limit info (empty dict on failure)."""
    try:
        resp = requests.get(
            f"{GITHUB_API}/rate_limit",
            headers=build_headers(token),
            timeout=10,
        )
        if resp.ok:
            return resp.json().get("rate", {})
    except Exception:
        pass
    return {}
