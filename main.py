import sys
import os


def print_cli_usage():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                        SUBGEN v2.0                               ║
║           AI-Powered Subtitle Generator                          ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  CLI USAGE:                                                      ║
║                                                                  ║
║    python main.py <path> [options]                               ║
║                                                                  ║
║  OPTIONS:                                                        ║
║                                                                  ║
║    --audio        Process only audio files (.mp3, .wav, etc.)    ║
║    --video        Process only video files (.mp4, .mkv, etc.)    ║
║                                                                  ║
║  EXAMPLES:                                                       ║
║                                                                  ║
║    python main.py ./my_video.mp4                                 ║
║    python main.py ./AMJ/tawheed_series                           ║
║    python main.py ./music --audio                                ║
║    python main.py ./movies --video                               ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  GUI MODE:                                                       ║
║                                                                  ║
║    Run without arguments to launch the GUI:                      ║
║                                                                  ║
║    python main.py                                                ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")


def parse_cli_args(args):
    """Parse CLI arguments with helpful error messages."""
    # Check for help flags (can be anywhere)
    if "-h" in args or "--help" in args or "help" in args:
        print_cli_usage()
        sys.exit(0)

    # Check for conflicting flags
    if "--audio" in args and "--video" in args:
        print("❌ Error: Cannot use both --audio and --video at the same time.")
        print("   Choose one to filter by file type, or use neither to process all files.")
        sys.exit(1)

    path = None
    filter_mode = None
    unknown_args = []

    # First pass: identify all flags and collect non-flag arguments
    non_flag_args = []
    for arg in args:
        if arg == "--audio":
            filter_mode = "audio"
        elif arg == "--video":
            filter_mode = "video"
        elif arg.startswith("-"):
            unknown_args.append(arg)
        else:
            non_flag_args.append(arg)

    # Handle the path (first non-flag argument)
    if len(non_flag_args) == 1:
        path = non_flag_args[0]
    elif len(non_flag_args) > 1:
        path = non_flag_args[0]
        unknown_args.extend(non_flag_args[1:])

    # Handle unknown arguments with helpful messages
    if unknown_args:
        print(f"❌ Unknown argument(s): {', '.join(unknown_args)}")
        print()
        print("   Did you mean one of these?")
        for bad_arg in unknown_args:
            if "audio" in bad_arg.lower():
                print(f"   • {bad_arg} → try: --audio")
            elif "video" in bad_arg.lower():
                print(f"   • {bad_arg} → try: --video")
            elif "help" in bad_arg.lower():
                print(f"   • {bad_arg} → try: --help")
            else:
                print(f"   • {bad_arg} → not recognized, see usage below")
        print()
        print_cli_usage()
        sys.exit(1)

    # Validate path was provided for CLI mode
    if path is None:
        print("❌ Error: No path provided.")
        print()
        print("   You need to specify a file or folder to process.")
        print()
        print_cli_usage()
        sys.exit(1)

    # Expand user paths like ~/Documents
    path = os.path.expanduser(path)

    if not os.path.exists(path):
        print(f"❌ Error: Path does not exist: '{path}'")
        print()
        print("   Please check:")
        print(f"   • Does the path exist?")
        print(f"   • Did you type it correctly?")
        print(f"   • Are you in the right directory?")
        print(f"   • Current directory: {os.getcwd()}")
        print()
        print("   Tip: Use tab completion to avoid typos!")
        sys.exit(1)

    return path, filter_mode


def run_gui_mode():
    """Launch the GUI application."""
    try:
        from gui import run_gui
        run_gui()
    except ImportError as e:
        print("❌ GUI dependency missing")
        print()
        print(f"   Details: {e}")
        print()
        print("   To use the GUI, install the required dependencies:")
        print("   uv pip install customtkinter tkinterdnd2")
        print()
        print("   Or use CLI mode instead:")
        print("   python main.py <path> [--audio|--video]")
        sys.exit(1)


def run_cli_mode(path, filter_mode):
    """Run the CLI application."""
    from cli import main as cli_main
    cli_main(path, filter_mode)


def main():
    # Skip the script name, get actual arguments
    args = sys.argv[1:]

    # If no arguments provided, launch GUI mode
    if not args:
        run_gui_mode()
        return

    # Check for help flags first
    if args[0] in ("-h", "--help"):
        print_cli_usage()
        sys.exit(0)

    # We have arguments - run CLI mode (parse_cli_args will handle validation)
    path, filter_mode = parse_cli_args(args)
    run_cli_mode(path, filter_mode)


if __name__ == "__main__":
    main()
