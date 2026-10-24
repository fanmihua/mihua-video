#!/usr/bin/env python3
"""Final audio mix: voice + music bed (ducked under the voice) + sound effects → one track.

    python3 tools/mix.py [config.json]   (run after tools/build.mjs with the same config)

voice : assets/voice/voice.wav (-16 LUFS), placed at timing "voice_offset"
music : assets/music/bed.wav, base -9 dB, lifted in the music-only intro and after the last line,
        side-chain compressed by the voice so it steps back whenever the voice speaks
sfx   : sfx.json entries (act + cue + offset), soft, summed on their own bus
master: one uniform gain to the config "loudness" (default -10 LUFS) + peak limiter at -1.5 dBFS → config "mix"
rides : optional config "rides" — audible volume moves for a demo in the voice-over, e.g. "整体偏小 → 一起调大":
        {"bus": "all"|"music", "from": "actJ.l22", "to": "actJ.l23+0.1", "db": -9, "in": 0.35, "out": 1.2}
        the gain reaches `db` at `from` (ramping over `in` s before it), holds until `to`, returns over `out` s.
        `<act>.start` / `<act>.end` mark an act's edges.
"""
import json, subprocess, re, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
cfg = json.loads((root / (sys.argv[1] if len(sys.argv) > 1 else "video.config.json")).read_text(encoding="utf8"))
TARGET = cfg.get("loudness", -10)                  # master loudness (LUFS)
timing = json.loads((root / cfg["timing"]).read_text(encoding="utf8"))
acts = {a["id"]: a for a in json.loads((root / "timing/acts.generated.json").read_text(encoding="utf8"))}
sfx_path = root / cfg.get("sfx", "sfx.json")
sfx = json.loads(sfx_path.read_text(encoding="utf8")) if sfx_path.exists() else []
total = max(a["end"] for a in acts.values())
vo_off = timing.get("voice_offset", 0)
first, last_end = timing["lines"][0]["start"], timing["lines"][-1]["end"]

inputs = ["-i", str(root / cfg.get("voiceFile", "assets/voice/voice.wav")), "-i", str(root / cfg.get("music", "assets/music/bed.wav"))]
fx = []
for i, s in enumerate(sfx):
    a = acts[s["act"]]; base = a["C"][s["cue"]] if s.get("cue") else 0
    t = max(0.0, a["start"] + base + s.get("offset", 0))
    inputs += ["-i", str(root / "assets/sfx" / f"{s['file']}.mp3")]
    fx.append((2 + i, t, s["vol"]))

def cue_time(ref):
    m = re.fullmatch(r"(act\w+)\.(\w+)([+-][\d.]+)?", ref.replace(" ", ""))
    a = acts[m.group(1)]   # "<act>.start" = where the act begins (module.py clamps cross-act rides to it)
    return a["start"] + (0 if m.group(2) == "start" else a["C"][m.group(2)]) + float(m.group(3) or 0)
def ride_expr(bus):
    terms = []
    for r in cfg.get("rides", []):
        if r.get("bus", "all") != bus: continue
        a, b = cue_time(r["from"]), cue_time(r["to"]); ri, ro = r.get("in", 0.3), r.get("out", 0.6)
        G = 10 ** (r["db"] / 20)
        terms.append(f"if(lt(t,{a - ri:.3f}),1,if(lt(t,{a:.3f}),1+({G - 1:.5f})*(t-{a - ri:.3f})/{ri},"
                     f"if(lt(t,{b:.3f}),{G:.5f},if(lt(t,{b + ro:.3f}),{G:.5f}+({1 - G:.5f})*(t-{b:.3f})/{ro},1))))")
    return "*".join(terms)

bed_gain = (f"if(lt(t,{first - 0.1}),2.8,"
            f"if(lt(t,{first + 0.7}),2.8-1.8*(t-{first - 0.1})/0.8,"
            f"if(lt(t,{last_end + 0.2}),1.0,"
            f"if(lt(t,{last_end + 1.2}),1.0+1.2*(t-{last_end + 0.2}),2.2))))")
g = []
# voice_offset < 0 happens in single-act previews (module.py): the act starts mid-voice, so cut the head off instead of
# delaying — ffmpeg's adelay rejects negative values
place = f"atrim=start={-vo_off:.3f},asetpts=PTS-STARTPTS" if vo_off < 0 else f"adelay={int(vo_off * 1000)}|{int(vo_off * 1000)}"
g.append(f"[0:a]{place},aformat=channel_layouts=stereo,apad=whole_dur={total}[vo]")
g.append("[vo]asplit=3[vo1][vosc][vosc2]")
mus_ride = ride_expr("music")
g.append(f"[1:a]volume=-9dB,volume='{bed_gain}':eval=frame" + (f",volume='{mus_ride}':eval=frame" if mus_ride else "") + f",atrim=0:{total}[bed]")
g.append("[bed][vosc]sidechaincompress=threshold=0.03:ratio=5:attack=40:release=450:makeup=1[bedd]")
labels = []
for idx, t, v in fx:
    # soften every effect: roll off the hissy top end so transitions never cut through the voice
    g.append(f"[{idx}:a]aformat=channel_layouts=stereo:sample_rates=48000,lowpass=f=4200,volume={v},adelay={int(t * 1000)}|{int(t * 1000)}[f{idx}]")
    labels.append(f"[f{idx}]")
if labels:
    g.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,volume=0.8[sfxr]")
    g.append("[sfxr][vosc2]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=300:makeup=1[sfx]")
    g.append("[vo1][bedd][sfx]amix=inputs=3:normalize=0,atrim=0:" + str(total) + "[mx]")
else:
    g.append("[vosc2]anullsink")
    g.append("[vo1][bedd]amix=inputs=2:normalize=0,atrim=0:" + str(total) + "[mx]")
all_ride = ride_expr("all")
g.append(f"[mx]volume='{all_ride}':eval=frame[pre]" if all_ride else "[mx]anull[pre]")
pre = root / "assets/mix/pre.wav"; pre.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(g), "-map", "[pre]", "-ar", "48000", str(pre)], check=True)

def integrated(path):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1])
out = root / cfg["mix"]
gain = TARGET - integrated(pre)
for _ in range(3):   # the limiter shaves a little loudness off — nudge until we land on target
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(pre), "-af",
                    f"volume={gain:.2f}dB,alimiter=limit=0.84:attack=4:release=60:level=false", "-ar", "48000", str(out)], check=True)
    miss = TARGET - integrated(out)
    if abs(miss) < 0.15: break
    gain += miss
r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
I = re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1]; P = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)[-1]
print(f"mixed {len(fx)} sfx · {total:.2f}s → {out.relative_to(root)} · {I} LUFS · peak {P} dBFS")
