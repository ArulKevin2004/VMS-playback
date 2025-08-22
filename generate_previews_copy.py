# #!/usr/bin/env python3
# import argparse, math, os, subprocess, sys
# from pathlib import Path
# from PIL import Image

# def run(cmd):
#     p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
#     if p.returncode != 0:
#         raise RuntimeError(f"Command failed:\n{' '.join(cmd)}\nSTDERR:\n{p.stderr}")
#     return p.stdout.strip()

# def ffprobe_duration(path):
#     return float(run([
#         "ffprobe", "-v", "error", "-show_entries", "format=duration",
#         "-of", "default=nokey=1:noprint_wrappers=1", str(path)
#     ]))

# def hhmmss_ms(t):
#     hrs = int(t // 3600)
#     t -= hrs * 3600
#     mins = int(t // 60)
#     secs = t - mins*60
#     return f"{hrs:02d}:{mins:02d}:{secs:06.3f}"

# def write_demo_html(out_dir, tile_w, tile_h):
#     # HTML with: sprite hover autoplay, scrub preview, click-to-play real video
#     html = f"""\
# <!doctype html>
# <html>
# <head>
# <meta charset="utf-8" />
# <title>YouTube-style Hover & Play Preview</title>
# <meta name="viewport" content="width=device-width, initial-scale=1" />
# <style>
#   :root {{
#     --w: 640px;
#   }}
#   body {{
#     font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
#     margin: 32px;
#     background: #fafafa;
#     color: #111;
#   }}
#   h2 {{ margin: 0 0 12px; }}
#   .player {{
#     width: var(--w);
#     max-width: 100%;
#   }}
#   .stage {{
#     position: relative;
#     width: 100%;
#     aspect-ratio: 16/9;
#     background: #000;
#     border-radius: 12px;
#     overflow: hidden;
#     box-shadow: 0 2px 14px rgba(0,0,0,.18);
#     margin-bottom: 10px;
#     user-select: none;
#   }}
#   /* Sprite preview "thumbnail" that animates on hover */
#   .preview {{
#     position: absolute; inset: 0;
#     background-repeat: no-repeat;
#     background-size: auto; /* we control via xywh window */
#     display: grid; place-items: center;
#     cursor: pointer;
#   }}
#   .preview::after {{
#     content: "▶";
#     position: absolute;
#     font-size: 56px; line-height: 56px;
#     color: rgba(255,255,255,.85);
#     text-shadow: 0 2px 10px rgba(0,0,0,.4);
#     opacity: .9; transition: opacity .2s ease;
#     pointer-events: none;
#   }}
#   .preview.hovering::after {{ opacity: 0; }}
#   /* Actual video sits behind the preview; revealed on click */
#   video {{
#     position: absolute; inset: 0; width: 100%; height: 100%;
#     object-fit: cover;
#     background: #000;
#   }}
#   .hidden {{ display: none !important; }}

#   .controls {{
#     display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: center;
#   }}
#   .scrubrow {{
#     display: grid; grid-template-columns: 72px 1fr 72px; gap: 10px; align-items: center;
#   }}
#   .time {{ font-variant-numeric: tabular-nums; text-align: center; }}
#   input[type="range"] {{ width: 100%; }}
#   .buttons {{ display: flex; gap: 8px; justify-content: flex-end; }}
#   .btn {{
#     padding: 8px 12px;
#     border-radius: 10px;
#     border: 1px solid #ddd;
#     background: #fff;
#     cursor: pointer;
#   }}
#   .btn:hover {{ background: #f2f2f2; }}
#   .note {{ margin-top: 10px; color: #666; font-size: 14px; }}
# </style>
# </head>
# <body>
#   <h2>YouTube-like Hover Preview + Click to Play</h2>
#   <div class="player">
#     <div class="stage" id="stage">
#       <video id="video" class="hidden" src="video.mp4" preload="metadata" playsinline></video>
#       <div id="preview" class="preview" title="Click to play"></div>
#     </div>

