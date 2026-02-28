"""nba_menu.py

Convenience launcher for the NBA slate menu.

This keeps your muscle memory consistent with `nfl_menu.py`:
- NFL: python nfl_menu.py
- NBA: python nba_menu.py

Internally, this uses the ASCII-safe, deterministic workflow menu:
`risk_first_slate_menu.py`.
"""

from __future__ import annotations


def main() -> None:
    # Import lazily so this file stays fast and doesn't pull heavy deps on import.
    from risk_first_slate_menu import main as _nba_menu_main

    _nba_menu_main()


if __name__ == "__main__":
    main()
