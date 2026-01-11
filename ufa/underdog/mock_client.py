from typing import List, Dict, Any

class UnderdogMockClient:
    """
    A safe stub client that avoids scraping Underdog.
    You can load your daily lines from JSON/CSV exported by you, then feed into CLI/API.
    """
    def __init__(self, lines: List[Dict[str, Any]] | None=None):
        self._lines = lines or []

    def load_lines(self, lines: List[Dict[str, Any]]) -> None:
        self._lines = lines

    def get_lines(self) -> List[Dict[str, Any]]:
        return list(self._lines)
