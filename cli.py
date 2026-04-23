import os
import sys
import time

from config import (
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    OUTPUT_DIR,
)
from ai_engine import transcribe


def _collect_files(path, filter_mode):
    """Collect audio/video files from a path."""
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

    # This shouldn't happen due to earlier validation, but just in case
    print(f"❌ Error: Cannot access path '{path}'")
    sys.exit(1)


def main(path=None, filter_mode=None):
    """
    Main CLI entry point.

    Args:
        path: Path to file or directory (from main.py arg parser)
        filter_mode: 'audio', 'video', or None
    """
    # If called directly without args (e.g., python cli.py), show usage
    if path is None:
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║  This is the CLI module. Run via: python main.py <path>          ║")
        print("╚══════════════════════════════════════════════════════════════════╝")
        sys.exit(1)

    # Collect files to process
    files = _collect_files(path, filter_mode)

    print(f"🎯 Found {len(files)} file(s) to process")
    print(f"📂 Output directory: {OUTPUT_DIR}")
    print()

    # Process each file
    total_files = len(files)
    start_time = time.time()

    for idx, filepath in enumerate(files, 1):
        print(f"┌─────────────────────────────────────────────────────────────────┐")
        print(f"│ [{idx}/{total_files}] {os.path.basename(filepath)[:52]:<52} │")
        print(f"└─────────────────────────────────────────────────────────────────┘")

        elapsed, merged = transcribe(filepath)

        # Construct output path
        basename = os.path.splitext(os.path.basename(filepath))[0]
        srt_path = os.path.join(os.path.dirname(filepath), f"{basename}.srt")

        print(f"   ✅ Done in {elapsed:.1f} min")
        print(f"   📄 {srt_path}")
        print()

    total_elapsed = (time.time() - start_time) / 60
    print(f"🎉 All done! Processed {total_files} file(s) in {total_elapsed:.1f} minutes total")
    print(f"   Output saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    # Direct execution without arguments - show helpful message
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  This is the CLI module. Run via: python main.py <path>          ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    sys.exit(1)
