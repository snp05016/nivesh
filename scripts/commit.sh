#!/bin/bash
# Nivesh commit helper
# Usage: ./commit.sh "your commit message"

if [ -z "$1" ]; then
    echo "Usage: ./commit.sh \"commit message\""
    exit 1
fi

git add -A
git commit -m "$1"
echo "Committed. Run 'git push' when ready."
