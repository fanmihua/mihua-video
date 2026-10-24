#!/usr/bin/env python3
"""Clean the creator's own voice recording into assets/voice/voice.wav (48 kHz mono, -16 LUFS).

    python3 tools/prep_voice.py 口播.MP3        (path to the recording)

Chain: 75 Hz high-pass → light denoise → gentle 2.2:1 compression → +1.5 dB presence at 3.5 kHz →
two-pass linear loudnorm to -16 LUFS, true peak -1.5 dB. Linear mode keeps the speaker's natural dynamics;
it only moves the level. The master loudness is set later in tools/mix.py.
"""
import json, subprocess, sys, re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
src = sys.argv[1]
out_dir = root / "assets/voice"; out_dir.mkdir(parents=True, exist_ok=True)
pre, out = out_dir / "voice_pre.wav", out_dir / "voice.wav"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", "48000", "-af",
                "highpass=f=75,afftdn=nf=-30,acompressor=threshold=-20dB:ratio=2.2:attack=8:release=120:makeup=1,"
                "equalizer=f=3500:t=q:w=1.2:g=1.5", str(pre)], check=True)
m = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(pre), "-af", "loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json", "-f", "null", "-"],
                   capture_output=True, text=True).stderr
j = json.loads(m[m.rindex("{"): m.rindex("}") + 1])
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(pre), "-af",
                f"loudnorm=I=-16:TP=-1.5:LRA=7:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
                f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true", "-ar", "48000", str(out)], check=True)
r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
I = re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1]; P = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)[-1]
d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
print(f"voice → {out.relative_to(root)} · {float(d):.2f}s · {I} LUFS · peak {P} dBFS (input was {j['input_i']} LUFS, TP {j['input_tp']})")
