import os

files_to_fix = [
    "/Users/saumya/Desktop/nivesh-agy-fix-gh-issues-batch-4/backend/main.py",
    "/Users/saumya/Desktop/nivesh-agy-fix-gh-issues-batch-4/backend/core/dashboard_state.py",
    "/Users/saumya/Desktop/nivesh-agy-fix-gh-issues-batch-4/backend/helpers.py"
]

for filepath in files_to_fix:
    if not os.path.exists(filepath):
        continue
        
    with open(filepath, 'r') as f:
        content = f.read()

    # We want to replace the swallowed exception in _log_token_usage
    old_except = "    except Exception:\n        pass\n    with _dash_lock:"
    new_except = "    except Exception as e:\n        import logging\n        logging.warning(f\"Failed to log token usage: {e}\")\n    with _dash_lock:"
    
    if old_except in content:
        content = content.replace(old_except, new_except)
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Fixed {filepath}")
    else:
        # handle main.py logic if indentation is different
        old_except_2 = "    except Exception:\n        pass"
        new_except_2 = "    except Exception as e:\n        import logging\n        logging.warning(f\"Failed to log token usage: {e}\")"
        
        # Make sure we only replace it inside _log_token_usage.
        # So let's locate _log_token_usage first.
        import re
        def replace_in_func(m):
            func_body = m.group(0)
            func_body = func_body.replace(old_except_2, new_except_2)
            return func_body
            
        content = re.sub(r'def _log_token_usage.*?with _dash_lock', replace_in_func, content, flags=re.DOTALL)
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Fixed {filepath} via regex")

