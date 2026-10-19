import hashlib, json, sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest_path = root / 'outputs' / '05b_freeze_manifest.json'
with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

mismatches = []
for name, entry in manifest['file_integrity_hashes'].items():
    target_file = root / entry["path"]
    actual = hashlib.sha256(target_file.read_bytes()).hexdigest()
    expected = entry["sha256"]
    if actual != expected:
        mismatches.append(f'{name}: expected {expected}, got {actual}')

if mismatches:
    print('FAIL: Frozen strategy hash mismatches:')
    for m in mismatches:
        print('  ', m)
    sys.exit(1)

print(f'PASS: All {len(manifest["file_integrity_hashes"])} frozen strategy hashes match 100%.')
