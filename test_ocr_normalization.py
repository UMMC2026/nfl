#!/usr/bin/env python3
"""Test script for OCR line value normalization."""

from parse_results_image import normalize_line_value

# Test cases
test_cases = [
    (555.0, "rebs+asts", 5.5),   # Double-5 OCR error
    (555, "rebs+asts", 5.5),     # Integer version
    (55, "rebs+asts", 5.5),      # Single-5 OCR error
    (5.5, "rebs+asts", 5.5),     # Already correct
    (125, "points", 12.5),       # Standard decimal fix
    (295, "pts+reb+ast", 29.5),  # PRA decimal fix
    (235, "points", 23.5),       # Another standard case
    (445, "pts+reb+ast", 44.5),  # Higher PRA
    (85, "rebounds", 8.5),       # Rebounds
]

print("OCR Line Value Normalization Tests")
print("=" * 50)

all_passed = True
for value, stat, expected in test_cases:
    result = normalize_line_value(value, stat)
    status = "✓" if result == expected else "✗"
    if result != expected:
        all_passed = False
    print(f"{status} normalize_line_value({value}, '{stat}') = {result} (expected {expected})")

print("=" * 50)
if all_passed:
    print("All tests PASSED")
else:
    print("Some tests FAILED")
