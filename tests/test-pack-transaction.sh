#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export REPO="$repo" FIXTURE_ROOT="$tmp"
python3 - <<'PY'
import hashlib, json, os, pathlib, shutil, sys
sys.path.insert(0, os.environ['REPO'])
import rhythm_pack_preview as preview
import rhythm_pack_transaction as tx
try:
 tx.parser().parse_args(['apply'])
 raise AssertionError('CLI accepted apply without --apply or other required inputs')
except SystemExit:
 pass
base=pathlib.Path(os.environ['FIXTURE_ROOT'])
validator=base/'validator'/'stepmania_song_validator'; validator.mkdir(parents=True)
(validator/'__init__.py').write_text('__version__ = "0.1.0"\n')
(validator/'cli.py').write_text('''import json\nfrom pathlib import Path\ndef main(argv):\n p=Path(argv[0]); charts=list(p.rglob("*.sm")); bad=[x for x in charts if not x.read_text().rstrip().endswith(";")]\n findings=[{"category":"fixture","severity":"error","code":"BAD","message":"fixture","path":str(x)} for x in bad]\n print(json.dumps({"library_path":str(p),"songs_scanned":len(charts),"charts_scanned":len(charts),"error_count":len(bad),"warning_count":0,"ok":not bad,"findings":findings}))\n return int(bool(bad))\n''')
def setup(name):
 root=base/name; source=root/'source'; target=root/'target'; inv=root/'inventory.json'; planfile=root/'plan.json'
 (source/'Group'/'Song').mkdir(parents=True); target.mkdir(parents=True)
 chart=source/'Group'/'Song'/'chart.sm'; chart.write_text('synthetic chart fixture;\n'); h=hashlib.sha256(chart.read_bytes()).hexdigest()
 inv.write_text(json.dumps({"schemaVersion":1,"identityVersion":1,"installationRoot":str(source),"diagnostics":[],"packs":[{"packId":"pack:Group","relativeLocation":"Group","diagnostics":[],"assets":[],"songs":[{"relativeLocation":"Group/Song","diagnostics":[],"assets":[],"charts":[{"sourceRelativeLocation":"Group/Song/chart.sm","sourceRevision":h}]}]}]}))
 ns=type('A',(),dict(source=str(source),target=str(target),inventory=str(inv),validator_report=None,validator_source=str(base/'validator'),validator_version=None,pack='pack:Group',runtime='stepmania-flatpak',profile='fixture'))()
 plan=preview.preview(ns); assert plan['status']=='READY',plan; planfile.write_text(json.dumps(plan))
 args=type('A',(),dict(plan=str(planfile),source=str(source),target=str(target),inventory=str(inv),validator_source=str(base/'validator'),pack='pack:Group',runtime='stepmania-flatpak',profile='fixture',game_stopped=True))()
 return root,source,target,plan,args
def invoke(target,tid): return type('A',(),dict(target=str(target),transaction=tid))()

# Apply, receipt ownership, recover idempotence, and rollback.
r,s,t,p,a=setup('success'); source_before=preview.source_snapshot(s); rec=tx.apply(a); assert rec['status']=='active' and (t/'Group'/'Song'/'chart.sm').is_file()
assert preview.source_snapshot(s)==source_before
assert tx.recover(invoke(t,rec['id']))['status']=='active'
assert tx.recover(invoke(t,rec['id']),rollback=True)['status']=='rolled-back' and not (t/'Group').exists()
assert tx.recover(invoke(t,rec['id']),rollback=True)['status']=='rolled-back'

# Stale/edited plan, source hash drift, and missing stopped acknowledgement.
r,s,t,p,a=setup('edited'); doc=json.loads(pathlib.Path(a.plan).read_text()); doc['packId']='edited'; pathlib.Path(a.plan).write_text(json.dumps(doc))
try: tx.apply(a); raise AssertionError('edited plan accepted')
except RuntimeError: pass
r,s,t,p,a=setup('drift'); (s/'Group'/'Song'/'chart.sm').write_text('different;\n')
try: tx.apply(a); raise AssertionError('source drift accepted')
except RuntimeError: pass
r,s,t,p,a=setup('ack'); a.game_stopped=False
try: tx.apply(a); raise AssertionError('missing acknowledgement accepted')
except RuntimeError: pass
r,s,t,p,a=setup('runtime'); a.runtime='itgmania-portable'
try: tx.apply(a); raise AssertionError('runtime mismatch accepted')
except RuntimeError: pass
r,s,t,p,a=setup('itg-runtime'); a.runtime='itgmania-portable'; a.profile='fixture-portable'
doc=json.loads(pathlib.Path(a.plan).read_text()); doc['runtime']=a.runtime; doc['profile']=a.profile; pathlib.Path(a.plan).write_text(json.dumps(doc))
assert tx.apply(a)['runtime']=='itgmania-portable'