#     <div class="controls">
#       <div class="scrubrow">
#         <div class="time" id="tcur">00:00:00.000</div>
#         <input id="scrub" type="range" min="0" max="1" step="0.001" value="0" />
#         <div class="time" id="tmax">00:00:00.000</div>
#       </div>
#       <div class="buttons">
#         <button class="btn" id="btnPlay">Play</button>
#         <button class="btn" id="btnPause">Pause</button>
#         <button class="btn" id="btnBackToPreview">Back to Preview</button>
#       </div>
#     </div>

#     <div class="note">
#       • Hover the thumbnail to see a looping sprite-based preview (no video buffering).<br/>
#       • Click the thumbnail (or “Play”) to switch to the real video. Scrubber syncs both ways.
#     </div>
#   </div>

# <script>
# async function parseVTT(url) {{
#   const txt = await (await fetch(url)).text();
#   const lines = txt.split(/\\r?\\n/);
#   const cues = [];
#   for (let i = 0; i < lines.length; i++) {{
#     const line = lines[i].trim();
#     if (!line) continue;
#     if (line.includes('-->')) {{
#       const [startStr, endStr] = line.split('-->').map(s => s.trim());
#       // Next non-empty line is target "file#xywh=x,y,w,h"
#       let j = i + 1;
#       while (j < lines.length && !lines[j].trim()) j++;
#       if (j >= lines.length) break;
#       const target = lines[j].trim();
#       const m = target.match(/^(.*)#xywh=(\\d+),(\\d+),(\\d+),(\\d+)$/);
#       if (!m) continue;
#       const [_, url2, x, y, w, h] = m;
#       cues.push({{
#         start: toSeconds(startStr),
#         end: toSeconds(endStr),
#         url: url2, x: +x, y: +y, w: +w, h: +h
#       }});
#       i = j;
#     }}
#   }}
#   return cues;
# }}
# function toSeconds(hms) {{
#   const [hh, mm, ss] = hms.split(':');
#   return (+hh)*3600 + (+mm)*60 + parseFloat(ss);
# }}
# function formatTime(t) {{
#   t = Math.max(0, t);
#   const hh = Math.floor(t/3600);
#   t -= hh*3600;
#   const mm = Math.floor(t/60);
#   const ss = (t - mm*60).toFixed(3);
#   return `${{String(hh).padStart(2,'0')}}:${{String(mm).padStart(2,'0')}}:${{String(ss).padStart(6,'0')}}`;
# }}

# (async function main() {{
#   const preview = document.getElementById('preview');
#   const video = document.getElementById('video');
#   const scrub = document.getElementById('scrub');
#   const tcur = document.getElementById('tcur');
#   const tmax = document.getElementById('tmax');
#   const btnPlay = document.getElementById('btnPlay');
#   const btnPause = document.getElementById('btnPause');
#   const btnBack = document.getElementById('btnBackToPreview');

#   const cues = await parseVTT('thumbnails.vtt');
#   if (!cues.length) {{
#     preview.textContent = 'No thumbnails.vtt found';
#     preview.style.color = '#fff';
#     return;
#   }}

#   const duration = cues[cues.length - 1].end;
#   scrub.max = duration.toString();
#   tmax.textContent = formatTime(duration);

#   // === Helpers ===
#   function setPreviewFromTime(t) {{
#     // binary search for last cue with start <= t
#     let lo = 0, hi = cues.length - 1, idx = 0;
#     while (lo <= hi) {{
#       const mid = (lo + hi) >> 1;
#       if (cues[mid].start <= t) {{ idx = mid; lo = mid + 1; }}
#       else hi = mid - 1;
#     }}
#     const c = cues[idx];
#     preview.style.backgroundImage = `url(${{c.url}})`;
#     preview.style.backgroundPosition = `-${{c.x}}px -${{c.y}}px`;
#     preview.style.width = c.w + 'px';
#     preview.style.height = c.h + 'px';

