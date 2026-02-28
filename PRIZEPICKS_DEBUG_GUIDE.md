# PrizePicks scraping — debug guide

## What this is

PrizePicks changes their front-end often (React + hashed class names). When body-text scraping returns **0 props**, it usually means:

- the page is gated (login / geo / captcha), or
- props render inside nested components and your plain `body.inner_text()` doesn’t surface the useful content.

This repo now includes two tools to make this deterministic:

- `scripts/inspect_prizepicks.py` — selector inspector (counts + samples)
- `src/parsers/prizepicks_parser.py` — DOM-based extraction with debug artifacts

## Run the selector inspector (recommended)

Run from the repo venv:

- `scripts/inspect_prizepicks.py`

It will:

1. Open PrizePicks in a visible persistent-profile browser
2. Attempt to click `NBA` (best-effort)
3. Scan a set of likely selectors (projection/card/stat)
4. Print counts + sample text
5. Save:
   - `data/debug/prizepicks_inspection_<timestamp>.txt`
   - `data/debug/prizepicks_inspection_<timestamp>.png`
   - `data/debug/prizepicks_inspection_<timestamp>.html`

## If the parser finds 0 props

`src/parsers/prizepicks_parser.py` will automatically save:

- `data/debug/prizepicks_debug_<sport>_<timestamp>.png`
- `data/debug/prizepicks_debug_<sport>_<timestamp>.html`
- `data/debug/prizepicks_debug_<sport>_<timestamp>.meta.txt`

These artifacts make it clear whether the page is:

- logged out / gated
- a blank React shell
- showing props but with different container selectors

## How to update selectors

If the inspector shows a selector with meaningful samples (player + stat + line), add it near the top of:

- `PrizePicksParser.card_selectors` in `src/parsers/prizepicks_parser.py`

Prefer selectors that are:

- `data-*` attributes (usually more stable than classes)
- broad partial matches like `[data-test*="projection"]`

## Notes on direction

PrizePicks is inherently **More/Less**. The UI doesn’t always include direction text within each card’s accessible text.

For pipeline compatibility (active slate expects a direction), the PrizePicks parser emits **both** directions (`higher` and `lower`) for each detected (player, stat, line).

This is ingestion-only behavior; it does not recommend picks.