# Existing pack and insufficient space are refused.
r,s,t,p,a=setup('existing'); (t/'Group').mkdir(); (t/'Group'/'keep').write_text('unrelated')
try: tx.apply(a); raise AssertionError('existing pack accepted')
except RuntimeError: pass
r,s,t,p,a=setup('space'); old=tx.shutil.disk_usage; tx.shutil.disk_usage=lambda _:type('U',(),dict(free=0))()
try:
 try: tx.apply(a); raise AssertionError('space shortage accepted')
 except RuntimeError: pass
finally: tx.shutil.disk_usage=old

# Rollback leaves modified owned data and unrelated content, and reports conflict.
r,s,t,p,a=setup('modified'); rec=tx.apply(a); owned=t/'Group'/'Song'/'chart.sm'; owned.write_text('operator edit\n'); unrelated=t/'Group'/'Song'/'keep.txt'; unrelated.write_text('unrelated\n')
out=tx.recover(invoke(t,rec['id']),rollback=True); assert out['status']=='rollback-conflict' and out['conflicts']==['Song/chart.sm','Song/keep.txt']
assert owned.read_text()=='operator edit\n' and unrelated.read_text()=='unrelated\n'

# Fixture interruption before activation leaves a durable stage that can be completed.
r,s,t,p,a=setup('crash-before')
def before(point):
 if point=='before-activation': raise OSError('fixture interruption')
try: tx.apply(a,before); raise AssertionError('fault injection did not fire')
except OSError: pass
tid=next((t/tx.STATE_DIR).glob('*.json')).stem
assert tx.recover(invoke(t,tid))['status']=='staging-ready'
assert tx.recover(invoke(t,tid))['status']=='active'

# Simulate interruption after activation rename while the receipt remains staging-ready.
r,s,t,p,a=setup('crash-receipt')
def pause(point):
 if point=='before-activation': raise OSError('fixture interruption')
try: tx.apply(a,pause); raise AssertionError('fixture interruption did not fire')
except OSError: pass
tid=next((t/tx.STATE_DIR).glob('*.json')).stem
assert tx.recover(invoke(t,tid))['status']=='staging-ready'
td1=tx.open_directory_walk(str(t)); td2=tx.open_directory_walk(str(t))
try: tx.rename_noreplace(tx.STAGE_PREFIX+tid,'Group',td1,td2)
finally: os.close(td1); os.close(td2)
assert tx.recover(invoke(t,tid))['status']=='active'

# Fixture interruption after rename is recognized by exact hashes on recovery.
r,s,t,p,a=setup('crash-after')
def after(point):
 if point=='after-activation': raise OSError('fixture interruption')
try: tx.apply(a,after); raise AssertionError('post-activation fault injection did not fire')
except OSError: pass
tid=next((t/tx.STATE_DIR).glob('*.json')).stem
assert tx.recover(invoke(t,tid))['status']=='active'

# Exact review regression: an absent owned stage plus a byte-matching unrelated
# destination is never adopted or deleted by recovery or rollback.
r,s,t,p,a=setup('review-unrelated-destination')
def stop_before(point):
 if point=='before-activation': raise OSError('fixture interruption')
try: tx.apply(a,stop_before); raise AssertionError('fixture interruption did not fire')
except OSError: pass
tid=next((t/tx.STATE_DIR).glob('*.json')).stem
stage=t/(tx.STAGE_PREFIX+tid); shutil.rmtree(stage)
destination=t/'Group'; (destination/'Song').mkdir(parents=True)
(destination/'Song'/'chart.sm').write_bytes((s/'Group'/'Song'/'chart.sm').read_bytes())
snapshot={str(x.relative_to(t)):x.read_bytes() for x in destination.rglob('*') if x.is_file()}
for rollback in (False, True):
 try: tx.recover(invoke(t,tid),rollback=rollback); raise AssertionError('unowned matching destination adopted')
 except RuntimeError: pass