#     // Center the xywh “window” inside the stage
#     // by scaling the preview box with transform, keeping aspect.
#     const stage = preview.parentElement.getBoundingClientRect();
#     const scaleW = stage.width / c.w;
#     const scaleH = stage.height / c.h;
#     const scale = Math.min(scaleW, scaleH);
#     preview.style.transformOrigin = 'top left';
#     preview.style.transform = `translate(calc(50% - ${{c.w/2}}px), calc(50% - ${{c.h/2}}px)) scale(${{scale}})`;
#   }}

#   function clamp(v, lo, hi) {{ return Math.max(lo, Math.min(hi, v)); }}

#   // === Init preview at 0 ===
#   setPreviewFromTime(0);
#   tcur.textContent = '00:00:00.000';

#   // === Hover autoplay over thumbnail ===
#   let animId = null;
#   let hoverTime = 0;
#   const HOVER_SPEED = 1.0; // 1x realtime
#   function loop(tsPrev) {{
#     let last = tsPrev;
#     function frame(ts) {{
#       const dt = (ts - last) / 1000; // seconds
#       last = ts;
#       hoverTime = (hoverTime + dt * HOVER_SPEED);
#       if (hoverTime > duration) hoverTime = 0;
#       setPreviewFromTime(hoverTime);
#       animId = requestAnimationFrame(frame);
#     }}
#     animId = requestAnimationFrame(frame);
#   }}

#   preview.addEventListener('mouseenter', () => {{
#     preview.classList.add('hovering');
#     // start from current scrub position for continuity
#     hoverTime = parseFloat(scrub.value) || 0;
#     if (!animId) loop(performance.now());
#   }});
#   preview.addEventListener('mouseleave', () => {{
#     preview.classList.remove('hovering');
#     if (animId) cancelAnimationFrame(animId);
#     animId = null;
#     // Snap back to scrub time
#     const t = parseFloat(scrub.value) || 0;
#     setPreviewFromTime(t);
#   }});

#   // === Scrub updates preview and (if visible) video ===
#   function setTimeAll(t) {{
#     t = clamp(t, 0, duration);
#     scrub.value = String(t);
#     tcur.textContent = formatTime(t);
#     setPreviewFromTime(t);
#     if (!video.classList.contains('hidden')) {{
#       if (Math.abs(video.currentTime - t) > 0.25) {{
#         video.currentTime = t;
#       }}
#     }}
#   }}
#   scrub.addEventListener('input', () => setTimeAll(parseFloat(scrub.value)));
#   scrub.addEventListener('mousemove', (e) => {{
#     // live peek on hover of slider (like YouTube)
#     const rect = scrub.getBoundingClientRect();
#     const ratio = clamp((e.clientX - rect.left) / rect.width, 0, 1);
#     const t = ratio * duration;
#     setPreviewFromTime(t);
#   }});
#   scrub.addEventListener('mouseleave', () => {{
#     // restore preview to scrub value
#     setPreviewFromTime(parseFloat(scrub.value) || 0);
#   }});

#   // === Click thumbnail to show real video ===
#   function showVideo(atTime) {{
#     preview.classList.add('hidden');
#     video.classList.remove('hidden');
#     video.currentTime = clamp(atTime ?? parseFloat(scrub.value) || 0, 0, duration);
#     video.play();
#   }}
#   function backToPreview() {{
#     video.pause();
#     video.classList.add('hidden');
#     preview.classList.remove('hidden');
#     // reflect latest video time into UI
#     setTimeAll(video.currentTime || parseFloat(scrub.value) || 0);
#   }}

#   preview.addEventListener('click', () => showVideo(parseFloat(scrub.value) || 0));
#   document.getElementById('btnPlay').addEventListener('click', () => showVideo(parseFloat(scrub.value) || 0));
#   document.getElementById('btnPause').addEventListener('click', () => video.pause());
#   document.getElementById('btnBackToPreview').addEventListener('click', backToPreview);

