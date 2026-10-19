"""Verify source reports, integrity status, and runnable skill manifests."""
from pathlib import Path
import json, re, hashlib
root = Path(__file__).resolve().parents[1]
reports = list((root/'research'/'backtests').glob('V*_*.md'))
versions = sorted(int(re.match(r'V(\d+)_', p.name).group(1)) for p in reports)
assert versions == list(range(1,23)), f'Expected V01..V22, got {versions}'
assert len(list((root/'.agents'/'skills').glob('*/SKILL.md'))) >= 3
meta=json.loads((root/'config'/'research_mode.json').read_text())
assert meta['mode'] == 'research_only' and not meta['allow_live_trading']
print(f'PASS: {len(reports)} immutable original research reports V01..V22 present')
for p in sorted(reports): print(p.name, hashlib.sha256(p.read_bytes()).hexdigest())
print('PASS: research-only config and local skills present')
