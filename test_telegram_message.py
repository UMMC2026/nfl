#!/usr/bin/env python3
"""Test the Telegram message parser."""

from send_telegram import get_latest_mc_file, parse_mc_file

mc_file = get_latest_mc_file()
print(f"📄 Latest MC file: {mc_file.name}\n")

msg = parse_mc_file(str(mc_file))
print("=" * 60)
print("PREVIEW MESSAGE:")
print("=" * 60)
print(msg)
print("\n" + "=" * 60)
print(f"Message length: {len(msg)} characters")
print("=" * 60)