#   // Keep scrub label in sync while video plays
#   video.addEventListener('timeupdate', () => {{
#     if (!video.paused && !video.seeking) {{
#       const t = clamp(video.currentTime, 0, duration);
#       scrub.value = String(t);
#       tcur.textContent = formatTime(t);
#     }}
#   }});
#   // When metadata loaded, clamp duration (in case VTT shorter)
#   video.addEventListener('loadedmetadata', () => {{
#     // If real video is longer than VTT, keep scrub limited to VTT for preview consistency
#   }});
# }})();
# </script>
# </body>
# </html>
# """
#     (Path(out_dir) / "demo.html").write_text(html, encoding="utf-8")

# def main():
#     ap = argparse.ArgumentParser(description="Generate sprite sheets + WebVTT + web video for hover/scrub previews.")
#     ap.add_argument("input", help="Input video file (e.g., input.mp4)")
#     ap.add_argument("outdir", help="Output directory")
#     ap.add_argument("--interval", type=float, default=2.0, help="Seconds per thumbnail frame (default: 2.0)")
#     ap.add_argument("--tile", default="10x10", help="Grid per sprite sheet: CxR (default: 10x10)")
#     ap.add_argument("--tile-size", default="160x90", help="Size of each thumbnail (w x h) (default: 160x90)")
#     ap.add_argument("--format", default="webp", choices=["webp","jpg","jpeg","png"], help="Sprite image format (default: webp)")
#     ap.add_argument("--transcode", action="store_true",
#                     help="Force transcode to H.264/AAC (recommended for broad browser support).")
#     ap.add_argument("--target-width", type=int, default=1280, help="Transcode width (default: 1280).")
#     ap.add_argument("--bitrate", default="1800k", help="Video bitrate for transcode (default: 1800k).")
#     args = ap.parse_args()

#     inp = Path(args.input)
#     outdir = Path(args.outdir)
#     outdir.mkdir(parents=True, exist_ok=True)
#     frames_dir = outdir / "frames"
#     frames_dir.mkdir(exist_ok=True)

#     cols, rows = map(int, args.tile.lower().split("x"))
#     tile_w, tile_h = map(int, args.tile_size.lower().split("x"))
#     per_sheet = cols * rows
#     duration = ffprobe_duration(inp)
#     interval = float(args.interval)
#     total_frames = int(math.ceil(duration / interval))
#     print(f"Duration: {duration:.3f}s | interval={interval}s -> {total_frames} frames | grid={cols}x{rows}")

#     # 0) Prepare web-friendly mp4 (faststart, baseline H.264, AAC)
#     #    If input is already H.264/AAC+mp4, we can just copy unless --transcode is requested.
#     out_video = outdir / "video.mp4"
#     if args.transcode:
#         # Transcode with keyint ~1s to make seeks snappy
#         print("Transcoding to web-friendly MP4...")
#         run([
#             "ffmpeg","-y","-i",str(inp),
#             "-vf", f"scale='min({args.target_width},iw)':-2",
#             "-c:v","libx264","-preset","veryfast","-profile:v","high","-crf","23",
#             "-x264-params","keyint=48:min-keyint=48:scenecut=0",
#             "-b:v", args.bitrate,
#             "-movflags","+faststart",
#             "-c:a","aac","-b:a","128k",
#             str(out_video)
#         ])
#     else:
#         # Try stream copy; if it fails, user can re-run with --transcode
#         try:
#             print("Copying to MP4 container (no transcode). Use --transcode if this fails in browser.")
#             run([
#                 "ffmpeg","-y","-i",str(inp),
#                 "-c","copy","-movflags","+faststart", str(out_video)
#             ])
#         except Exception as e:
#             print("Container copy failed; falling back to transcode (use --transcode to control params).")
#             run([
#                 "ffmpeg","-y","-i",str(inp),
#                 "-vf", f"scale='min({args.target_width},iw)':-2",
#                 "-c:v","libx264","-preset","veryfast","-profile:v","high","-crf","23",
#                 "-x264-params","keyint=48:min-keyint=48:scenecut=0",
#                 "-b:v", args.bitrate,
#                 "-movflags","+faststart",
#                 "-c:a","aac","-b:a","128k",
#                 str(out_video)
#             ])

