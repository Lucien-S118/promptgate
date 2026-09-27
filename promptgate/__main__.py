"""Small CLI: scan one prompt, prepare data, or evaluate a frozen dataset."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys

from .baselines import regex_screen
from .contracts import ContractError, validate_prompt
from .data import prepare
from .evaluate import evaluate
from .llm import screen


def _key(ask):
    key = os.environ.get("MY_PRIVATE_OPENROUTER_KEY") or os.environ.get("OPENROUTER_API_KEY") or ""
    if not key and ask:
        if not sys.stdin.isatty():
            raise ContractError("Hidden key entry needs an interactive terminal.")
        key = getpass.getpass("OpenRouter API key (hidden, not saved): ")
    if not key.strip():
        raise ContractError("No API key configured. In a terminal, add --ask-key for hidden entry.")
    return key


def main():
    parser = argparse.ArgumentParser(description="PromptGate: one prompt -> one screening decision")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="Screen one input; interactive input avoids shell history")
    scan.add_argument("--backend", choices=["llm", "regex"], default="llm")
    scan.add_argument("--ask-key", action="store_true")
    prep = sub.add_parser("prepare", help="Audit the original downloads and freeze cleaned local splits")
    prep.add_argument("--source", type=Path, required=True)
    prep.add_argument("--output", type=Path, default=Path("data/processed/v1"))
    ev = sub.add_parser("evaluate", help="Evaluate fixed JSONL rows without saving prompt text")
    ev.add_argument("--dataset", type=Path, required=True)
    ev.add_argument("--output", type=Path, required=True)
    ev.add_argument("--backend", choices=["llm", "regex"], required=True)
    ev.add_argument("--ask-key", action="store_true")
    ev.add_argument("--max-calls", type=int, default=100)
    args = parser.parse_args()
    try:
        if args.command == "scan":
            text = input("English prompt to screen: ") if sys.stdin.isatty() else sys.stdin.read()
            validate_prompt(text)
            result = screen(text, _key(args.ask_key)) if args.backend == "llm" else regex_screen(text)
            print(json.dumps(result.public_dict(), ensure_ascii=False, indent=2))
            return 0 if result.status == "ok" else 2
        if args.command == "prepare":
            report = prepare(args.source, args.output)
            print(json.dumps({"before": report["before"], "after": report["after"],
                              "output_sizes": report["output_sizes"]}, indent=2))
        else:
            key = _key(args.ask_key) if args.backend == "llm" else ""
            print(json.dumps(evaluate(args.dataset, args.output, args.backend, key, args.max_calls), indent=2))
        return 0
    except (ValueError, OSError, EOFError) as exc:
        # Contract errors are sanitized; unexpected exception traces are not printed with request bodies.
        print(f"PromptGate: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Stopped. No complete evaluation is claimed.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
