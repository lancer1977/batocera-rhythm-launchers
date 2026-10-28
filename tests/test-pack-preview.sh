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
rm "$tmp/source/Group/Song/escape"

# The inventory's nested asset paths are preserved under their song directory.
mkdir -p "$tmp/source/Group/Song/audio"
printf 'nested audio fixture\n' > "$tmp/source/Group/Song/audio/theme.ogg"
nested_hash="$(sha256sum "$tmp/source/Group/Song/audio/theme.ogg" | cut -d' ' -f1)"
python3 - "$tmp/inventory.json" "$nested_hash" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); p['packs'][0]['songs'][0]['assets']=[
 {'relativeLocation':'Group/Song/audio/theme.ogg','status':'present','sha256':sys.argv[2]}]
json.dump(p,open(sys.argv[1],'w'))
PY
python3 "$repo/rhythm_pack_preview.py" --source "$tmp/source" --inventory "$tmp/inventory.json" --pack pack:Group \
  --runtime stepmania-flatpak --target "$tmp/target" --profile stock --validator-report "$tmp/report.json" --validator-version 0.1.0 > "$tmp/nested.json" 2>/dev/null
python3 - "$tmp/nested.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); assert p['status']=='READY'
assert 'Song/audio/theme.ogg' in [x['destination'] for x in p['files']]
PY

# Assets outside the selected song and symlinked source ancestors are refused.
python3 - "$tmp/inventory.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); p['packs'][0]['songs'][0]['assets'][0]['relativeLocation']='Group/Elsewhere/theme.ogg'
json.dump(p,open(sys.argv[1],'w'))
PY
set +e
python3 "$repo/rhythm_pack_preview.py" --source "$tmp/source" --inventory "$tmp/inventory.json" --pack pack:Group \
  --runtime stepmania-flatpak --target "$tmp/target" --profile stock --validator-report "$tmp/report.json" --validator-version 0.1.0 > "$tmp/outside-song.json" 2>/dev/null
status=$?
set -e
[ "$status" -eq 2 ]
python3 - "$tmp/outside-song.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); assert 'source-path-escape-or-unsupported-path' in p['blockers']
PY

# Target ancestors, including Songs root, are checked for symlinks.
ln -s "$tmp/target" "$tmp/target-link"
set +e
python3 "$repo/rhythm_pack_preview.py" --source "$tmp/source" --inventory "$tmp/inventory.json" --pack pack:Group \
  --runtime stepmania-flatpak --target "$tmp/target-link" --profile stock --validator-report "$tmp/report.json" --validator-version 0.1.0 > "$tmp/target-link.json" 2>/dev/null
status=$?
set -e
[ "$status" -eq 2 ]
python3 - "$tmp/target-link.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); assert 'target-symlink-unsupported' in p['blockers']
PY

# Pack-level assets use the same target conflict checks as song assets.
printf 'pack banner\n' > "$tmp/source/Group/banner.png"
banner_hash="$(sha256sum "$tmp/source/Group/banner.png" | cut -d' ' -f1)"
python3 - "$tmp/inventory.json" "$banner_hash" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); p['packs'][0]['songs'][0]['assets']=[]
p['packs'][0]['assets']=[{'relativeLocation':'Group/banner.png','status':'present','sha256':sys.argv[2]}]
json.dump(p,open(sys.argv[1],'w'))
PY
mkdir -p "$tmp/target"
printf 'different target banner\n' > "$tmp/target/banner.png"
set +e
python3 "$repo/rhythm_pack_preview.py" --source "$tmp/source" --inventory "$tmp/inventory.json" --pack pack:Group \
  --runtime stepmania-flatpak --target "$tmp/target" --profile stock --validator-report "$tmp/report.json" --validator-version 0.1.0 > "$tmp/pack-conflict.json" 2>/dev/null
status=$?
set -e
[ "$status" -eq 2 ]
python3 - "$tmp/pack-conflict.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); assert 'target-file-conflict' in p['blockers']
PY

# Pack banner and song banner occupy distinct destination paths; never flatten them.
printf 'different banner\n' > "$tmp/source/Group/Song/banner.png"
other_hash="$(sha256sum "$tmp/source/Group/Song/banner.png" | cut -d' ' -f1)"
python3 - "$tmp/inventory.json" "$other_hash" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); p['packs'][0]['assets'][0]['relativeLocation']='Group/banner.png'
p['packs'][0]['assets'][0]['sha256']='bdd1bb181d72d6a7ad144c79d43198143281797b91cc3e069499950138a5c559'
p['packs'][0]['songs'][0]['assets']=[
 {'relativeLocation':'Group/Song/banner.png','status':'present','sha256':sys.argv[2]}]
json.dump(p,open(sys.argv[1],'w'))
PY
set +e
python3 "$repo/rhythm_pack_preview.py" --source "$tmp/source" --inventory "$tmp/inventory.json" --pack pack:Group \
  --runtime stepmania-flatpak --target "$tmp/other-target" --profile stock --validator-report "$tmp/report.json" --validator-version 0.1.0 > "$tmp/collision.json" 2>/dev/null
status=$?
set -e
[ "$status" -eq 0 ]
python3 - "$tmp/collision.json" <<'PYCASE'
import json,sys
p=json.load(open(sys.argv[1])); assert p['status']=='READY'
assert {'banner.png','Song/banner.png'} <= {f['destination'] for f in p['files']}
assert 'destination-hash-collision' not in p['blockers']
PYCASE

# Structurally malformed inventories return BLOCKED JSON, never a traceback.
for malformed in '[]' '{"packs":[null]}' '{"packs":{},"schemaVersion":1,"identityVersion":1,"installationRoot":"x","diagnostics":[]}' '{"schemaVersion":1,"identityVersion":1,"installationRoot":"x","diagnostics":[],"packs":[{"packId":"p","relativeLocation":"Group","songs":[{"relativeLocation":"Group/Song","assets":[{"relativeLocation":5,"sha256":false,"status":1}],"charts":[]}]}]}'
do
  printf '%s\n' "$malformed" > "$tmp/inventory.json"
  set +e
  python3 "$repo/rhythm_pack_preview.py" --source "$tmp/source" --inventory "$tmp/inventory.json" --pack pack:Group \
    --runtime stepmania-flatpak --target "$tmp/target" --profile stock --validator-report "$tmp/report.json" --validator-version 0.1.0 > "$tmp/malformed.json" 2>"$tmp/malformed.err"
  status=$?
  set -e
  [ "$status" -eq 2 ]
  ! rg -q 'Traceback' "$tmp/malformed.err"
  python3 - "$tmp/malformed.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); assert p['status']=='BLOCKED' and 'inventory-unavailable-or-invalid' in p['blockers']
PY
done
