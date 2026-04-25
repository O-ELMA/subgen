import os
import sys
import time

from config import (
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    OUTPUT_DIR,
)
from ai_engine import transcribe
from utils import ensure_api_key


def _get_api_key_from_user():
    """Prompt user for API key in CLI and return it."""
    print("⚠️  NANO_GPT_KEY not found in .env")
    while True:
        key = input("Please enter your Nano-GPT API key: ").strip()
        if key:
            return key
        print("API key cannot be empty. Please try again.")


def _collect_files(path, filter_mode):
    path = os.path.abspath(path)

    if os.path.isfile(path):
        ext = os.path.splitext(path)[1].lower()
        if ext in AUDIO_EXTENSIONS or ext in VIDEO_EXTENSIONS:
            return [path]
        supported = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
        print(f"❌ Error: Unsupported file format '{ext}'")
        print()
        print("   Supported formats:")
        print(f"   • Audio: {', '.join(sorted(AUDIO_EXTENSIONS))}")
        print(f"   • Video: {', '.join(sorted(VIDEO_EXTENSIONS))}")
        print()
        print(f"   Your file: {os.path.basename(path)}")
        sys.exit(1)

    if os.path.isdir(path):
        extensions = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
        label = "audio/video"
        if filter_mode == "audio":
            extensions = AUDIO_EXTENSIONS
            label = "audio"
        elif filter_mode == "video":
            extensions = VIDEO_EXTENSIONS
            label = "video"

        files = sorted(
            os.path.join(path, f)
            for f in os.listdir(path)
            if os.path.splitext(f)[1].lower() in extensions
        )

        if not files:
            print(f"❌ No {label} files found in '{path}'")
            print()
            print("   Folder contents:")
            try:
                items = sorted(os.listdir(path))[:10]  # Show first 10 items
                for item in items:
                    item_path = os.path.join(path, item)
                    item_type = "📁" if os.path.isdir(item_path) else "📄"
                    print(f"   {item_type} {item}")
                if len(os.listdir(path)) > 10:
                    print(f"   ... and {len(os.listdir(path)) - 10} more items")
            except Exception:
                print("   (Could not list folder contents)")
            print()
            print("   Supported formats:")
            print(f"   • Audio: {', '.join(sorted(AUDIO_EXTENSIONS))}")
            print(f"   • Video: {', '.join(sorted(VIDEO_EXTENSIONS))}")
            print()
            if filter_mode:
                print(f"   Tip: Remove --{filter_mode} to search for all file types")
            sys.exit(1)

        return files

    print(f"❌ Error: Cannot access path '{path}'")
    sys.exit(1)


def main(path=None, filter_mode=None):
    if path is None:
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║  This is the CLI module. Run via: python main.py <path>          ║")
        print("╚══════════════════════════════════════════════════════════════════╝")
        sys.exit(1)

    # Check for API key and prompt if missing
    ensure_api_key(_get_api_key_from_user)
    print("✅ API key saved to .env")
    print()

    files = _collect_files(path, filter_mode)

    print(f"🎯 Found {len(files)} file(s) to process")
    print(f"📂 Output directory: {OUTPUT_DIR}")
    print()

    total_files = len(files)
    start_time = time.time()

    for idx, filepath in enumerate(files, 1):
        print(f"┌─────────────────────────────────────────────────────────────────┐")
        print(f"│ [{idx}/{total_files}] {os.path.basename(filepath)[:52]:<52} │")
        print(f"└─────────────────────────────────────────────────────────────────┘")

        try:
            elapsed, merged = transcribe(filepath)
        except KeyboardInterrupt:
            print("\n\n🛑 Interrupted by user. Cleaning up...")
            break

        basename = os.path.splitext(os.path.basename(filepath))[0]
        srt_path = os.path.join(os.path.dirname(filepath), f"{basename}.srt")

        print(f"   ✅ Done in {elapsed:.1f} min")
        print(f"   📄 {srt_path}")
        print()

    total_elapsed = (time.time() - start_time) / 60
    if idx < total_files:
        print(f"⏹️  Stopped. Processed {idx - 1} of {total_files} file(s) in {total_elapsed:.1f} minutes")
    else:
        print(f"🎉 All done! Processed {total_files} file(s) in {total_elapsed:.1f} minutes total")
    print(f"   Output saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  This is the CLI module. Run via: python main.py <path>          ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    sys.exit(1)
