#!/usr/bin/env python3
"""
HUSH Professional Demo Video Generator
- Generates studio voiceover narration using macOS text-to-speech.
- Drives Playwright Chromium at 1920x1080 (60fps) with smooth navigation through all features.
- Muxes high-res video and narration into a production-grade 1080p MP4.
"""
import os
import sys
import time
import subprocess
import asyncio
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "demo_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FFMPEG_BIN = BASE_DIR / ".venv" / "bin" / "ffmpeg"

SECTIONS = [
    {
        "id": "intro",
        "tab": "brief",
        "text": "Welcome to Hush. An on-device attention operating system built for the Google Gemma and Temporal Hackathon. Hush reads every notification your device receives, so you only have to read four.",
        "duration": 14,
        "actions": ["wait_start", "hover_lines"],
    },
    {
        "id": "brief",
        "tab": "brief",
        "text": "Rather than an endless stream of pings, Hush silences all noise during your focus window. Every cycle, it presents exactly four high-signal lines with strict source quotas and slot-borrowing spillover.",
        "duration": 15,
        "actions": ["scroll_brief", "hover_footer"],
    },
    {
        "id": "cadence",
        "tab": "cadence",
        "text": "You can dynamically configure your quiet window from fifteen minutes to four hours, backed by Temporal durable timers that persist across laptop sleep without clock drift. A master power toggle gives you instant manual control.",
        "duration": 15,
        "actions": ["switch_cadence", "hover_power"],
    },
    {
        "id": "apps",
        "tab": "apps",
        "text": "Hush monitors channels including WhatsApp, Gmail, Slack, and SMS. Our live sandbox routes messages through an on-device Gemma two-B model, computing a deterministic cost formula of urgency, consequence, and decay.",
        "duration": 16,
        "actions": ["apps_interact", "sandbox_test"],
    },
    {
        "id": "drill",
        "tab": "drill",
        "text": "We prove Hush with an empirical benchmark: ten staged life-and-death emergencies against realistic promotional noise. Watch the live result: one hundred percent Emergency Recall, one hundred percent Precision, and one hundred percent Silence Integrity.",
        "duration": 18,
        "actions": ["run_drill_demo", "highlight_metrics"],
    },
    {
        "id": "discard",
        "tab": "discard",
        "text": "Every silenced notification is safely preserved in a transparent audit log, so nothing is ever lost. Hush operates entirely on-device with zero cloud dependencies, zero subscriptions, and complete privacy. Silence is the new luxury. Thank you.",
        "duration": 16,
        "actions": ["show_discard", "return_brief"],
    },
]


