"""Deploy warehouse SQL files to the Synapse serverless SQL pool with sqlcmd."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DIR = ROOT / "warehouse"
DEFAULT_SERVER = "synw-megasale-dev-ondemand.sql.azuresynapse.net"
DEFAULT_DATABASE = "megasale_warehouse"


def find_sqlcmd(explicit_path: str | None = None) -> str | None:
    """Find sqlcmd on PATH or in the standard Windows WinGet package location."""
    if explicit_path:
        candidate = Path(explicit_path).expanduser()
        if candidate.is_file():
            return str(candidate)
        located = shutil.which(explicit_path)
        return located

    located = shutil.which("sqlcmd")
    if located:
        return located

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        matches = sorted(packages.glob("Microsoft.Sqlcmd_*/*/sqlcmd.exe"))
        if matches:
            return str(matches[-1])
        matches = sorted(packages.glob("Microsoft.Sqlcmd_*/sqlcmd.exe"))
        if matches:
            return str(matches[-1])
    return None


def sql_files() -> list[Path]:
    files = sorted(
        path for path in WAREHOUSE_DIR.glob("*.sql")
        if path.name[:2].isdigit() and path.name[2:3] == "_"
    )
    if not files or files[0].name != "00_create_database.sql":
        raise RuntimeError("Expected warehouse/00_create_database.sql as the first deployment file.")
    return files


def build_command(sqlcmd: str, server: str, database: str, sql_file: Path) -> list[str]:
    target_database = "master" if sql_file.name == "00_create_database.sql" else database
    return [
        sqlcmd,
        "-S", server,
        "-d", target_database,
        "--authentication-method", "ActiveDirectoryAzCli",
        "-b",
        "-i", str(sql_file),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run numbered warehouse SQL files in order against Synapse serverless SQL."
    )
    parser.add_argument("--server", default=DEFAULT_SERVER, help="Synapse serverless SQL endpoint")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Warehouse metadata database")
    parser.add_argument("--sqlcmd", help="Path to sqlcmd executable (defaults to PATH / WinGet)")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without connecting")
    args = parser.parse_args(argv)

    files = sql_files()
    executable = (args.sqlcmd or "sqlcmd") if args.dry_run else find_sqlcmd(args.sqlcmd)
    if not executable:
        print(
            "sqlcmd was not found. Install it with `winget install Microsoft.Sqlcmd`, "
            "then reopen the terminal or pass --sqlcmd <path>.",
            file=sys.stderr,
        )
        return 2

    for sql_file in files:
        command = build_command(executable, args.server, args.database, sql_file)
        print(f"[{sql_file.name}] database={'master' if sql_file.name == '00_create_database.sql' else args.database}")
        if args.dry_run:
            print(subprocess.list2cmdline(command))
            continue
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            print(
                f"Deployment stopped at {sql_file.name} (sqlcmd exit code {result.returncode}); "
                "fix the SQL error and rerun. Earlier files are safe to rerun.",
                file=sys.stderr,
            )
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
