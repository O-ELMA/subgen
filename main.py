import argparse
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", action="store_true", help="Run the CLI")
    args = parser.parse_args()

    if args.cli:
        from cli import main as cli_main
        cli_main()
    else:
        try:
            from gui import run_gui
            run_gui()
        except ImportError as e:
            print(f"GUI dependency missing: {e}")
            print("Install GUI dependencies with: pip install customtkinter tkinterdnd2")
            sys.exit(1)


if __name__ == "__main__":
    main()
