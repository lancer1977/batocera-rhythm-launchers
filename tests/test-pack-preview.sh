#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/source/Group/Song" "$tmp/target" "$tmp/other-target"
printf 'synthetic chart fixture; no audio\n' > "$tmp/source/Group/Song/chart.sm"
hash="$(sha256sum "$tmp/source/Group/Song/chart.sm" | cut -d' ' -f1)"
cat > "$tmp/inventory.json" <<JSON
{
  "schemaVersion": 1, "identityVersion": 1, "installationId": "fixture",
  "installationRoot": "$tmp/source", "diagnostics": [],
  "packs": [{"packId":"pack:Group", "relativeLocation":"Group", "diagnostics":[],
    "songs":[{"relativeLocation":"Group/Song", "diagnostics":[], "assets":[],
      "charts":[{"sourceRelativeLocation":"Group/Song/chart.sm", "sourceRevision":"$hash"}]}]}]
}
JSON
cat > "$tmp/report.json" <<JSON
{"library_path":"$tmp/source", "songs_scanned":1, "charts_scanned":1,
 "error_count":0, "warning_count":0, "ok":true, "findings":[]}
JSON
before="$(find "$tmp/target" -printf '%P %y %s\n' | sort)"
python3 "$repo/rhythm_pack_preview.py" --source "$tmp/source" --inventory "$tmp/inventory.json" --pack pack:Group \
  --runtime stepmania-flatpak --target "$tmp/target" --profile stock-stepmania-flatpak \
  --validator-report "$tmp/report.json" --validator-version 0.1.0 > "$tmp/plan.json" 2> "$tmp/human.txt"
python3 - "$tmp/plan.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]))
assert p['status']=='READY' and p['estimatedBytes'] > 0
assert p['files'][0]['destination']=='Song/chart.sm'
assert p['provenance']['inventory']['commit']=='072dcfb83e28fa3cd5b6754db668c006b01eeec7'
assert p['provenance']['validator']['status']=='PASS'
assert p['canonicalIdentity'].startswith('unresolved')
PY
[ "$before" = "$(find "$tmp/target" -printf '%P %y %s\n' | sort)" ]
python3 "$repo/rhythm_pack_preview.py" --source "$tmp/source" --inventory "$tmp/inventory.json" --pack pack:Group \
  --runtime itgmania-portable --target "$tmp/other-target" --profile stock-itgmania-portable \
  --validator-report "$tmp/report.json" --validator-version 0.1.0 > "$tmp/plan2.json" 2> /dev/null
python3 - "$tmp/plan.json" "$tmp/plan2.json" <<'PY'
import json,sys
a,b=(json.load(open(p)) for p in sys.argv[1:])
for p in (a,b):
    p.pop('runtime'); p.pop('profile'); p.pop('targetSongsRoot')
    p['files'][0].pop('targetState'); p['files'][0].pop('targetSha256')
    p['availableBytes']=None
assert a==b
PY
set +e
python3 "$repo/rhythm_pack_preview.py" --source "$tmp/source" --inventory "$tmp/inventory.json" --pack pack:Group \
  --runtime stepmania-flatpak --target "$tmp/target" --profile stock --validator-report "$tmp/report.json" --validator-version 9.9.9 > "$tmp/blocked.json" 2>/dev/null
status=$?
set -e
[ "$status" -eq 2 ]
python3 - "$tmp/blocked.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); assert p['status']=='BLOCKED' and 'unsupported-validator-version' in p['blockers']
PY
ln -s "$tmp/outside" "$tmp/source/Group/Song/escape"
set +e
python3 "$repo/rhythm_pack_preview.py" --source "$tmp/source" --inventory "$tmp/inventory.json" --pack pack:Group \
  --runtime stepmania-flatpak --target "$tmp/target" --profile stock --validator-report "$tmp/report.json" --validator-version 0.1.0 > "$tmp/link.json" 2>/dev/null
status=$?
set -e
[ "$status" -eq 2 ]
python3 - "$tmp/link.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); assert 'source-symlink-unsupported' in p['blockers']
PY
