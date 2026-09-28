"""Command-line entrypoint for wyze-dl."""

import argparse
import sys

from . import client, export


def _cmd_list(args):
    try:
        scales = client.list_scales(verbose=True)
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


def _cmd_login(args):
    """Fresh login + cache the token (do this once after a 429 clears)."""
    try:
        client.login(verbose=True, force=args.force)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    print("[OK] Logged in. Token cached; future runs will reuse it (no re-login).")
    return 0


def _cmd_logout(args):
    """Delete the cached token (next run logs in fresh)."""
    print("Cached token removed." if client.clear_token() else "No cached token.")
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
    p_login = sub.add_parser("login", help="fresh login and cache the token")
    p_login.add_argument(
        "--force", action="store_true",
        help="override the local 429 cooldown guard",
    )
    p_login.set_defaults(func=_cmd_login)
    sub.add_parser("logout", help="delete the cached token").set_defaults(
        func=_cmd_logout
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
