import os
import re

IOS_DIR = "/Users/saumya/Desktop/nivesh/ios/StockApp"

def fix_swift_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # 1. Add .controlSize(.small) to Picker and Menu if not present
    # But wait, Picker or Menu spans multiple lines usually.
    # It's safer to just do simple regex replacements on known patterns.

    # 2. Text(IndianFormatter... -> add minimumScaleFactor
    # A bit risky to regex everything. Let's find specific text elements.