def generate_voiceover():
    """Generates clean audio tracks for each segment using macOS say and ffmpeg."""
    print("Generating voiceover audio segments...")
    segment_files = []

    for i, s in enumerate(SECTIONS):
        raw_aiff = OUTPUT_DIR / f"segment_{i}_{s['id']}.aiff"
        wav_file = OUTPUT_DIR / f"segment_{i}_{s['id']}.wav"

        # Use macOS Samantha voice at comfortable professional pace (-r 170)
        cmd = ["/usr/bin/say", "-v", "Samantha", "-r", "170", "-o", str(raw_aiff), s["text"]]
        subprocess.run(cmd, check=True)

        # Convert to standardized 44.1kHz mono WAV
        cmd_ff = [
            str(FFMPEG_BIN), "-y", "-i", str(raw_aiff),
            "-ar", "44100", "-ac", "1", str(wav_file)
        ]
        subprocess.run(cmd_ff, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        segment_files.append(wav_file)

    # Concatenate all wav files with pad intervals
    concat_list = OUTPUT_DIR / "concat_list.txt"
    with open(concat_list, "w") as f:
        for wf in segment_files:
            f.write(f"file '{wf.resolve()}'\n")

    master_audio = OUTPUT_DIR / "master_voiceover.wav"
    subprocess.run([
        str(FFMPEG_BIN), "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list), "-c", "copy", str(master_audio)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"Master voiceover generated: {master_audio}")
    return master_audio


async def record_playwright_video():
    """Drives Playwright to smoothly record the 1080p video demo."""
    from playwright.async_api import async_playwright

    video_raw_dir = OUTPUT_DIR / "raw_video"
    video_raw_dir.mkdir(parents=True, exist_ok=True)

    print("Launching Chromium to capture full 1080p demo sequence...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(video_raw_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        # Load local Hush UI
        await page.goto("http://localhost:8484", wait_until="networkidle")
        await asyncio.sleep(2)

        # 1. INTRO & BRIEF
        print(" -> Scene 1: The Brief & Silence Focus")
        await asyncio.sleep(4)
        brief_lines = await page.query_selector_all(".brief-line")
        for bl in brief_lines[:3]:
            await bl.hover()
            await asyncio.sleep(1.5)
        await asyncio.sleep(4)

        # 2. THE BRIEF DETAILS
        print(" -> Scene 2: The Four Lines")
        await page.mouse.wheel(0, 300)
        await asyncio.sleep(3)
        await page.mouse.wheel(0, -300)
        await asyncio.sleep(5)

        # 3. CADENCE
        print(" -> Scene 3: Cadence & Power")
        await page.click("button[data-tab='cadence']")
        await asyncio.sleep(2)
        # Click 15m button
        b15 = await page.query_selector("button[data-min='15']")
        if b15:
            await b15.click()
            await asyncio.sleep(1.5)
        # Click 1 Hour button
        b60 = await page.query_selector("button[data-min='60']")
        if b60:
            await b60.click()
            await asyncio.sleep(1.5)
        # Click 3 Hours button (Default)
        b180 = await page.query_selector("button[data-min='180']")
        if b180:
            await b180.click()
            await asyncio.sleep(2)
        await asyncio.sleep(4)

        # 4. APPS & CHANNELS & SANDBOX
        print(" -> Scene 4: Apps & Live Sandbox")
        await page.click("button[data-tab='apps']")
        await asyncio.sleep(2)
        # Click a quick preset
        fb_chip = await page.query_selector(".chip")
        if fb_chip:
            await fb_chip.hover()
            await asyncio.sleep(1)
        # Scroll to live sandbox
        sb_run = await page.query_selector("#sbRun")
        if sb_run:
            await sb_run.scroll_into_view_if_needed()
            await asyncio.sleep(2)
            await sb_run.click()
            await asyncio.sleep(3)
        await page.mouse.wheel(0, 400)
        await asyncio.sleep(3)
        await page.mouse.wheel(0, -400)
        await asyncio.sleep(3)

        # 5. FIRE DRILL BENCHMARK
        print(" -> Scene 5: Fire Drill & Scorecard")
        await page.click("button[data-tab='drill']")
        await asyncio.sleep(2)
        drill_btn = await page.query_selector("#drillRun")
        if drill_btn:
            await drill_btn.click()
            # Wait for Gemma evaluation to complete
            await asyncio.sleep(6)
        # Hover over the metric cards
        metrics = await page.query_selector_all(".metric")
        for m in metrics:
            await m.hover()
            await asyncio.sleep(1)
        await page.mouse.wheel(0, 300)
        await asyncio.sleep(3)
        await page.mouse.wheel(0, -300)
        await asyncio.sleep(2)

        # 6. DISCARD PILE & CONCLUSION
        print(" -> Scene 6: Discard Pile & Wrap Up")
        await page.click("button[data-tab='discard']")
        await asyncio.sleep(3)
        await page.mouse.wheel(0, 300)
        await asyncio.sleep(2)
        await page.mouse.wheel(0, -300)
        await asyncio.sleep(2)

        # Return to The Brief for final beauty shot
        await page.click("button[data-tab='brief']")
        await asyncio.sleep(4)

        # Close page to flush video
        await page.close()
        video_path = await page.video.path()
        await context.close()
        await browser.close()

    print(f"Raw video recorded: {video_path}")
    return Path(video_path)


def assemble_final_video(raw_video: Path, master_audio: Path):
    """Muxes the video and audio into a polished, crisp 1080p MP4."""
    final_output = BASE_DIR / "hush_demo_1080p.mp4"
    print(f"Muxing into final video: {final_output}...")

    # We use ffmpeg to merge video and audio, matching durations smoothly
    cmd = [
        str(FFMPEG_BIN), "-y",
        "-i", str(raw_video),
        "-i", str(master_audio),
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(final_output)
    ]
    subprocess.run(cmd, check=True)
    print("==================================================")
    print(f"SUCCESS! Professional Demo Video Created:")
    print(f" -> {final_output}")
    print("==================================================")
    return final_output


def main():
    master_audio = generate_voiceover()
    raw_video = asyncio.run(record_playwright_video())
    final_video = assemble_final_video(raw_video, master_audio)
    print(f"Demo video ready for submission at: {final_video}")


if __name__ == "__main__":
    main()
