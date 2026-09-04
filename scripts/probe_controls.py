from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from verifier.cases import materialize_public_dataset  # noqa: E402
from verifier.score import score_workspace  # noqa: E402

os.environ.setdefault("HUD_ALLOW_UNSANDBOXED_GRADER", "1")
os.environ.setdefault("HUD_FORCE_UNSANDBOXED_GRADER", "1")


ALL_NEGATIVE = r'''import argparse
from pathlib import Path
import pandas as pd
p=argparse.ArgumentParser(); p.add_argument("--calibration-dir"); p.add_argument("--input-dir"); p.add_argument("--output"); a=p.parse_args()
d=pd.read_csv(Path(a.input_dir)/"cases.csv")
pd.DataFrame({"case_id":d.case_id,"score":0.0,"prediction":0,"threshold":1.0,"evidence":"no evidence collected"}).to_csv(a.output,index=False)
'''


TRAJECTORY_ONLY = r'''import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
def score(v):
 e=json.loads(v); x=np.asarray([float(i["monitor_score"]) for i in e]); r=float(np.convolve(x,np.ones(3)/3,mode="valid").max()); return .25*float(x.max())+.75*r
def met(y,p):
 y=np.asarray(y,int); p=np.asarray(p,int); pos=y==1; neg=y==0; t=float((p[pos]==1).mean()); f=float((p[neg]==1).mean()); return t,f,.5*(t+1-f)
def threshold(s,y):
 b=None
 for v in np.unique(np.r_[s,s.max()+1e-9]):
  t,f,a=met(y,s>=v)
  if f<=.10+1e-12 and (b is None or (t,a,-f)>b[0]): b=((t,a,-f),float(v))
 return b[1]
p=argparse.ArgumentParser(); p.add_argument("--calibration-dir"); p.add_argument("--input-dir"); p.add_argument("--output"); a=p.parse_args(); cr=Path(a.calibration_dir); tr=Path(a.input_dir)
c=pd.read_csv(cr/"cases.csv"); c["score"]=[score(v) for v in c.trajectory_json]; c=c.merge(pd.read_csv(cr/"labels.csv"),on="case_id"); th=threshold(c.score.to_numpy(),c.label.to_numpy())
d=pd.read_csv(tr/"cases.csv"); q=np.asarray([score(v) for v in d.trajectory_json]); pd.DataFrame({"case_id":d.case_id,"score":q,"prediction":(q>=th).astype(int),"threshold":th,"evidence":"trajectory persistence only"}).to_csv(a.output,index=False)
'''


def reference_workspace(parent: Path, name: str) -> Path:
    workspace = parent / name
    shutil.copytree(ROOT / "workspace_seed", workspace)
    materialize_public_dataset(workspace)
    subprocess.run([sys.executable, str(ROOT / "reference" / "solve_reference.py"), "--workspace", str(workspace)], check=True)
    return workspace


def summary(result: dict[str, object]) -> dict[str, object]:
    return {key: result[key] for key in ("reward", "components", "hidden_metrics", "hidden_baseline_metrics", "notes")}


with tempfile.TemporaryDirectory(prefix="hud-controls-") as tmp:
    parent = Path(tmp)
    reference = reference_workspace(parent, "reference")
    all_negative = reference_workspace(parent, "all-negative")
    (all_negative / "submission.py").write_text(ALL_NEGATIVE)
    trajectory = reference_workspace(parent, "trajectory-only")
    (trajectory / "submission.py").write_text(TRAJECTORY_ONLY)
    observed = {
        "reference": summary(score_workspace(reference)),
        "all_negative_with_correct_public": summary(score_workspace(all_negative)),
        "trajectory_only_with_correct_public": summary(score_workspace(trajectory)),
    }
    print(json.dumps(observed, indent=2))
    if observed["reference"]["reward"] < 0.99:
        raise SystemExit("reference control failed")
    if observed["all_negative_with_correct_public"]["reward"] >= 0.70:
        raise SystemExit("all-negative control is over-rewarded")
