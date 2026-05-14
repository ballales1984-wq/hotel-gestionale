import sys
import os

# Set PYTHONPATH
sys.path.insert(0, r"D:\hotel gestionale\backend")
os.chdir(r"D:\hotel gestionale\backend")

# Now run the full populate
exec(open(r"D:\hotel gestionale\backend\scripts\full_populate.py").read())