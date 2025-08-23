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

    # 4) Generate a thumbnail at the midpoint of the video
    thumbnail_cmd = [
        "ffmpeg", "-y", 
        "-i", str(inp), 
        "-ss", str(duration/2),  # Seek to midpoint 
        "-vframes", "1",  # Capture only one frame
        "-q:v", "2",  # High quality
        str(outdir / "thumbnail.jpg")
    ]
    print("Generating thumbnail...")
    run(thumbnail_cmd)
    print("Wrote thumbnail.jpg")
    print("\nDone. Generated sprite sheets, WebVTT, and thumbnail.")

if __name__ == "__main__":
    main()
