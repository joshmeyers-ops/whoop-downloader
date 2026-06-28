"""Run both exporters in sequence into a single output folder."""

import argparse
import sys

from whoop_dl import export as whoop_export
from wyze_dl import export as wyze_export


def _banner(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="downloader",
        description="Run the WHOOP and Wyze exporters into one output folder.",
    )
    parser.add_argument("--out", default="out", help="output directory (default: ./out)")
    parser.add_argument("--start", help="start date YYYY-MM-DD (applies to both)")
    parser.add_argument("--end", help="end date YYYY-MM-DD (applies to both)")
    parser.add_argument(
        "--limit", type=int, default=25, help="WHOOP API page size, max 25"
    )
    parser.add_argument("--skip-whoop", action="store_true", help="don't run whoop_dl")
    parser.add_argument("--skip-wyze", action="store_true", help="don't run wyze_dl")
    args = parser.parse_args(argv)

    results = {}  # source -> "ok" | error string | None(skipped)

    # Wyze first (no interactive auth), then WHOOP.
    if args.skip_wyze:
        results["wyze"] = None
    else:
        _banner("WYZE SCALE")
        try:
            wyze_export.export_all(
                out_dir=args.out, start=args.start, end=args.end, verbose=True
            )
            results["wyze"] = "ok"
        except Exception as exc:  # noqa: BLE001
            results["wyze"] = str(exc)
            print(f"[ERROR] Wyze export failed: {exc}", file=sys.stderr)

    if args.skip_whoop:
        results["whoop"] = None
    else:
        _banner("WHOOP")
        try:
            whoop_export.export_all(
                out_dir=args.out,
                start=args.start,
                end=args.end,
                limit=args.limit,
                verbose=True,
            )
            results["whoop"] = "ok"
        except Exception as exc:  # noqa: BLE001
            results["whoop"] = str(exc)
            print(f"[ERROR] WHOOP export failed: {exc}", file=sys.stderr)

    _banner("SUMMARY")
    any_failed = False
    for src in ("wyze", "whoop"):
        status = results.get(src)
        if status == "ok":
            print(f"  {src:6s}: OK")
        elif status is None:
            print(f"  {src:6s}: skipped")
        else:
            any_failed = True
            print(f"  {src:6s}: FAILED - {status}")
    print(f"\nOutput folder: {args.out}")

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
