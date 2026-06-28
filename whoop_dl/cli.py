"""Command-line entrypoint for whoop-dl."""

import argparse
import json
import sys

from . import auth, client, export


def _cmd_auth_login(args):
    auth.login(manual=args.manual)
    # De-risk gate: prove the token works by fetching a single cycle.
    print("\nVerifying API access (GET /v2/cycle?limit=1)...")
    try:
        records = client.get_collection("/v2/cycle", limit=1)
    except Exception as exc:  # noqa: BLE001 — surface any API failure clearly
        print(f"[WARN] Token stored but verification call failed: {exc}")
        return 1
    if records:
        print("[OK] API access confirmed. Sample cycle:")
        print(json.dumps(records[0], indent=2)[:2000])
    else:
        print("[OK] API reachable, but no cycles returned (new account?).")
    return 0


def _cmd_auth_status(args):
    info = auth.status()
    print(json.dumps(info, indent=2))
    return 0 if info.get("authenticated") else 1


def _cmd_export(args):
    try:
        export.export_all(
            out_dir=args.out,
            start=args.start,
            end=args.end,
            limit=args.limit,
            verbose=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Export failed: {exc}", file=sys.stderr)
        return 1
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="whoop-dl",
        description="Download WHOOP history to CSVs matching the official export.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # auth
    p_auth = sub.add_parser("auth", help="authentication commands")
    auth_sub = p_auth.add_subparsers(dest="auth_cmd", required=True)
    p_login = auth_sub.add_parser("login", help="one-time OAuth, stores token")
    p_login.add_argument(
        "--manual",
        action="store_true",
        help="skip the local callback server; paste the code by hand",
    )
    p_login.set_defaults(func=_cmd_auth_login)
    auth_sub.add_parser("status", help="show token validity").set_defaults(
        func=_cmd_auth_status
    )

    # export
    p_export = sub.add_parser("export", help="full history -> 3 CSVs")
    p_export.add_argument("--start", help="start date YYYY-MM-DD (default: all history)")
    p_export.add_argument("--end", help="end date YYYY-MM-DD (default: now)")
    p_export.add_argument("--out", default="out", help="output directory (default: ./out)")
    p_export.add_argument(
        "--limit", type=int, default=25, help="records per API page, max 25"
    )
    p_export.set_defaults(func=_cmd_export)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