#     # 1) Extract thumbnails normalized to tile size (maintain AR, pad)
#     vf = f"fps=1/{interval},scale={tile_w}:{tile_h}:force_original_aspect_ratio=decrease,pad={tile_w}:{tile_h}:(ow-iw)/2:(oh-ih)/2:color=black"
#     print("Extracting frames with ffmpeg...")
#     run([
#         "ffmpeg","-y","-i",str(inp),
#         "-vf", vf,
#         "-q:v","5",
#         str(frames_dir / "thumb_%05d.jpg")
#     ])

#     # 2) Assemble sprite sheets
#     frame_paths = sorted(frames_dir.glob("thumb_*.jpg"))
#     if not frame_paths:
#         print("No frames extracted; aborting."); sys.exit(1)

#     sprite_files = []
#     print("Assembling sprite sheets...")
#     for sheet_idx in range(math.ceil(len(frame_paths) / per_sheet)):
#         chunk = frame_paths[sheet_idx*per_sheet : (sheet_idx+1)*per_sheet]
#         sprite = Image.new("RGB", (cols*tile_w, rows*tile_h), (0,0,0))
#         for i, fp in enumerate(chunk):
#             img = Image.open(fp).convert("RGB")
#             r = i // cols
#             c = i % cols
#             sprite.paste(img, (c*tile_w, r*tile_h))
#         sprite_name = f"sprite_{sheet_idx}.{args.format}"
#         sprite_path = outdir / sprite_name
#         save_kwargs = {}
#         if args.format == "webp":
#           save_kwargs = { "method": 6, "quality": 80 }
#         elif args.format in ("jpg","jpeg"):
#           save_kwargs = { "quality": 85 }
#         else:
#           save_kwargs = {}
#         sprite.save(sprite_path, **save_kwargs)
#         sprite_files.append(sprite_name)
#         print(f"  wrote {{sprite_name}} ({{len(chunk)}} tiles)")

#     # 3) Write WebVTT mapping time -> sprite#xywh
#     vtt_lines = ["WEBVTT", ""]
#     for idx in range(total_frames):
#         start = idx * interval
#         end = min(duration, start + interval)
#         sheet = idx // per_sheet
#         pos = idx % per_sheet
#         r = pos // cols
#         c = pos % cols
#         x = c * tile_w
#         y = r * tile_h
#         url = sprite_files[sheet]
#         vtt_lines.append(f"{{hhmmss_ms(start)}} --> {{hhmmss_ms(end)}}")
#         vtt_lines.append(f"{{url}}#xywh={{x}},{{y}},{{tile_w}},{{tile_h}}")
#         vtt_lines.append("")
#     (outdir / "thumbnails.vtt").write_text("\\n".join(vtt_lines), encoding="utf-8")
#     print("Wrote thumbnails.vtt")

#     # 4) Write upgraded HTML demo
#     write_demo_html(outdir, tile_w, tile_h)
#     print("Wrote demo.html")

#     print("\\nDone. Serve the folder and open demo.html, e.g.:")
#     print(f"  cd {{outdir}}")
#     print("  python -m http.server 8000  # visit http://localhost:8000/demo.html")

# if __name__ == "__main__":
#     main()


#!/usr/bin/env python3
import argparse, math, os, subprocess, sys, textwrap
from pathlib import Path
from PIL import Image

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

