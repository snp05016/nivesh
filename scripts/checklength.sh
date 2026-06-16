#!/usr/bin/env bash
cd ..
git ls-files | grep -E '\.(swift|sh|py)$' | xargs wc -l 2> /dev/null | tail -n 1
cd scripts/
