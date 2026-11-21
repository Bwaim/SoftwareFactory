import argparse
import json
import sys

from .errors import FactoryError

VERSION = "0.2.1"
NO_VERSION_CHECK = {"init", "version", "migrate", "link", "terminal check", "menu", "hook", "serve", "dashboard", "server stop", "server waiting", "app install"}
COMMANDS = {}


def command(name):
    def register(fn):
        COMMANDS[name] = fn
        return fn
    return register


def emit(data, as_json):
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--task", default=None)
    common.add_argument("--json", action="store_true")
    parser = argparse.ArgumentParser(prog="factory")
    parser.add_argument("--version", action="version", version=f"factory {VERSION}")
    sub = parser.add_subparsers(dest="cmd", required=True)
    return parser, sub, common


def command_name(args):
    action = getattr(args, "action", None)
    return f"{args.cmd} {action}" if action else args.cmd


def split_passthrough(argv):
    if "--" not in argv or "start-session" not in argv:
        return list(argv), []
    index = list(argv).index("--")
    return list(argv[:index]), list(argv[index + 1:])


def main(argv):
    argv, passthrough = split_passthrough(argv)
    parser, sub, common = build_parser()
    from . import commands
    commands.register(sub, common)
    args = parser.parse_args(argv)
    args.passthrough = passthrough
    name = command_name(args)
    try:
        if args.cmd not in NO_VERSION_CHECK and name not in NO_VERSION_CHECK:
            from . import repo, version
            ctx = repo.load_ctx(task_opt=args.task)
            version.require_repo(ctx)
        return COMMANDS[name](args) or 0
    except FactoryError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