def write_demo_html(out_dir, tile_w, tile_h):
    html = f"""\
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>Hover/Scrub Preview Demo</title>
<style>
  body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 32px; }}
  .player {{ width: 640px; }}
  .preview {{
    width: {tile_w}px; height: {tile_h}px;
    background-repeat: no-repeat; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.15);
    margin-bottom: 12px; background-color: #000;
  }}
  .controls {{ display: flex; align-items: center; gap: 12px; }}
  .time {{ width: 72px; text-align: right; font-variant-numeric: tabular-nums; }}
  input[type="range"] {{ width: 100%; }}
  .note {{ margin-top: 12px; color: #666; font-size: 14px; }}
</style>
</head>
<body>
  <h2>Thumbnail/Sprite Preview (YouTube-style)</h2>
  <div class="player">
    <div id="preview" class="preview"></div>
    <div class="controls">
      <div class="time" id="tlabel">00:00:00.000</div>
      <input id="scrub" type="range" min="0" max="1" step="0.001" value="0" />
    </div>
    <div class="note">Move/drag the slider to scrub. Preview is built from image sprites via <code>thumbnails.vtt</code>.</div>
  </div>

<script>
async function parseVTT(url) {{
  const txt = await (await fetch(url)).text();
  const lines = txt.split(/\\r?\\n/);
  const cues = [];
  for (let i = 0; i < lines.length; i++) {{
    const line = lines[i].trim();
    if (!line) continue;
    if (line.includes('-->')) {{
      const [startStr, endStr] = line.split('-->').map(s => s.trim());
      // Next non-empty line is the target "file#xywh=x,y,w,h"
      let j = i + 1;
      while (j < lines.length && !lines[j].trim()) j++;
      if (j >= lines.length) break;
      const target = lines[j].trim(); // e.g., "sprite_0.webp#xywh=320,180,160,90"
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
  // "HH:MM:SS.mmm"
  const [hh, mm, ss] = hms.split(':');
  return parseInt(hh)*3600 + parseInt(mm)*60 + parseFloat(ss);
}}

function formatTime(t) {{
  const sign = t < 0 ? "-" : "";
  t = Math.max(0, t);
  const hh = Math.floor(t/3600);
  t -= hh*3600;
  const mm = Math.floor(t/60);
  const ss = (t - mm*60).toFixed(3);
  return `${{sign}}${{String(hh).padStart(2,'0')}}:${{String(mm).padStart(2,'0')}}:${{String(ss).padStart(6,'0')}}`;
}}

(async function() {{
  const cues = await parseVTT('thumbnails.vtt');
  const preview = document.getElementById('preview');
  const scrub = document.getElementById('scrub');
  const tlabel = document.getElementById('tlabel');

  if (cues.length === 0) {{
    preview.textContent = 'No cues found';
    preview.style.color = '#fff';
    preview.style.display = 'grid';
    preview.style.placeItems = 'center';
    return;
  }}

  const duration = cues[cues.length - 1].end;
  scrub.max = duration.toString();

  function setTime(t) {{
    t = Math.max(0, Math.min(duration, t));
    tlabel.textContent = formatTime(t);
    // find cue where start <= t < end (fallback to closest prior)
    let lo = 0, hi = cues.length - 1, idx = 0;
    while (lo <= hi) {{
      const mid = (lo + hi) >> 1;
      if (cues[mid].start <= t) {{ idx = mid; lo = mid + 1; }}
      else hi = mid - 1;
    }}
    const c = cues[idx];
    // Update preview from sprite sheet + xywh
    preview.style.backgroundImage = `url(${{c.url}})`;
    preview.style.backgroundPosition = `-${{c.x}}px -${{c.y}}px`;
    preview.style.width = c.w + 'px';
    preview.style.height = c.h + 'px';
  }}

  // initial frame
  setTime(0);

  scrub.addEventListener('input', (e) => setTime(parseFloat(scrub.value)));
  // Show preview on hover move as well
  scrub.addEventListener('mousemove', (e) => {{
    const rect = scrub.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    setTime(ratio * duration);
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

    inp = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    frames_dir = outdir / "frames"
    frames_dir.mkdir(exist_ok=True)

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
    write_demo_html(outdir, tile_w, tile_h)
    print("Wrote demo.html")
    print("\nDone. Start a static server in the output folder and open demo.html, e.g.:")
    print(f"  cd {outdir}")
    print(f"  python -m http.server 8000  # then visit http://localhost:8000/demo.html")

if __name__ == "__main__":
    main()

