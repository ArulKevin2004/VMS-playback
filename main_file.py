#!/usr/bin/env python3
import argparse, math, os, subprocess, sys, textwrap
from pathlib import Path
from PIL import Image
import shutil

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed:\n{' '.join(cmd)}\nSTDERR:\n{p.stderr}")
    return p.stdout.strip()

def ffprobe_duration(path):
    return float(run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nokey=1:noprint_wrappers=1", str(path)
    ]))

def hhmmss_ms(t):
    # t in seconds -> "HH:MM:SS.mmm"
    hrs = int(t // 3600)
    t -= hrs * 3600
    mins = int(t // 60)
    secs = t - mins * 60
    return f"{hrs:02d}:{mins:02d}:{secs:06.3f}"

def write_demo_html(out_dir, tile_w, tile_h, video_filename):
    html = f"""\
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>YouTube-like Hover/Scrub Preview Demo</title>
<style>
  body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 32px; background: #fafafa; }}
  .player {{ width: 640px; max-width: 100%; }}
  .stage {{
    position: relative;
    width: 100%;
    aspect-ratio: 16/9;
    background: #000;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 14px rgba(0,0,0,.18);
    margin-bottom: 10px;
    user-select: none;
  }}
  .preview {{
    position: absolute; inset: 0;
    background-repeat: no-repeat;
    background-size: auto;
    display: grid; place-items: center;
    cursor: pointer;
  }}
  .preview::after {{
    content: "▶";
    position: absolute;
    font-size: 56px; line-height: 56px;
    color: rgba(255,255,255,.85);
    text-shadow: 0 2px 10px rgba(0,0,0,.4);
    opacity: .9; transition: opacity .2s ease;
    pointer-events: none;
  }}
  .preview.hovering::after {{ opacity: 0; }}
  video {{
    position: absolute; inset: 0; width: 100%; height: 100%;
    object-fit: cover;
    background: #000;
  }}
  .hidden {{ display: none !important; }}
  .controls {{
    display: grid; grid-template-columns: 1fr; gap: 10px;
  }}
  .scrubrow {{
    display: grid; grid-template-columns: 72px 1fr 72px; gap: 10px; align-items: center;
  }}
  .time {{ font-variant-numeric: tabular-nums; text-align: center; }}
  input[type="range"] {{ width: 100%; }}
  .note {{ margin-top: 10px; color: #666; font-size: 14px; }}
</style>
</head>
<body>
  <h2>YouTube-like Hover Preview</h2>
  <div class="player">
    <div class="stage" id="stage">
      <video id="video" class="hidden" src="{video_filename}" preload="metadata" playsinline muted></video>
      <div id="preview" class="preview" title="Hover to preview, click to play"></div>
    </div>

    <div class="controls">
      <div class="scrubrow">
        <div class="time" id="tcur">00:00:00.000</div>
        <input id="scrub" type="range" min="0" max="1" step="0.001" value="0" />
        <div class="time" id="tmax">00:00:00.000</div>
      </div>
    </div>

    <div class="note">
      • Hover the thumbnail to see a looping sprite-based preview.<br/>
      • Click the thumbnail to play the full video.
    </div>
  </div>

<script>
// Global state to track user interaction
let userHasInteracted = false;

async function parseVTT(url) {{
  const txt = await (await fetch(url)).text();
  const lines = txt.split(/\\r?\\n/);
  const cues = [];
  for (let i = 0; i < lines.length; i++) {{
    const line = lines[i].trim();
    if (!line) continue;
    if (line.includes('-->')) {{
      const [startStr, endStr] = line.split('-->').map(s => s.trim());
      let j = i + 1;
      while (j < lines.length && !lines[j].trim()) j++;
      if (j >= lines.length) break;
      const target = lines[j].trim();
      const m = target.match(/^(.*)#xywh=(\\d+),(\\d+),(\\d+),(\\d+)$/);
      if (!m) continue;
      const [_, url, x, y, w, h] = m;
      cues.push({{
        start: toSeconds(startStr),
        end: toSeconds(endStr),
        url, x: parseInt(x), y: parseInt(y), w: parseInt(w), h: parseInt(h)
      }});
      i = j;
    }}
  }}
  return cues;
}}

function toSeconds(hms) {{
  const [hh, mm, ss] = hms.split(':');
  return parseInt(hh)*3600 + parseInt(mm)*60 + parseFloat(ss);
}}

function formatTime(t) {{
  t = Math.max(0, t);
  const hh = Math.floor(t/3600);
  t -= hh*3600;
  const mm = Math.floor(t/60);
  const ss = (t - mm*60).toFixed(3);
  return `${{String(hh).padStart(2,'0')}}:${{String(mm).padStart(2,'0')}}:${{String(ss).padStart(6,'0')}}`;
}}

(async function() {{
  const preview = document.getElementById('preview');
  const video = document.getElementById('video');
  const scrub = document.getElementById('scrub');
  const tcur = document.getElementById('tcur');
  const tmax = document.getElementById('tmax');

  // Ensure first user interaction enables video playback
  function enableVideoPlayback() {{
    if (!userHasInteracted) {{
      userHasInteracted = true;
      video.muted = false;  // Unmute after first interaction
    }}
  }}

  // Add interaction listeners
  document.addEventListener('click', enableVideoPlayback);
  document.addEventListener('touchstart', enableVideoPlayback);
  document.addEventListener('keydown', enableVideoPlayback);

  const cues = await parseVTT('thumbnails.vtt');
  if (!cues.length) {{
    preview.textContent = 'No thumbnails.vtt found';
    preview.style.color = '#fff';
    return;
  }}

  const duration = cues[cues.length - 1].end;
  scrub.max = duration.toString();
  tmax.textContent = formatTime(duration);

  function setPreviewFromTime(t) {{
    let lo = 0, hi = cues.length - 1, idx = 0;
    while (lo <= hi) {{
      const mid = (lo + hi) >> 1;
      if (cues[mid].start <= t) {{ idx = mid; lo = mid + 1; }}
      else hi = mid - 1;
    }}
    const c = cues[idx];
    preview.style.backgroundImage = `url(${{c.url}})`;
    preview.style.backgroundPosition = `-${{c.x}}px -${{c.y}}px`;
    preview.style.width = c.w + 'px';
    preview.style.height = c.h + 'px';
  }}

  function clamp(v, lo, hi) {{ return Math.max(lo, Math.min(hi, v)); }}

  // Initial preview
  setPreviewFromTime(0);
  tcur.textContent = '00:00:00.000';

  // Hover preview logic
  let animId = null;
  let hoverTime = 0;
  const HOVER_SPEED = 1.0;

  function loop(tsPrev) {{
    let last = tsPrev;
    function frame(ts) {{
      const dt = (ts - last) / 1000;
      last = ts;
      hoverTime = (hoverTime + dt * HOVER_SPEED);
      if (hoverTime > duration) hoverTime = 0;
      setPreviewFromTime(hoverTime);
      
      // Play video during hover with user interaction check
      if (preview.classList.contains('hovering')) {{
        if (video.paused) {{
          try {{
            video.currentTime = hoverTime;
            if (userHasInteracted) {{
              video.play().catch(e => {{
                console.log('Hover play prevented:', e);
              }});
            }}
          }} catch (e) {{
            console.log('Video hover error:', e);
          }}
        }}
      }}
      
      animId = requestAnimationFrame(frame);
    }}
    animId = requestAnimationFrame(frame);
  }}

  preview.addEventListener('mouseenter', () => {{
    preview.classList.add('hovering');
    hoverTime = parseFloat(scrub.value) || 0;
    if (!animId) loop(performance.now());
  }});

  preview.addEventListener('mouseleave', () => {{
    preview.classList.remove('hovering');
    if (animId) {{
      cancelAnimationFrame(animId);
      animId = null;
    }}
    video.pause();
    // Snap back to scrub time
    const t = parseFloat(scrub.value) || 0;
    setPreviewFromTime(t);
  }});

  // Click to fully play
  preview.addEventListener('click', () => {{
    enableVideoPlayback();
    preview.classList.add('hidden');
    video.classList.remove('hidden');
    video.currentTime = parseFloat(scrub.value) || 0;
    if (userHasInteracted) {{
      video.play().catch(e => {{
        console.log('Play error:', e);
      }});
    }}
  }});

  // Scrub updates preview
  scrub.addEventListener('input', () => {{
    const t = clamp(parseFloat(scrub.value), 0, duration);
    scrub.value = String(t);
    tcur.textContent = formatTime(t);
    setPreviewFromTime(t);
  }});

  // Live peek on slider hover
  scrub.addEventListener('mousemove', (e) => {{
    const rect = scrub.getBoundingClientRect();
    const ratio = clamp((e.clientX - rect.left) / rect.width, 0, 1);
    const t = ratio * duration;
    setPreviewFromTime(t);
  }});
}})();
</script>
</body>
</html>
"""
    (Path(out_dir) / "demo.html").write_text(html, encoding="utf-8")

def main():
    ap = argparse.ArgumentParser(description="Generate sprite sheets + WebVTT for hover/scrub previews.")
    ap.add_argument("input", help="Input video file (e.g., input.mp4)")
    ap.add_argument("outdir", help="Output directory")
    ap.add_argument("--interval", type=float, default=2.0, help="Seconds per thumbnail frame (default: 2.0)")
    ap.add_argument("--tile", default="10x10", help="Grid per sprite sheet: CxR (default: 10x10)")
    ap.add_argument("--tile-size", default="160x90", help="Size of each thumbnail (w x h) (default: 160x90)")
    ap.add_argument("--format", default="webp", choices=["webp","jpg","jpeg","png"], help="Sprite image format (default: webp)")
    args = ap.parse_args()

    # Use absolute paths to resolve path issues
    inp = Path(args.input).resolve()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    frames_dir = outdir / "frames"
    frames_dir.mkdir(exist_ok=True)

    # Copy input video to output directory
    video_filename = inp.name
    video_dest = outdir / video_filename
    shutil.copy2(inp, video_dest)

    cols, rows = map(int, args.tile.lower().split("x"))
    tile_w, tile_h = map(int, args.tile_size.lower().split("x"))
    per_sheet = cols * rows
    duration = ffprobe_duration(inp)
    interval = float(args.interval)
    total_frames = int(math.ceil(duration / interval))
    print(f"Duration: {duration:.3f}s | interval={interval}s -> {total_frames} frames | grid={cols}x{rows}")

    # 1) Extract normalized thumbnails (letterboxed to tile_w x tile_h)
    #    We maintain aspect ratio and pad to exact tile size.
    vf = f"fps=1/{interval},scale={tile_w}:{tile_h}:force_original_aspect_ratio=decrease,pad={tile_w}:{tile_h}:(ow-iw)/2:(oh-ih)/2:color=black"
    extract_cmd = [
        "ffmpeg", "-y", "-i", str(inp),
        "-vf", vf,
        "-q:v", "5",
        str(frames_dir / "thumb_%05d.jpg")
    ]
    print("Extracting frames with ffmpeg...")
    run(extract_cmd)

    # 2) Load frames, assemble sprite sheets
    frame_paths = sorted(frames_dir.glob("thumb_*.jpg"))
    if not frame_paths:
        print("No frames extracted; aborting.")
        sys.exit(1)

    sprite_files = []
    print("Assembling sprite sheets...")
    for sheet_idx in range(math.ceil(len(frame_paths) / per_sheet)):
        chunk = frame_paths[sheet_idx*per_sheet : (sheet_idx+1)*per_sheet]
        sprite = Image.new("RGB", (cols*tile_w, rows*tile_h), (0,0,0))
        for i, fp in enumerate(chunk):
            img = Image.open(fp).convert("RGB")
            r = i // cols
            c = i % cols
            sprite.paste(img, (c*tile_w, r*tile_h))
        sprite_name = f"sprite_{sheet_idx}.{args.format}"
        sprite_path = outdir / sprite_name
        save_kwargs = {}
        if args.format == "webp":
            save_kwargs = {"method": 6, "quality": 80}
        elif args.format in ("jpg","jpeg"):
            save_kwargs = {"quality": 85}
        sprite.save(sprite_path, **save_kwargs)
        sprite_files.append(sprite_name)
        print(f"  wrote {sprite_name} ({len(chunk)} tiles)")

    # 3) Write WebVTT mapping time -> sprite#xywh
    vtt = ["WEBVTT", ""]
    for idx in range(total_frames):
        start = idx * interval
        end = min(duration, start + interval)
        sheet = idx // per_sheet
        pos = idx % per_sheet
        r = pos // cols
        c = pos % cols
        x = c * tile_w
        y = r * tile_h
        url = sprite_files[sheet]
        vtt.append(f"{hhmmss_ms(start)} --> {hhmmss_ms(end)}")
        vtt.append(f"{url}#xywh={x},{y},{tile_w},{tile_h}")
        vtt.append("")  # blank line between cues
    (outdir / "thumbnails.vtt").write_text("\n".join(vtt), encoding="utf-8")
    print("Wrote thumbnails.vtt")

    # 4) Write a ready-to-open HTML demo
    write_demo_html(outdir, tile_w, tile_h, video_filename)
    print("Wrote demo.html")
    print("\nDone. Start a static server in the output folder and open demo.html, e.g.:")
    print(f"  cd {outdir}")
    print(f"  python -m http.server 8000  # then visit http://localhost:8000/demo.html")

if __name__ == "__main__":
    main()
