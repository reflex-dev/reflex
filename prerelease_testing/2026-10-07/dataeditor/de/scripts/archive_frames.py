"""Move verbose websocket evidence to compressed sidecars, preserving all frames."""
import gzip
import json
import sys
from pathlib import Path

root=Path(sys.argv[1])
for result in root.glob(sys.argv[2] if len(sys.argv) > 2 else 'runs/*/results.json'):
    data=json.loads(result.read_text())
    frames={}
    for name,group in data['groups'].items():
        if 'ws_frames' in group:
            frames[name]=group.pop('ws_frames')
    if frames:
        sidecar=result.with_name('websocket-frames.json.gz')
        sidecar.write_bytes(gzip.compress(json.dumps(frames,indent=1).encode(),mtime=0))
        data['ws_frames_artifact']=sidecar.name
        result.write_text(json.dumps(data,indent=1))
    data=json.loads(result.read_text())
    if 'full_console_artifact' not in data:
        full_console={name:group['console'] for name,group in data['groups'].items()}
        for group in data['groups'].values():
            compact={}
            for entry in group['console']:
                key=json.dumps(entry,sort_keys=True)
                if key not in compact:
                    compact[key]={**entry,'repeat_count':0}
                compact[key]['repeat_count']+=1
            group['console']=list(compact.values())
        sidecar=result.with_name('full-console.json.gz')
        sidecar.write_bytes(gzip.compress(json.dumps(full_console,indent=1).encode(),mtime=0))
        data['full_console_artifact']=sidecar.name
        result.write_text(json.dumps(data,indent=1))
