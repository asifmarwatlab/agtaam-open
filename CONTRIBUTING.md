# Contributing

Thanks for helping! This is a small library, so the rules are short.

1. **Open an issue first** for anything bigger than a typo, so we agree on the idea.
2. Fork, make a branch, keep the change focused.
3. Add or update a test in `tests/` (every behaviour in the README has one).
4. Run `python -m pytest` - everything must pass.
5. Open a pull request and say *what* changed and *why*.

Ground rules
- The core (`agtaam_project/store.py`) must stay **pure Python**, standard library only.
  Anything that needs Qt belongs in `agtaam_project/qt.py`.
- Never change what an existing `.agtaam` file means without bumping `FORMAT_VERSION`
  and keeping older files readable.
