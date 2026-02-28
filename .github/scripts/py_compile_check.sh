#!/bin/bash
# Fail on any error
set -e

# Find all Python scripts in tools/ and root, check with py_compile
echo "Checking Python entry-point structure with py_compile..."
find tools . -maxdepth 2 -name "*.py" | while read -r file; do
    echo "Compiling $file..."
    python -m py_compile "$file"
done
echo "All Python scripts compiled successfully."
