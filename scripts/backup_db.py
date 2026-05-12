#!/usr/bin/env python3
"""
Database backup script for PostgreSQL.
Dumps the database to a .sql file with rotation.
"""

import os
import sys
import subprocess
import datetime
import glob
from pathlib import Path

# Add backend to path to import settings
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from app.config import get_settings
except ImportError:
    print("Error: Could not import backend settings. Make sure you're running from the project root.")
    sys.exit(1)

def get_db_connection_info():
    """Extract PostgreSQL connection info from settings."""
    settings = get_settings()
    db_url = settings.database_url
    
    # Check if we're using PostgreSQL
    if not db_url.startswith("postgresql"):
        print(f"Error: This script is designed for PostgreSQL databases. Current URL: {db_url}")
        print("Set DATABASE_URL environment variable to a PostgreSQL connection string.")
        sys.exit(1)
    
    # Parse the URL (simplified - assumes standard format)
    # postgresql://user:password@host:port/dbname
    try:
        # Remove postgresql://
        url_part = db_url[13:]
        if '@' in url_part:
            auth, hostpart = url_part.split('@', 1)
            if ':' in auth:
                user, password = auth.split(':', 1)
            else:
                user = auth
                password = ''
            if ':' in hostpart:
                hostport, dbname = hostpart.split('/', 1)
                if ':' in hostport:
                    host, port = hostport.split(':', 1)
                else:
                    host = hostport
                    port = '5432'
            else:
                host = hostpart
                port = '5432'
                dbname = ''
        else:
            # No auth
            hostpart, dbname = url_part.split('/', 1)
            if ':' in hostpart:
                host, port = hostpart.split(':', 1)
            else:
                host = hostpart
                port = '5432'
            user = os.getenv('POSTGRES_USER', 'postgres')
            password = os.getenv('POSTGRES_PASSWORD', '')
    except Exception as e:
        print(f"Error parsing database URL: {e}")
        sys.exit(1)
    
    return {
        'user': user,
        'password': password,
        'host': host,
        'port': port,
        'dbname': dbname
    }

def create_backup_dir():
    """Create backup directory if it doesn't exist."""
    backup_dir = Path('./backups')
    backup_dir.mkdir(exist_ok=True)
    return backup_dir

def generate_backup_filename():
    """Generate a timestamped backup filename."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"backup_{timestamp}.sql"

def run_pg_dump(conn_info, backup_path):
    """Execute pg_dump to create backup."""
    # Set PGPASSWORD environment variable for psql
    env = os.environ.copy()
    if conn_info['password']:
        env['PGPASSWORD'] = conn_info['password']
    
    cmd = [
        'pg_dump',
        '-h', conn_info['host'],
        '-p', conn_info['port'],
        '-U', conn_info['user'],
        '-d', conn_info['dbname'],
        '-f', str(backup_path),
        '--verbose'
    ]
    
    print(f"Running pg_dump to {backup_path}...")
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running pg_dump: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False
    except FileNotFoundError:
        print("Error: pg_dump command not found. Make sure PostgreSQL client tools are installed and in PATH.")
        return False

def rotate_backups(backup_dir, keep_daily=7, keep_weekly=4, keep_monthly=6):
    """Rotate backup files, keeping specified number of daily, weekly, monthly backups."""
    backup_files = list(backup_dir.glob("backup_*.sql"))
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
    print("Starting database backup...")
    
    # Get connection info
    conn_info = get_db_connection_info()
    print(f"Connecting to {conn_info['host']}:{conn_info['port']}/{conn_info['dbname']} as {conn_info['user']}")
    
    # Create backup directory
    backup_dir = create_backup_dir()
    print(f"Backup directory: {backup_dir.absolute()}")
    
    # Generate backup filename
    backup_filename = generate_backup_filename()
    backup_path = backup_dir / backup_filename
    
    # Run backup
    success = run_pg_dump(conn_info, backup_path)
    
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