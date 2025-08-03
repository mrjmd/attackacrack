#!/usr/bin/env python3
"""
Monitor sync progress from the progress file and update Celery task state
"""
import json
import time
from datetime import datetime

def get_sync_progress():
    """Read the current sync progress from file"""
    try:
        with open('/app/import_progress.json', 'r') as f:
            progress = json.load(f)
            
        stats = progress.get('stats', {})
        conversations = progress.get('conversations_processed', 0)
        
        # Calculate elapsed time
        start_time = datetime.fromisoformat(progress.get('started_at', datetime.now().isoformat()))
        elapsed = (datetime.now() - start_time).total_seconds()
        rate = conversations / elapsed if elapsed > 0 else 0
        
        return {
            'current': conversations,
            'stats': stats,
            'rate': rate,
            'elapsed_seconds': elapsed
        }
    except Exception as e:
        return None

if __name__ == '__main__':
    progress = get_sync_progress()
    if progress:
        print(f"Conversations: {progress['current']}")
        print(f"Rate: {progress['rate']:.1f} conv/sec")
        print(f"Time: {int(progress['elapsed_seconds'] // 60)} minutes")