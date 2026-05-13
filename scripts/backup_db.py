#!/usr/bin/env python3
"""
Database backup script for SQLite.
Copies the database file with rotation.
"""

import os
import sys
import shutil
import datetime
from pathlib import Path

# Add backend to path to import settings
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    from app.config import get_settings
except ImportError:
    print("Error: Could not import backend settings. Make sure you're running from the project root.")
    sys.exit(1)

def get_db_path():
    """Extract SQLite database path from settings."""
    settings = get_settings()
    db_url = settings.database_url
    
    # Check if we're using SQLite
    if not db_url.startswith("sqlite"):
        print(f"Error: This script is designed for SQLite databases. Current URL: {db_url}")
        print("Set DATABASE_URL environment variable to a SQLite connection string.")
        sys.exit(1)
    
    # Extract path from sqlite:/// or sqlite://// (handle +aiosqlite etc)
    # Remove driver prefix (sqlite+aiosqlite:/// -> sqlite:///)
    if "+" in db_url:
        # Split on + and take the first part, then reconstruct
        protocol, rest = db_url.split("+", 1)
        if "://" in rest:
            driver_part, url_part = rest.split("://", 1)
            db_url = f"{protocol}://{url_part}"
        else:
            db_url = rest
    
    # Now handle standard sqlite URL formats
    if db_url.startswith("sqlite:///"):
        # Relative or absolute path (3 slashes)
        db_path = db_url[9:]  # Remove sqlite:///
    elif db_url.startswith("sqlite:////"):
        # Absolute path with 4 slashes
        db_path = db_url[10:]  # Remove sqlite:////
    else:
        print(f"Error: Unable to parse SQLite URL: {db_url}")
        sys.exit(1)
    
    # Handle relative paths - make them relative to project root
    if not os.path.isabs(db_path):
        # The path is relative to where the application runs
        # Try resolving relative to current directory first
        attempt1 = os.path.join(os.getcwd(), db_path)
        # If that doesn't exist, try relative to backend directory (common case)
        if not os.path.exists(attempt1):
            backend_path = os.path.join(os.getcwd(), 'backend', db_path.lstrip('./'))
            if os.path.exists(backend_path):
                db_path = backend_path
            else:
                db_path = attempt1
        else:
            db_path = attempt1
    
    # Normalize the path to remove any . or .. components
    db_path = os.path.normpath(db_path)
    
    return db_path

def create_backup_dir():
    """Create backup directory if it doesn't exist."""
    backup_dir = Path('./backups')
    backup_dir.mkdir(exist_ok=True)
    return backup_dir

def generate_backup_filename():
    """Generate a timestamped backup filename."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"backup_{timestamp}.db"

def backup_sqlite_db(db_path, backup_path):
    """Copy SQLite database file."""
    print(f"Backing up SQLite database from {db_path} to {backup_path}...")
    
    try:
        # Ensure the source database exists
        if not os.path.exists(db_path):
            print(f"Error: Source database not found: {db_path}")
            return False
        
        # Copy the database file
        shutil.copy2(db_path, backup_path)
        print("Backup completed successfully!")
        return True
    except Exception as e:
        print(f"Error copying database: {e}")
        return False

def rotate_backups(backup_dir, keep_daily=7, keep_weekly=4, keep_monthly=6):
    """Rotate backup files, keeping specified number of daily, weekly, monthly backups."""
    backup_files = list(backup_dir.glob("backup_*.db"))
    if not backup_files:
        return
    
    # Sort by modification time (newest first)
    backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    # For now, implement simple rotation keeping most recent backups
    # TODO: Implement sophisticated rotation based on daily/weekly/monthly policies
    # For simplicity, we keep the most recent backups based on keep_daily
    # In a production system, you'd want to implement proper grandfather-father-son rotation
    keep_total = keep_daily  # Start with daily backups
    
    # Add weekly and monthly if we have enough backups
    if len(backup_files) > keep_daily:
        keep_total = min(keep_daily + keep_weekly, len(backup_files))
    if len(backup_files) > keep_daily + keep_weekly:
        keep_total = min(keep_daily + keep_weekly + keep_monthly, len(backup_files))
    
    # Cap at a reasonable maximum to prevent keeping too many backups
    keep_total = min(keep_total, 50)
    
    if len(backup_files) > keep_total:
        files_to_delete = backup_files[keep_total:]
        for file_path in files_to_delete:
            try:
                file_path.unlink()
                print(f"Removed old backup: {file_path.name}")
            except Exception as e:
                print(f"Error removing {file_path.name}: {e}")

def main():
    """Main backup function."""
    print("Starting SQLite database backup...")
    
    # Get database path
    db_path = get_db_path()
    print(f"Source database: {db_path}")
    
    # Create backup directory
    backup_dir = create_backup_dir()
    print(f"Backup directory: {backup_dir.absolute()}")
    
    # Generate backup filename
    backup_filename = generate_backup_filename()
    backup_path = backup_dir / backup_filename
    
    # Run backup
    success = backup_sqlite_db(db_path, backup_path)
    
    if success:
        # Get file size
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        print(f"Backup completed successfully: {backup_path} ({size_mb:.2f} MB)")
        
        # Rotate old backups
        rotate_backups(backup_dir)
    else:
        print("Backup failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()