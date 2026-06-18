import os
import re

IOS_DIR = "/Users/saumya/Desktop/nivesh/ios/StockApp/stockme"

def fix_ui():
    count_files = 0
    
    for root, dirs, files in os.walk(IOS_DIR):
        for file in files:
            if not file.endswith(".swift"):
                continue
                
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
            original = content
            lines = content.split('\n')
            new_lines = []
            
            i = 0
            while i < len(lines):
                line = lines[i]
                
                # Fix frame heights for expanding containers
                if ".frame(" in line and "height:" in line and "minHeight" not in line and "width:" not in line:
                    if "maxWidth: .infinity" in line or "maxWidth:" in line:
                        line = re.sub(r'height:\s*([0-9\.]+)', r'minHeight: \1', line)

                new_lines.append(line)
                
                # Fix Text shrinking (for prices, percentages, generic text using IndianFormatter)
                if "Text(IndianFormatter." in line:
                    j = i + 1
                    already_has_limit = False
                    while j < len(lines) and j < i + 5:
                        next_line_stripped = lines[j].strip()
                        if ".lineLimit" in next_line_stripped or ".minimumScaleFactor" in next_line_stripped:
                            already_has_limit = True
                            break
                        if not next_line_stripped.startswith("."):
                            # If it's not a modifier, we stop looking ahead
                            break
                        j += 1
                        
                    if not already_has_limit:
                        indent = " " * (len(line) - len(line.lstrip()))
                        # Insert modifiers right after the Text line
                        new_lines.append(indent + ".lineLimit(1)")
                        new_lines.append(indent + ".minimumScaleFactor(0.6)")

                i += 1
                
            content = "\n".join(new_lines)
            
            # Global App tweaks
            if file == "stockmeApp.swift":
                if ".pickerStyle(.menu)" not in content:
                    content = content.replace(
                        ".buttonStyle(PlainButtonStyle())",
                        ".buttonStyle(PlainButtonStyle())\n                .pickerStyle(.menu)\n                .controlSize(.small)"
                    )
                    # Also make sure PlainButtonStyle is there if we haven't added it yet
                    if ".buttonStyle(PlainButtonStyle())" not in content:
                        content = content.replace(
                            ".preferredColorScheme(darkMode ? .dark : nil)",
                            ".preferredColorScheme(darkMode ? .dark : nil)\n                .buttonStyle(PlainButtonStyle())\n                .pickerStyle(.menu)\n                .controlSize(.small)"
                        )
            
            if content != original:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                count_files += 1
                print(f"Fixed: {filepath}")

    print(f"Total files updated: {count_files}")

if __name__ == "__main__":
    fix_ui()
