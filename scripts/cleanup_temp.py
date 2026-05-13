#!/usr/bin/env python3
"""Cleanup temp scripts from repo."""
import os, glob
repo = r"D:\hotel gestionale"
temp_patterns = [
    os.path.join(repo, "scripts_fix_seed.py"),
    os.path.join(repo, "backend", "scripts", "check_db.py"),
    os.path.join(repo, "backend", "scripts", "check_db_state.py"),
    os.path.join(repo, "backend", "scripts", "quick_check.py"),
    os.path.join(repo, "backend", "scripts", "verify_seed.py"),
    os.path.join(repo, "backend", "scripts", "verify_seed2.py"),
    os.path.join(repo, "backend", "scripts", "fix_users.py"),
    os.path.join(repo, "backend", "scripts", "populate_history.py"),
    os.path.join(repo, "backend", "scripts", "setup_local.py"),
]
for p in temp_patterns:
    if os.path.exists(p):
        os.remove(p)
        print(f"Removed: {p}")
print("Cleanup done")