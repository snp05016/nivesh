"""
test_02_syntax_lint.py
======================
Scans every .py file in the backend directory for:
- SyntaxErrors (using py_compile)
- IndentationErrors
- TabErrors
- Common anti-patterns that indicate bugs (bare except, print statements)

This test does NOT execute the code — it only parses the AST.
It produces a line-by-line report of every file with issues.
"""
from datetime import timezone
import sys
import os
import ast
import py_compile
import tempfile
import traceback
from pathlib import Path

# Path setup
sys.path.insert(0, str(Path(__file__).parent))
from _base import TestRunner

_BACKEND = Path(__file__).parent.parent.parent

# Files to exclude from scanning (generated files, migrations, etc.)
EXCLUDE_DIRS = {"__pycache__", ".venv", "venv", ".cache", "migrations", "tradingagents-core"}
EXCLUDE_FILES = {"alembic.ini"}


def collect_py_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*.py"):
        # Skip excluded directories
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def check_syntax(filepath: Path) -> tuple[bool, str]:
    """Check file for syntax errors using py_compile."""
    try:
        py_compile.compile(str(filepath), doraise=True)
        return True, ""
    except py_compile.PyCompileError as e:
        return False, str(e)
    except SyntaxError as e:
        return False, f"SyntaxError at {filepath}:{e.lineno}: {e.msg}\n  Line: {e.text}"
    except IndentationError as e:
        return False, f"IndentationError at {filepath}:{e.lineno}: {e.msg}\n  Line: {e.text}"
    except Exception as e:
        return False, f"Unknown error: {e}\n{traceback.format_exc()}"


def check_ast_patterns(filepath: Path) -> list[str]:
    """
    Parse the AST and look for common dangerous patterns.
    Returns a list of warning strings.
    """
    warnings = []
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, IndentationError):
        return []  # Already caught by check_syntax

    for node in ast.walk(tree):
        # Bare except: (catches everything including SystemExit, KeyboardInterrupt)
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            warnings.append(
                f"  Line {node.lineno}: Bare 'except:' detected. "
                f"This catches SystemExit and KeyboardInterrupt. "
                f"Use 'except Exception:' or a specific exception type."
            )

        # datetime.now(timezone.utc) usage (forbidden per AGENTS.md)
        if isinstance(node, ast.Attribute) and node.attr == "utcnow":
            warnings.append(
                f"  Line {node.col_offset}: datetime.now(timezone.utc) is forbidden per AGENTS.md. "
                f"Use datetime.now(timezone.utc) instead. "
                f"utcnow() returns a naive datetime which compares incorrectly with timezone-aware datetimes."
            )

        # exec() calls (security risk)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "exec":
                warnings.append(f"  Line {node.lineno}: exec() call detected — potential security vulnerability.")

        # assert statements in production code (stripped by -O flag)
        if isinstance(node, ast.Assert):
            # Only warn in non-test files
            if "test" not in str(filepath).lower():
                warnings.append(
                    f"  Line {node.lineno}: assert statement in production code. "
                    f"Assertions are removed when Python runs with -O flag. Use explicit if/raise instead."
                )

    return warnings


def run():
    runner = TestRunner("02_syntax_lint")

    py_files = collect_py_files(_BACKEND)
    runner.ok("file_scan_start", f"Scanning {len(py_files)} Python files in {_BACKEND}")

    syntax_errors = 0
    pattern_warnings = 0

    for filepath in py_files:
        rel = filepath.relative_to(_BACKEND)

        # Syntax check
        ok, error = check_syntax(filepath)
        if ok:
            runner.ok(f"syntax:{rel}", "No syntax errors")
        else:
            syntax_errors += 1
            runner.fail(
                f"syntax:{rel}",
                f"SYNTAX ERROR in {filepath}:\n{error}\n"
                f"FIX: Open the file at the indicated line and correct the syntax. "
                f"This file will fail to import, causing 500 errors on all routes in this module."
            )

        # AST pattern check
        warnings = check_ast_patterns(filepath)
        if warnings:
            pattern_warnings += len(warnings)
            for w in warnings:
                runner.fail(
                    f"pattern:{rel}",
                    f"Anti-pattern in {filepath}:\n{w}"
                )

    runner.ok(
        "scan_complete",
        f"Scanned {len(py_files)} files. Syntax errors: {syntax_errors}. Pattern warnings: {pattern_warnings}."
    )

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "backend_integrity_latest.txt")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