assert {str(x.relative_to(t)):x.read_bytes() for x in destination.rglob('*') if x.is_file()}==snapshot

# An active directory replaced by a byte-identical copy is not the owned inode.
r,s,t,p,a=setup('review-identical-replacement'); rec=tx.apply(a); destination=t/'Group'
replacement=r/'replacement'; shutil.copytree(destination,replacement)
shutil.rmtree(destination); shutil.copytree(replacement,destination)
snapshot={str(x.relative_to(t)):x.read_bytes() for x in destination.rglob('*') if x.is_file()}
for rollback in (False, True):
 try: tx.recover(invoke(t,rec['id']),rollback=rollback); raise AssertionError('replacement adopted')
 except RuntimeError: pass
assert {str(x.relative_to(t)):x.read_bytes() for x in destination.rglob('*') if x.is_file()}==snapshot

# Missing and false ownership evidence fail closed without changing the stage.
for label, change in [('missing',lambda receipt: receipt.pop('ownership')),
                      ('false',lambda receipt: receipt['ownership'].__setitem__('inode',receipt['ownership']['inode']+1))]:
 r,s,t,p,a=setup('review-ownership-'+label)
 try: tx.apply(a,stop_before); raise AssertionError('fixture interruption did not fire')
 except OSError: pass
 receipt_path=next((t/tx.STATE_DIR).glob('*.json')); receipt=json.loads(receipt_path.read_text())
 tid=receipt['id']; change(receipt); receipt_path.write_text(json.dumps(receipt))
 stage=t/(tx.STAGE_PREFIX+tid); snapshot={str(x.relative_to(stage)):x.read_bytes() for x in stage.rglob('*') if x.is_file()}
 try: tx.recover(invoke(t,tid),rollback=True); raise AssertionError(label+' ownership evidence accepted')
 except RuntimeError: pass
 assert {str(x.relative_to(stage)):x.read_bytes() for x in stage.rglob('*') if x.is_file()}==snapshot

# The reserved ownership marker path cannot be supplied by a source plan.
r,s,t,p,a=setup('review-marker-collision'); altered=dict(p); altered['files']=[dict(p['files'][0],destination='Group/'+tx.OWNER_MARKER)]
old_fresh_plan=tx.fresh_plan; tx.fresh_plan=lambda _: (altered,altered)
try:
 try: tx.apply(a); raise AssertionError('reserved ownership marker collision accepted')
 except RuntimeError: pass
finally: tx.fresh_plan=old_fresh_plan

# Symlink target ancestry is refused.
r,s,t,p,a=setup('symlink'); outside=r/'outside'; outside.mkdir(); shutil.rmtree(t); t.symlink_to(outside)
try: tx.apply(a); raise AssertionError('target symlink accepted')
except (RuntimeError,OSError): pass

# An operator-added empty directory is a rollback conflict; ownership evidence survives until it is removed.
r,s,t,p,a=setup('review-empty-dir'); rec=tx.apply(a); empty=t/'Group'/'operator-empty-dir'; empty.mkdir()
out=tx.recover(invoke(t,rec['id']),rollback=True); assert out['status']=='rollback-conflict' and out['conflicts']==['operator-empty-dir'], out
assert (t/'Group'/tx.OWNER_MARKER).exists() and (t/'Group').exists()
empty.rmdir()
out=tx.recover(invoke(t,rec['id']),rollback=True); assert out['status']=='rolled-back' and not (t/'Group').exists(), out

# A staging name replaced before the activation boundary is refused before any rename.
r,s,t,p,a=setup('review-stage-replaced')
def replace_stage(point):
 if point=='before-activation':
  stage=next(x for x in t.iterdir() if x.name.startswith(tx.STAGE_PREFIX)); stage.rename(t/'aside'); stage.mkdir(); (stage/'unrelated.txt').write_text('unrelated\n')
try: tx.apply(a,hook=replace_stage); raise AssertionError('replaced stage activated')
except RuntimeError as exc: assert 'replaced before activation' in str(exc), exc
assert not (t/'Group').exists()

# A FIFO in an installed pack cannot block recovery or rollback.
import signal
r,s,t,p,a=setup('review-fifo'); rec=tx.apply(a); chart=t/'Group'/'Song'/'chart.sm'; chart.unlink(); os.mkfifo(chart)
def timed_out(*_): raise TimeoutError('recovery blocked on FIFO')
signal.signal(signal.SIGALRM, timed_out); signal.alarm(5)
try:
 try: tx.recover(invoke(t,rec['id'])); raise AssertionError('fifo accepted')
 except RuntimeError: pass
 out=tx.recover(invoke(t,rec['id']),rollback=True); assert out['status']=='rollback-conflict' and 'Song/chart.sm' in out['conflicts'], out
