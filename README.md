# TT_story_agent (v2)

Autonomous short-form video pipeline. It writes a script, voices it, times captions, renders a 9:16 video,
runs quality gates and drops a ready-to-post folder into `output/`. **Uploading is manual by design.**

```
premise -> drafts -> editor pass -> hook pick -> AI-sounding filter
   -> Kokoro voice -> Whisper word timing -> ASS captions -> FFmpeg render -> gates -> output/<date>/<video>/
```

Two channel profiles ship in `config/channels/`: `horror` (original creepy stories) and `facts` (explainers).
Add a niche by adding a YAML file. Everything runs locally (Ollama + Kokoro + faster-whisper + FFmpeg); no API keys.

## Setup (Mac mini, Apple Silicon)

```bash
brew install ffmpeg ollama uv
ollama pull qwen2.5:14b-instruct        # use a 7-8B model if RAM <= 16GB; edit config/settings.yaml
uv venv && source .venv/bin/activate
uv pip install -e ".[voice,align,dev]"
mkdir models   # download kokoro-v1.0.onnx + voices-v1.0.bin from the kokoro-onnx releases into ./models
# put clips you have rights to into assets/footage/horror/ and assets/footage/facts/
ttagent doctor
ttagent run --channel horror facts --count 2
```

Set `video.encoder: h264_videotoolbox` in `config/settings.yaml` for hardware-accelerated encodes on macOS.

## Scheduling

Use `launchd` (or cron) to run `ttagent run --count 3` daily. Each video lands in
`output/<date>/<channel>-<slug>/` with `video.mp4`, `script.txt`, `captions.ass`, `metadata.json`
and `POST_CHECKLIST.md`. Videos that fail a gate are still saved but marked `FAILED GATES`.

## Quality gates

duration, 1080x1920, audio present, loudness (-16 LUFS +/-2.5), word count, stock-phrase ban list,
and an "AI-sounding" heuristic score (`src/ttagent/script/filters.py`). The score is a cheap first filter,
not a quality guarantee: watch each video before posting and turn on TikTok's AI-content label.

## Security and compliance notes

- No secrets in the repo; `.env`, cookies and keys are git-ignored. Use Keychain/a secrets manager for any real key.
- Footage, music and cloned voices must be licensed or yours. Check each model's licence before monetising.
- Do not automate TikTok login/cookies; the official API's rules do not allow auto-posting for your own accounts.

## Tests

`pytest` runs unit tests plus an end-to-end render (stub LLM/TTS, real FFmpeg).
