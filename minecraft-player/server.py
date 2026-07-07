#!/usr/bin/env python3
"""Minimal, dependency-free web audio player for a folder of .wav files.

Serves a themed UI at / and streams audio with HTTP Range support so the
browser can seek/scrub. Stdlib only — no pip install required.
"""
import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MUSIC_DIR = os.path.expanduser("~/minecraft-soundtrack-wav")
PORT = 8001


def list_tracks():
    try:
        names = sorted(
            f for f in os.listdir(MUSIC_DIR)
            if f.lower().endswith(".wav") and os.path.isfile(os.path.join(MUSIC_DIR, f))
        )
    except FileNotFoundError:
        names = []
    tracks = []
    for f in names:
        title = os.path.splitext(f)[0].replace("_", " ").strip()
        title = " ".join(w.capitalize() if not w.isdigit() else w for w in title.split())
        tracks.append({"file": f, "title": title or f})
    return tracks


def safe_path(name):
    """Resolve a requested filename to a path strictly inside MUSIC_DIR."""
    name = urllib.parse.unquote(name)
    candidate = os.path.normpath(os.path.join(MUSIC_DIR, name))
    base = os.path.realpath(MUSIC_DIR)
    if os.path.realpath(candidate).startswith(base) and os.path.isfile(candidate):
        return candidate
    return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # keep the console quiet

    def _send(self, code, body=b"", ctype="text/plain", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/" or path == "/index.html":
            self._send(200, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/tracks":
            body = json.dumps(list_tracks()).encode("utf-8")
            self._send(200, body, "application/json")
        elif path.startswith("/media/"):
            self.serve_media(path[len("/media/"):])
        else:
            self._send(404, b"Not found")

    do_HEAD = do_GET

    def serve_media(self, name):
        full = safe_path(name)
        if not full:
            self._send(404, b"No such track")
            return
        size = os.path.getsize(full)
        range_header = self.headers.get("Range")
        start, end = 0, size - 1
        status = 200
        if range_header:
            m = re.match(r"bytes=(\d*)-(\d*)", range_header)
            if m:
                g1, g2 = m.group(1), m.group(2)
                if g1:
                    start = int(g1)
                    end = int(g2) if g2 else size - 1
                elif g2:  # suffix range: last N bytes
                    start = max(0, size - int(g2))
                start = min(start, size - 1)
                end = min(end, size - 1)
                status = 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(full, "rb") as fh:
            fh.seek(start)
            remaining = length
            chunk = 64 * 1024
            while remaining > 0:
                data = fh.read(min(chunk, remaining))
                if not data:
                    break
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(data)


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Soundtrack Player</title>
<style>
  :root {
    --bg:#1d1f21; --panel:#2b2f33; --panel2:#33383d; --line:#3d4349;
    --grass:#5d9c3b; --grass2:#7cc44f; --text:#e8eef2; --muted:#9aa5ad;
    --accent:#7cc44f;
  }
  * { box-sizing:border-box; }
  body {
    margin:0; font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
    background:var(--bg); color:var(--text);
    background-image:linear-gradient(rgba(0,0,0,.25),rgba(0,0,0,.45));
    min-height:100vh;
  }
  header {
    padding:18px 20px; border-bottom:3px solid #000;
    background:linear-gradient(180deg,var(--grass2),var(--grass));
    color:#12240a; text-shadow:1px 1px 0 rgba(255,255,255,.25);
  }
  header h1 { margin:0; font-size:20px; letter-spacing:1px; }
  header p { margin:4px 0 0; font-size:12px; opacity:.85; }
  .wrap { max-width:820px; margin:0 auto; padding:18px; }
  .list {
    background:var(--panel); border:2px solid #000; border-radius:6px;
    max-height:46vh; overflow:auto; margin-bottom:16px;
  }
  .row {
    display:flex; align-items:center; gap:10px; padding:9px 12px;
    border-bottom:1px solid var(--line); cursor:pointer; font-size:13px;
  }
  .row:last-child { border-bottom:none; }
  .row:hover { background:var(--panel2); }
  .row.active { background:#3a4a2a; color:var(--grass2); font-weight:bold; }
  .row .idx { color:var(--muted); width:34px; text-align:right; font-size:11px; }
  .row.active .idx { color:var(--grass2); }
  .row .eq { margin-left:auto; color:var(--grass2); opacity:0; font-size:11px; }
  .row.active .eq { opacity:1; }
  .player {
    background:var(--panel); border:2px solid #000; border-radius:6px;
    padding:16px; position:sticky; bottom:0;
  }
  .now { font-size:15px; margin-bottom:12px; min-height:20px; }
  .now .lbl { color:var(--muted); font-size:11px; }
  .seek { display:flex; align-items:center; gap:10px; margin-bottom:14px; }
  .time { font-size:11px; color:var(--muted); width:44px; text-align:center; }
  input[type=range] {
    -webkit-appearance:none; appearance:none; height:8px; border-radius:4px;
    background:var(--panel2); border:1px solid #000; outline:none; cursor:pointer;
  }
  #seekbar { flex:1; }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance:none; width:16px; height:16px; border-radius:3px;
    background:var(--grass2); border:1px solid #000; cursor:pointer;
  }
  .controls { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
  button {
    font-family:inherit; font-size:13px; color:var(--text);
    background:var(--panel2); border:2px solid #000; border-radius:4px;
    padding:9px 12px; cursor:pointer; min-width:44px;
  }
  button:hover { background:#41474d; }
  button:active { transform:translateY(1px); }
  #play { background:var(--grass); color:#12240a; font-weight:bold; min-width:64px; }
  #play:hover { background:var(--grass2); }
  .vol { display:flex; align-items:center; gap:8px; margin-left:auto; }
  .vol span { font-size:11px; color:var(--muted); }
  #volbar { width:120px; }
  .hint { font-size:11px; color:var(--muted); margin-top:10px; }
</style>
</head>
<body>
<header>
  <h1>⛏  Soundtrack Player</h1>
  <p id="sub">Loading tracks…</p>
</header>
<div class="wrap">
  <div class="list" id="list"></div>

  <div class="player">
    <div class="now"><span class="lbl">NOW PLAYING</span><br><span id="title">—</span></div>
    <div class="seek">
      <span class="time" id="cur">0:00</span>
      <input type="range" id="seekbar" min="0" max="1000" value="0" step="1">
      <span class="time" id="dur">0:00</span>
    </div>
    <div class="controls">
      <button id="prev" title="Previous">⏮</button>
      <button id="rw" title="Back 10s">« 10s</button>
      <button id="play" title="Play/Pause">▶ Play</button>
      <button id="ff" title="Forward 10s">10s »</button>
      <button id="next" title="Next">⏭</button>
      <div class="vol">
        <span>VOL</span>
        <input type="range" id="volbar" min="0" max="100" value="80">
        <span id="volval">80</span>
      </div>
    </div>
    <div class="hint">Space = play/pause · ← / → = seek 10s · ↑ / ↓ = volume · scrub the bar to jump anywhere</div>
  </div>
</div>

<audio id="audio" preload="metadata"></audio>
<script>
const audio = document.getElementById('audio');
const listEl = document.getElementById('list');
const titleEl = document.getElementById('title');
const seek = document.getElementById('seekbar');
const curEl = document.getElementById('cur');
const durEl = document.getElementById('dur');
const vol = document.getElementById('volbar');
const volval = document.getElementById('volval');
const playBtn = document.getElementById('play');
let tracks = [], idx = -1, seeking = false;

function fmt(s){ if(!isFinite(s)) return '0:00'; s=Math.floor(s); return Math.floor(s/60)+':'+String(s%60).padStart(2,'0'); }

function render(){
  listEl.innerHTML = '';
  tracks.forEach((t,i)=>{
    const r = document.createElement('div');
    r.className = 'row' + (i===idx?' active':'');
    r.innerHTML = `<span class="idx">${i+1}</span><span class="name">${t.title}</span><span class="eq">♪ playing</span>`;
    r.onclick = ()=>load(i,true);
    listEl.appendChild(r);
  });
}

function load(i, play){
  if(i<0||i>=tracks.length) return;
  idx = i;
  audio.src = '/media/' + encodeURIComponent(tracks[i].file);
  titleEl.textContent = tracks[i].title;
  render();
  const active = listEl.children[i];
  if(active) active.scrollIntoView({block:'nearest'});
  updateMediaMetadata();
  if(play){ audio.play().catch(()=>{}); }
}

function prev(){ load(idx<=0 ? tracks.length-1 : idx-1, true); }
function next(){ load(idx>=tracks.length-1 ? 0 : idx+1, true); }

playBtn.onclick = ()=>{ if(idx<0) load(0,true); else if(audio.paused) audio.play(); else audio.pause(); };
document.getElementById('prev').onclick = prev;
document.getElementById('next').onclick = next;
document.getElementById('rw').onclick = ()=>{ audio.currentTime = Math.max(0, audio.currentTime-10); };
document.getElementById('ff').onclick = ()=>{ audio.currentTime = Math.min(audio.duration||0, audio.currentTime+10); };

audio.onplay = ()=>{ playBtn.textContent = '⏸ Pause'; if('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing'; };
audio.onpause = ()=>{ playBtn.textContent = '▶ Play'; if('mediaSession' in navigator) navigator.mediaSession.playbackState = 'paused'; };
audio.onended = next;
audio.onloadedmetadata = ()=>{ durEl.textContent = fmt(audio.duration); updatePositionState(); };
audio.ontimeupdate = ()=>{
  if(seeking) return;
  curEl.textContent = fmt(audio.currentTime);
  if(audio.duration) seek.value = Math.round(audio.currentTime/audio.duration*1000);
};

seek.oninput = ()=>{ seeking = true; if(audio.duration) curEl.textContent = fmt(seek.value/1000*audio.duration); };
seek.onchange = ()=>{ if(audio.duration) audio.currentTime = seek.value/1000*audio.duration; seeking = false; };

vol.oninput = ()=>{ audio.volume = vol.value/100; volval.textContent = vol.value; };
audio.volume = vol.value/100;

document.addEventListener('keydown', e=>{
  if(e.target.tagName==='INPUT') return;
  if(e.code==='Space'){ e.preventDefault(); playBtn.click(); }
  else if(e.code==='ArrowRight'){ audio.currentTime = Math.min(audio.duration||0, audio.currentTime+10); }
  else if(e.code==='ArrowLeft'){ audio.currentTime = Math.max(0, audio.currentTime-10); }
  else if(e.code==='ArrowUp'){ e.preventDefault(); vol.value = Math.min(100, +vol.value+5); vol.oninput(); }
  else if(e.code==='ArrowDown'){ e.preventDefault(); vol.value = Math.max(0, +vol.value-5); vol.oninput(); }
});

// ---- Media Session API: route macOS media keys (fn+F7/F8/F9) & Now Playing ----
function updateMediaMetadata(){
  if(!('mediaSession' in navigator) || idx<0) return;
  navigator.mediaSession.metadata = new MediaMetadata({
    title: tracks[idx].title,
    artist: 'Soundtrack',
    album: 'minecraft-soundtrack-wav'
  });
}
function updatePositionState(){
  if(!('mediaSession' in navigator) || !('setPositionState' in navigator.mediaSession)) return;
  if(!isFinite(audio.duration) || audio.duration<=0) return;
  try {
    navigator.mediaSession.setPositionState({
      duration: audio.duration,
      playbackRate: audio.playbackRate || 1,
      position: Math.min(audio.currentTime, audio.duration)
    });
  } catch(e){}
}
if('mediaSession' in navigator){
  const ms = navigator.mediaSession;
  ms.setActionHandler('previoustrack', ()=> prev());          // fn+F7
  ms.setActionHandler('nexttrack',     ()=> next());          // fn+F9
  ms.setActionHandler('play',  ()=> audio.play().catch(()=>{}));   // fn+F8 (toggles)
  ms.setActionHandler('pause', ()=> audio.pause());               // fn+F8 (toggles)
  // Optional: OS scrubber + skip controls, harmless if unused by the keys
  try { ms.setActionHandler('seekto', d=>{ if(d.seekTime!=null) audio.currentTime = d.seekTime; updatePositionState(); }); } catch(e){}
  try { ms.setActionHandler('seekforward',  d=>{ audio.currentTime = Math.min(audio.duration||0, audio.currentTime+(d.seekOffset||10)); }); } catch(e){}
  try { ms.setActionHandler('seekbackward', d=>{ audio.currentTime = Math.max(0, audio.currentTime-(d.seekOffset||10)); }); } catch(e){}
  // keep the OS Now-Playing scrubber in sync
  setInterval(updatePositionState, 1000);
}

fetch('/api/tracks').then(r=>r.json()).then(data=>{
  tracks = data;
  document.getElementById('sub').textContent = tracks.length + ' tracks · ~/minecraft-soundtrack-wav';
  render();
  if(tracks.length) load(0,false);
});
</script>
</body>
</html>
"""


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    n = len(list_tracks())
    print(f"Serving {n} tracks from {MUSIC_DIR}")
    print(f"Player running at http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
