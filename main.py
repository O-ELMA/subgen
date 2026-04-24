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
    if "-h" in args or "--help" in args or "help" in args:
        print_cli_usage()
        sys.exit(0)

    if "--audio" in args and "--video" in args:
        print("❌ Error: Cannot use both --audio and --video at the same time.")
        print("   Choose one to filter by file type, or use neither to process all files.")
        sys.exit(1)

    path = None
    filter_mode = None
    unknown_args = []

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

    if len(non_flag_args) == 1:
        path = non_flag_args[0]
    elif len(non_flag_args) > 1:
        path = non_flag_args[0]
        unknown_args.extend(non_flag_args[1:])

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

    if path is None:
        print("❌ Error: No path provided.")
        print()
        print("   You need to specify a file or folder to process.")
        print()
        print_cli_usage()
        sys.exit(1)

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
    from cli import main as cli_main
    cli_main(path, filter_mode)


def main():
    args = sys.argv[1:]

    if not args:
        run_gui_mode()
        return

    if args[0] in ("-h", "--help"):
        print_cli_usage()
        sys.exit(0)

    path, filter_mode = parse_cli_args(args)
    run_cli_mode(path, filter_mode)


if __name__ == "__main__":
    main()
