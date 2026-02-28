"""Temporary smoke test for Matchup Memory menu.

Runs menu.run_matchup_memory_menu() with scripted inputs to ensure the
interactive flow doesn't crash on gate wiring.

Safe to delete.
"""

import builtins

import menu


def main() -> None:
    # Force manual flow regardless of active slate state
    menu._active_slate_path = lambda: None  # type: ignore[assignment]

    seq = iter(
        [
            "sabonis",  # player search
            "2",        # select Domantas
            "cle",      # opponent
            "threes",   # stat
            "",         # pause
        ]
    )

    def fake_input(prompt: str = "") -> str:
        try:
            v = next(seq)
        except StopIteration:
            v = ""
        print(prompt + v)
        return v

    builtins.input = fake_input

    menu.run_matchup_memory_menu(settings={})


if __name__ == "__main__":
    main()
