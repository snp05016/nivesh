import os
import re
import argparse

parser = argparse.ArgumentParser(description='Scan frontend codebase for violations.')
parser.add_argument('--root', default='ios/StockApp/stockme/stockme/', help='Root directory to scan.')
parser.add_argument('--out', default='.agent-runs/frontend-scan/frontend_findings.md', help='Output file path for findings.')
args = parser.parse_args()

dir_path = args.root

violations = []

def add_violation(file, line_num, desc, line):
    violations.append(f"- **{file}:{line_num}** - {desc}\n  `{line.strip()}`")

for root, _, files in os.walk(dir_path):
    for file in files:
        if file.endswith('.swift'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            has_button = False
            has_haptic = False
            
            for i, line in enumerate(lines):
                line_num = i + 1
                
                # Raw hex colors
                if re.search(r'Color\(\s*hex:', line):
                    add_violation(path, line_num, 'Raw hex color used instead of Theme token', line)
                
                # Hardcoded padding
                if re.search(r'\.padding\(\s*[1-9]\d*\s*\)', line):
                    add_violation(path, line_num, 'Hardcoded pixel padding instead of Theme.Spacing', line)
                
                # Hardcoded spacing
                if re.search(r'spacing:\s*[1-9]\d*', line):
                    add_violation(path, line_num, 'Hardcoded spacing instead of Theme.Spacing', line)
                    
                # Hardcoded width/height
                if re.search(r'width:\s*[1-9]\d*', line) or re.search(r'height:\s*[1-9]\d*', line):
                    add_violation(path, line_num, 'Hardcoded pixel width/height', line)
                
                # Raw fonts
                if re.search(r'\.system\(\s*(size|weight):', line) or re.search(r'\.font\(\s*\.system', line):
                    # Exclude Theme.swift itself because it defines them
                    if not path.endswith('Theme.swift'):
                        add_violation(path, line_num, 'Raw system font used instead of Theme.engravedSerif etc.', line)
                
                # Million/Billion
                if re.search(r'(?i)\b(million|billion)\b', line):
                    # Ignore Comments and Extensions.swift/IndianFormatter.swift which are utilities
                    if not line.strip().startswith('//') and not path.endswith('Extensions.swift') and not path.endswith('IndianFormatter.swift'):
                        add_violation(path, line_num, 'Use of Million/Billion instead of Lakhs/Crores', line)
                        
                # Haptics check prep
                if re.search(r'\bButton\b|\.onTapGesture', line):
                    has_button = True
                if re.search(r'HapticManager|EKPressStyle', line):
                    has_haptic = True
                    
            if has_button and not has_haptic:
                violations.append(f"- **{path}** - Contains Button/onTapGesture but missing HapticManager/EKPressStyle entirely in the file.")

out_path = args.out
out_dir = os.path.dirname(out_path)
if out_dir:
    os.makedirs(out_dir, exist_ok=True)
with open(out_path, 'w') as f:
    f.write("# Frontend Codebase Scanner Findings\n\n")
    for v in violations:
        f.write(v + "\n")

print(f"Found {len(violations)} violations.")