finally: signal.alarm(0)
assert chart.exists()

# Issue 20 finding 1: staging-ready receipts must retain the live activation validation contract.
r,s,t,p,a=setup('issue20-validator-recovery')
def stop_before_activation(point):
 if point=='after-activation': raise OSError('fixture interruption')
try: tx.apply(a,stop_before_activation); raise AssertionError('fixture interruption did not fire')
except OSError: pass
tid=next((t/tx.STATE_DIR).glob('*.json')).stem
receipt=json.loads(next((t/tx.STATE_DIR).glob('*.json')).read_text())
assert receipt.get('activationValidation') == p['provenance']['validator'], receipt

# Issue 20 finding 2: unrelated nested empty directories remain conflicts.
r,s,t,p,a=setup('issue20-nested-empty'); rec=tx.apply(a); empty=t/'Group'/'operator'/'empty'; empty.mkdir(parents=True)
out=tx.recover(invoke(t,rec['id']),rollback=True)
assert out['status']=='rollback-conflict' and 'operator/empty' in out['conflicts'], out
assert (t/'Group'/tx.OWNER_MARKER).exists() and empty.is_dir()

# Issue 20 finding 3: normalize --target before recording it in the receipt.
r,s,t,p,a=setup('issue20-target-dotdot'); normalized=t/'normalized'; normalized.mkdir(); a.target=str(normalized/'..'/'normalized')
try: tx.apply(a); raise AssertionError('target containing dot-dot accepted')
except RuntimeError: pass

# Issue 20 finding 4: replacing the stage pathname before activation is rejected.
r,s,t,p,a=setup('issue20-stage-swap')
def swap_stage(point):
 if point=='before-activation':
  stage=next(x for x in t.iterdir() if x.name.startswith(tx.STAGE_PREFIX)); stage.rename(t/'saved'); stage.mkdir(); (stage/'intruder').write_text('x')
try: tx.apply(a,swap_stage); raise AssertionError('swapped stage pathname activated')
except RuntimeError: pass
assert not (t/'Group').exists()

# Issue 20 finding 5: mutating staged bytes after tree verification is rejected.
r,s,t,p,a=setup('issue20-stage-content')
def mutate_stage(point):
 if point=='before-activation':
  stage=next(x for x in t.iterdir() if x.name.startswith(tx.STAGE_PREFIX)); (stage/'Song'/'chart.sm').write_text('changed;')
try: tx.apply(a,mutate_stage); raise AssertionError('changed staged content activated')
except RuntimeError: pass
assert not (t/'Group').exists()

# Issue 20 finding 6: a non-directory destination does not prevent staged recovery or rollback.
r,s,t,p,a=setup('issue20-nondir-candidate')
def stop_for_candidate(point):
 if point=='before-activation': raise OSError('fixture interruption')
try: tx.apply(a,stop_for_candidate); raise AssertionError('fixture interruption did not fire')
except OSError: pass
tid=next((t/tx.STATE_DIR).glob('*.json')).stem; (t/'Group').write_text('operator file')
assert tx.recover(invoke(t,tid))['status']=='staging-ready'
out=tx.recover(invoke(t,tid),rollback=True)
assert out['status']=='rolled-back' and (t/'Group').read_text()=='operator file', out

# Issue 20 finding 7: FIFO recovery and rollback return under a subprocess timeout.
import subprocess, sys
r,s,t,p,a=setup('issue20-fifo'); rec=tx.apply(a); chart=t/'Group'/'Song'/'chart.sm'; chart.unlink(); os.mkfifo(chart)
code='import sys; sys.path.insert(0,sys.argv[1]); import rhythm_pack_transaction as tx; root=sys.argv[2]; args=type("A",(),dict(target=root,transaction=sys.argv[3]))();\nfor rollback in (False,True):\n try: tx.recover(args,rollback=rollback)\n except RuntimeError: pass'
subprocess.run([sys.executable,'-c',code,os.environ['REPO'],str(t),rec['id']],timeout=3,check=True)
assert chart.exists()
print('PASS: staged pack transaction fixture cases')
PY
