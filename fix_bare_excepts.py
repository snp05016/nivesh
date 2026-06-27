import os
import re

ROUTERS_DIR = "/Users/saumya/Desktop/nivesh-agy-fix-gh-issues-batch-4/backend/routers"

def fix_bare_excepts(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    out_lines = []
    i = 0
    modified = False
    while i < len(lines):
        line = lines[i]
        
        # Match 'except Exception:' with any leading whitespace
        match = re.match(r'^(\s*)except Exception:\s*$', line)
        if match:
            indent = match.group(1)
            # Check if next line is 'pass'
            if i + 1 < len(lines):
                next_line = lines[i+1]
                if re.match(r'^\s*pass\s*$', next_line):
                    out_lines.append(f"{indent}except Exception as e:\n")
                    out_lines.append(f"{indent}    import logging\n")
                    out_lines.append(f"{indent}    logging.warning(f\"Swallowed exception: {{e}}\")\n")
                    i += 2
                    modified = True
                    continue
            
            # If not pass, still change to 'except Exception as e:' and log it before the next statement
            out_lines.append(f"{indent}except Exception as e:\n")
            out_lines.append(f"{indent}    import logging\n")
            out_lines.append(f"{indent}    logging.warning(f\"Caught exception: {{e}}\")\n")
            i += 1
            modified = True
            continue
            
        out_lines.append(line)
        i += 1
        
    if modified:
        with open(filepath, 'w') as f:
            f.writelines(out_lines)
        print(f"Fixed bare excepts in {filepath}")

for root, _, files in os.walk(ROUTERS_DIR):
    for f in files:
        if f.endswith(".py"):
            fix_bare_excepts(os.path.join(root, f))
