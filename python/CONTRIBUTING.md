# Contributing to uxchannel 0.1.0

1. Use Python 3.10+.
2. `pip install -e ".[dev]"` if extras exist; otherwise `pip install -e .` and `pip install pytest`.
3. Run `pytest -q` before opening a PR.
4. Product API lives on `Channel` (`view` / `on` / `ok` / `err`) — see docs/start/GLOSSARY.md.
5. Rebuild the book after doc changes: `python scripts/build_ux_channel_book_pdf.py`.
