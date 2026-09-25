# Contributing to samvit

Thanks for wanting to help. This document keeps the repo small,
dependency-free, and honest about what each claim means.

## Ground rules

- Keep the package **standard-library only** and **Python 3.9 compatible**.
- Open an issue before opening a pull request so a change is discussed once
  and implemented once.
- Every behavioral constraint (VISION, ULTRON, profiles, privacy) needs a
  matching check in `tests/test_samvit.py`.
- Run the suite before pushing:
  ```sh
  python -m pytest
  ```

## Adding a constraint or profile

1. Implement the behavior in the relevant module (e.g. `vision`, `ultron`,
   `persona`).
2. Add tests that lock the exact behavior and the honest boundaries (no
   sentience, no errorless claims).
3. Document it: README, and the requirements spec if it affects system
   constraints (C1-C12).

## Reporting bugs

Search the issues list first. When you open a new issue, include the command
you ran, the Python version, and the first ~30 lines of any error.

## Support expectations

This is maintained by a single maintainer in spare time. Issues are the
channel for help; expect answers within a week, not minutes.

## License

By contributing you agree that your contributions are licensed under the same
MIT license as the rest of the project.