import os
import sys
import argparse

from config import (
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    OUTPUT_DIR,
)
from ai_engine import transcribe


def _collect_files(path, filter_mode):
    path = os.path.abspath(path)

    if os.path.isfile(path):
        ext = os.path.splitext(path)[1].lower()
        if ext in AUDIO_EXTENSIONS or ext in VIDEO_EXTENSIONS:
            return [path]
        print(f"❌ Error: unsupported file format '{ext}'")
        sys.exit(1)

    if os.path.isdir(path):
        extensions = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
        if filter_mode == "audio":
            extensions = AUDIO_EXTENSIONS
        elif filter_mode == "video":
            extensions = VIDEO_EXTENSIONS

        files = sorted(
            os.path.join(path, f)
            for f in os.listdir(path)
            if os.path.splitext(f)[1].lower() in extensions
        )
        if not files:
            label = filter_mode or "audio/video"
            print(f"❌ No {label} files found in '{path}'")
            sys.exit(1)
        return files

    print(f"❌ Error: path does not exist '{path}'")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="SUBGEN",
        description="📄 Generate subtitles from audio/video files using AI-powered ASR.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="📂 Path to an audio/video file or directory",
    )
    parser.add_argument(
        "--audio",
        "-audio",
        dest="filter",
        action="store_const",
        const="audio",
        help="⏩ Process only audio files in the directory",
    )
    parser.add_argument(
        "--video",
        "-video",
        dest="filter",
        action="store_const",
        const="video",
        help="🎦 Process only video files in the directory",
    )

    args = parser.parse_args()

    if args.path is None:
        parser.print_help()
        sys.exit(0)

    files = _collect_files(args.path, args.filter)

    total_files = len(files)
    for idx, filepath in enumerate(files, 1):
        print(f"📁 [{idx}/{total_files}] Processing: {filepath}")
        elapsed, _ = transcribe(filepath)
        print(f"✅ Done in {elapsed:.1f} min — {os.path.join(OUTPUT_DIR, os.path.splitext(os.path.basename(filepath))[0] + '.srt')}")


if __name__ == "__main__":
    main()
