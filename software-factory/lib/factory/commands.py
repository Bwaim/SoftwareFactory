from . import cli


def register(sub, common):
    p = sub.add_parser("version")
    vs = p.add_subparsers(dest="action", required=True)
    vs.add_parser("check", parents=[common])


@cli.command("version check")
def version_check(args):
    from . import repo, version
    cli.emit(version.report(repo.load_ctx(task_opt=args.task)), args.json)
