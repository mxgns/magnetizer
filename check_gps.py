#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from magnetizer.gps import count_gps_images


def main():
    parser = argparse.ArgumentParser(
        prog="check_gps.py",
        description=(
            "Scan every raster image under DIRECTORY for GPS EXIF data and report "
            "counts only — never filenames or coordinate values. Intended to run "
            "against a real build output (default: dist), since the Pages repo is "
            "public and the unit tests only prove the code path against fixtures."
        ),
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default="dist",
        metavar="DIRECTORY",
        help="Directory to scan (default: dist).",
    )
    args = parser.parse_args()

    total, with_gps = count_gps_images(Path.cwd() / args.directory)
    print(f"Scanned {total} image{'s' if total != 1 else ''}.")
    print(f"{with_gps} carry GPS EXIF data.")
    sys.exit(1 if with_gps else 0)


if __name__ == "__main__":
    main()
