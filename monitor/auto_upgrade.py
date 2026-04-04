# monitor/auto_upgrade.py
import sys
import os
import subprocess
import json
import hashlib
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

UPGRADE_LOG = 'logs/upgrade_log.jsonl'
CHECKSUM_FILE = 'logs/checksums.json'


def calculate_file_checksums(directory):
    checksums = {}
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'rb') as f:
                    checksums[filepath] = hashlib.md5(f.read()).hexdigest()
    return checksums


def check_for_changes(current_checksums, new_checksums):
    changes = {
        'added': [],
        'modified': [],
        'deleted': []
    }

    for filepath, checksum in new_checksums.items():
        if filepath not in current_checksums:
            changes['added'].append(filepath)
        elif current_checksums[filepath] != checksum:
            changes['modified'].append(filepath)

    for filepath in current_checksums:
        if filepath not in new_checksums:
            changes['deleted'].append(filepath)

    return changes


def log_upgrade(changes):
    os.makedirs('logs', exist_ok=True)
    entry = {
        'timestamp': datetime.now().isoformat(),
        'changes': changes,
        'total_files': len(changes['added']) + len(changes['modified']) + len(changes['deleted'])
    }
    with open(UPGRADE_LOG, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def run_upgrade_check():
    print('Checking for code changes...')

    if os.path.exists(CHECKSUM_FILE):
        with open(CHECKSUM_FILE, 'r') as f:
            old_checksums = json.load(f)
    else:
        old_checksums = {}

    new_checksums = calculate_file_checksums('.')

    changes = check_for_changes(old_checksums, new_checksums)

    if changes['added'] or changes['modified'] or changes['deleted']:
        print(f'Changes detected:')
        if changes['added']:
            print(f'  Added: {len(changes["added"])} files')
            for f in changes['added']:
                print(f'    + {f}')
        if changes['modified']:
            print(f'  Modified: {len(changes["modified"])} files')
            for f in changes['modified']:
                print(f'    ~ {f}')
        if changes['deleted']:
            print(f'  Deleted: {len(changes["deleted"])} files')
            for f in changes['deleted']:
                print(f'    - {f}')

        log_upgrade(changes)

        with open(CHECKSUM_FILE, 'w') as f:
            json.dump(new_checksums, f, indent=2)

        print('Checksums updated. Restart recommended.')
        return True
    else:
        print('No changes detected.')
        return False


def restart_system():
    print('Restarting trading system...')
    script = os.path.join(os.path.dirname(__file__), '..', 'run_247.py')
    subprocess.Popen([sys.executable, script], creationflags=subprocess.CREATE_NEW_CONSOLE)
    print('New instance started.')


if __name__ == '__main__':
    changed = run_upgrade_check()
    if changed:
        response = input('Restart now? (y/n): ').strip().lower()
        if response == 'y':
            restart_system()
