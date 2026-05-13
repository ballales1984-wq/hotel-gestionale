#!/usr/bin/env python3
"""
Database backup script with rotation (daily/weekly/monthly).
Supports SQLite and PostgreSQL (via pg_dump).
"""

import os
import sys
import shutil
import subprocess
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path to import settings
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    from app.config import get_settings
except ImportError:
    print("Error: Could not import backend settings. Make sure you're running from the project root.")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description='Database backup with rotation')
    parser.add_argument('--db-url', default=os.getenv('DATABASE_URL'), help='Database connection URL')
    parser.add_argument('--backup-dir', default=os.getenv('BACKUP_DIR', './backups'), help='Backup directory')
    parser.add_argument('--retention-daily', type=int, default=7, help='Keep daily backups for N days')
    parser.add_argument('--retention-weekly', type=int, default=4, help='Keep weekly backups for N weeks')
    parser.add_argument('--retention-monthly', type=int, default=12, help='Keep monthly backups for N months')
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def generate_backup_filename() -> str:
    """Generate timestamped backup filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"backup_{timestamp}.db"


def get_db_path_from_url(db_url: str) -> Path:
    """Extract SQLite database file path from URL."""
    if not db_url.startswith("sqlite"):
        raise ValueError(f"This script supports SQLite only. URL: {db_url}")

    # Strip driver: sqlite+aiosqlite:/// -> sqlite:///
    if "+" in db_url:
        protocol, rest = db_url.split("+", 1)
        if "://" in rest:
            _, url_part = rest.split("://", 1)
            db_url = f"sqlite://{url_part}" if url_part.startswith('/') else f"sqlite:///{url_part}"

    # Extract path
    if db_url.startswith("sqlite:///"):
        path = db_url[9:]
    elif db_url.startswith("sqlite:////"):
        path = db_url[10:]
    else:
        raise ValueError(f"Unsupported SQLite URL format: {db_url}")

    # Resolve relative paths
    if not os.path.isabs(path):
        # Try project root then backend
        attempt1 = Path.cwd() / path
        if not attempt1.exists():
            backend_path = Path.cwd() / 'backend' / path.lstrip('./')
            if backend_path.exists():
                path = backend_path
            else:
                path = attempt1
        else:
            path = attempt1

    return Path(os.path.normpath(path))


def backup_sqlite_db(db_path: Path, backup_path: Path) -> bool:
    """Copy SQLite database file."""
    print(f"Backing up SQLite DB: {db_path} -> {backup_path}")
    try:
        if not db_path.exists():
            print(f"Error: Source DB not found: {db_path}")
            return False
        shutil.copy2(db_path, backup_path)
        print("Backup completed successfully.")
        return True
    except Exception as e:
        print(f"Error copying database: {e}")
        return False


def backup_postgres_db(db_url: str, backup_path: Path) -> bool:
    """Use pg_dump to export PostgreSQL database."""
    print(f"Backing up PostgreSQL DB via pg_dump -> {backup_path}")
    try:
        # pg_dump requires connection URL or params
        # For URL format: postgresql://user:pass@host:port/dbname
        cmd = [
            'pg_dump',
            '--format=c',  # custom format
            '--file', str(backup_path),
            db_url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"pg_dump error: {result.stderr}")
            return False
        print("pg_dump completed successfully.")
        return True
    except FileNotFoundError:
        print("Error: pg_dump not found. Install PostgreSQL client tools.")
        return False
    except Exception as e:
        print(f"Error during pg_dump: {e}")
        return False


def rotate_backups(backup_dir: Path, retention_daily: int, retention_weekly: int, retention_monthly: int) -> None:
    """
    Sophisticated rotation:
      - Keep daily backups for the last N days
      - Keep weekly backups (one per week, on Sunday) for last N weeks
      - Keep monthly backups (first day of month) for last N months
    """
    backup_files = list(backup_dir.glob("backup_*.db"))
    if not backup_files:
        return

    now = datetime.now()
    cutoff_daily = now - timedelta(days=retention_daily)

    # Classify backups by date parsed from filename
    weekly_candidates = []   # (file, date) for Sundays
    monthly_candidates = [] # (file, date) for 1st of month

    for f in backup_files:
        try:
            # backup_YYYYMMDD_HHMMSS.db
            parts = f.stem.split('_')
            if len(parts) < 2:
                continue
            date_str = parts[1]  # YYYYMMDD
            file_date = datetime.strptime(date_str, "%Y%m%d")
            # Weekly: Sunday
            if file_date.weekday() == 6:  # Monday=0, Sunday=6
                weekly_candidates.append((f, file_date))
            # Monthly: first day of month
            if file_date.day == 1:
                monthly_candidates.append((f, file_date))
        except Exception:
            continue

    # Sort descending by date
    weekly_candidates.sort(key=lambda x: x[1], reverse=True)
    monthly_candidates.sort(key=lambda x: x[1], reverse=True)

    keep_weekly_files = {f for f, _ in weekly_candidates[:retention_weekly]}
    keep_monthly_files = {f for f, _ in monthly_candidates[:retention_monthly]}

    # Delete old backups not needed for any tier
    deleted_count = 0
    for f in backup_files:
        try:
            parts = f.stem.split('_')
            if len(parts) < 2:
                continue
            file_date = datetime.strptime(parts[1], "%Y%m%d")
        except Exception:
            # If cannot parse, keep it (safer)
            continue

        keep = False
        # Daily tier: files within retention window
        if file_date >= cutoff_daily:
            keep = True
        # Weekly tier: explicitly marked
        if f in keep_weekly_files:
            keep = True
        # Monthly tier: explicitly marked
        if f in keep_monthly_files:
            keep = True

        if not keep:
            try:
                f.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"Error removing {f.name}: {e}")

    print(f"Rotation complete. Deleted {deleted_count} old backup(s).")


def main():
    args = parse_args()

    db_url = args.db_url or os.getenv('DATABASE_URL')
    if not db_url:
        print("Error: DATABASE_URL not provided. Set env var or use --db-url.")
        sys.exit(1)

    backup_dir = Path(args.backup_dir)
    ensure_dir(backup_dir)

    backup_filename = generate_backup_filename()
    backup_path = backup_dir / backup_filename

    # Choose backend
    if db_url.startswith("sqlite"):
        success = backup_sqlite_db(get_db_path_from_url(db_url), backup_path)
    elif db_url.startswith("postgresql") or db_url.startswith("postgres"):
        success = backup_postgres_db(db_url, backup_path)
    else:
        print(f"Error: Unsupported database type: {db_url}")
        sys.exit(1)

    if success:
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        print(f"Backup saved: {backup_path} ({size_mb:.2f} MB)")

        # Run rotation
        rotate_backups(
            backup_dir,
            args.retention_daily,
            args.retention_weekly,
            args.retention_monthly,
        )
    else:
        print("Backup failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()