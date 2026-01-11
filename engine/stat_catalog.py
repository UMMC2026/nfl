from engine.stat_catalog import STAT_CATALOG

meta = STAT_CATALOG.get(stat)

if not meta:
    reject("Unknown stat")

if meta["class"] == "TIME_BOXED":
    reject("Display-only stat")
