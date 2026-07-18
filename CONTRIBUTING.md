# Contributing

Thank you for considering a contribution to the GitHub Analytics Dashboard!

## Getting started

```bash
git clone https://github.com/UshaAIDev/crispy.git
cd crispy
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Project layout

```
crispy/
├── app.py          # Streamlit UI — page layout and chart rendering
├── github_api.py   # GitHub REST API wrappers (cached)
├── scorer.py       # Contributor scoring and ranking logic
├── requirements.txt
└── README.md
```

## Making changes

1. Create a feature branch: `git checkout -b feat/my-improvement`
2. Make your changes and verify the app still launches.
3. Open a Pull Request against `main` with a clear description.

## Code style

- Follow [PEP 8](https://peps.python.org/pep-0008/).
- Add docstrings to new public functions.
- Keep Streamlit UI code in `app.py`; keep data/logic code in separate modules.

## Reporting issues

Please open a GitHub Issue with steps to reproduce and the expected vs. actual behaviour.
