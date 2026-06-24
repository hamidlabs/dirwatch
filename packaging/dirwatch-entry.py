"""PyInstaller entry point for the AppImage build."""
import sys

from dirwatch.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
