"""Command-line entrypoint for wyze-dl."""

import argparse
import sys

from . import client, export


def _cmd_list(args):
    try:
        wyze = client.make_client()
        scales = client.list_scales(wyze)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    if not scales:
        print("No scales found on this account.")
        return 0
    print(f"Found {len(scales)} scale(s):")
    for s in scales:
        model = getattr(getattr(s, "product", None), "model", "?")
        print(
            f"  - {getattr(s, 'nickname', '?')}  "
            f"mac={getattr(s, 'mac', '?')}  model={model}  "
            f"unit={getattr(s, 'unit', '?')}  online={getattr(s, 'is_online', '?')}"
        )
    return 0


def _cmd_export(args):
    try:
        export.export_all(out_dir=args.out, start=args.start, end=args.end, verbose=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Export failed: {exc}", file=sys.stderr)
        return 1
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="wyze-dl",
        description="Download Wyze Scale body-composition history to a CSV.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list scales on the account (auth check)").set_defaults(
        func=_cmd_list
    )

    p_export = sub.add_parser("export", help="scale history -> body_composition.csv")
    p_export.add_argument("--start", help="start date YYYY-MM-DD (default: all history)")
    p_export.add_argument("--end", help="end date YYYY-MM-DD (default: today)")
    p_export.add_argument("--out", default="out", help="output directory (default: ./out)")
    p_export.set_defaults(func=_cmd_export)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
