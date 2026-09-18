from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .common import load_env, parse_date
from .config import load_config, call_limits, plan
from .http import Transport
from .pipeline import run_pipeline
from .providers import missing_keys, required_keys


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hiring listing → Meta activity → possible owner → research brief")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["plan", "run", "doctor"]:
        p = commands.add_parser(name)
        p.add_argument("--config", type=Path, default=Path("mvp.toml"))
        if name == "run":
            p.add_argument("--execute", action="store_true", help="Make billable API calls using the reviewed config; see docs/PROVIDERS.md")
            p.add_argument("--output", type=Path)
    demo = commands.add_parser("demo", help="Offline synthetic fixtures through the same workflow; no keys required")
    demo.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            from .demo import DemoTransport, load_fixture
            fixture = load_fixture()
            config = fixture["config"]
        else:
            config = load_config(args.config)
        if args.command == "plan" or args.command == "run" and not args.execute:
            print(json.dumps(plan(config), indent=2))
            print("No network calls made. Review scope and costs before run --execute.")
            return 0
        if args.command in {"run", "doctor"}:
            load_env(args.config.resolve().parent / ".env")
            missing = missing_keys(config)
            if args.command == "doctor":
                for name in required_keys(config):
                    print(f"{name}: {'missing' if name in missing else 'present'}")
                print("Presence check only; credentials and live integrations have not been tested.")
                return 1 if missing else 0
            if missing:
                parser.error("Missing configuration: " + ", ".join(missing) + ". Run doctor after creating .env.")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = args.output or Path("runs") / (args.command + "-" + stamp)
        if output.exists():
            parser.error("Output path already exists; choose a new directory. Runs cannot be overwritten or blindly resumed.")
        output.mkdir(parents=True)
        is_demo = args.command == "demo"
        transport = DemoTransport(output, call_limits(config), fixture) if is_demo else Transport(output, call_limits(config))
        result = run_pipeline(config, transport, output, demo=is_demo, clock=parse_date(fixture["clock"]) if is_demo else None, progress=print)
        print(f"{result['manifest']['state'].upper()}: {output / 'report.md'}")
        if result["manifest"]["state"] != "complete":
            return 2
        if not result["manifest"]["outcome"]["priority_review_accounts"]:
            print("NO QUALIFYING BRIEFS: execution finished, but the end-to-end proof did not pass.")
            return 3
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(f"Could not read configuration/output ({type(exc).__name__}). Check paths and TOML values.")


if __name__ == "__main__":
    raise SystemExit(main())
