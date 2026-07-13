#!/usr/bin/env python3
"""Build-time transform: convert the standard Minecraft content-addressed asset
store under /app (indexes/*.json + objects/<xx>/<hash>) into a self-contained,
NON-standard "pack" so the task genuinely requires reverse-engineering the
format rather than recognizing a well-known one. Output:

    /app/data/manifest        one line per asset: "<blobid>|<base64(logical_name)>"
    /app/data/blobs/<blobid>  the raw asset bytes (no extension)

The original indexes/ and objects/ are removed so only the obfuscated pack
remains for the agent to reverse-engineer.
"""
import base64
import glob
import json
import os
import shutil

APP = "."

idx = max(glob.glob(f"{APP}/indexes/*.json"), key=os.path.getmtime)
objs = json.load(open(idx))["objects"]

blobs = f"{APP}/data/blobs"
os.makedirs(blobs, exist_ok=True)

lines = []
for i, (name, meta) in enumerate(sorted(objs.items())):
    h = meta["hash"]
    src = f"{APP}/objects/{h[:2]}/{h}"
    if not os.path.exists(src):
        continue
    blobid = f"{i:05d}"
    os.rename(src, f"{blobs}/{blobid}")  # cheap: same filesystem
    lines.append(f"{blobid}|{base64.b64encode(name.encode()).decode()}")

with open(f"{APP}/data/manifest", "w") as fh:
    fh.write("\n".join(lines) + "\n")

# Drop the standard, recognizable layout so only the obfuscated pack remains.
for d in ("indexes", "objects", "skins", "log_configs"):
    shutil.rmtree(f"{APP}/{d}", ignore_errors=True)

print(f"obfuscated {len(lines)} assets -> /app/data/manifest + /app/data/blobs")
