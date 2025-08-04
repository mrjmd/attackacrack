#!/usr/bin/env python3
"""
Simple wrapper to run OpenPhone imports from command line
"""
import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import and run the enhanced importer
from scripts.data_management.imports.enhanced_openphone_import import main

if __name__ == "__main__":
    main()