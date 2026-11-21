import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts import deploy_sql


class DeploySqlTests(unittest.TestCase):
    def test_sql_files_are_sorted_and_only_numbered_sql_files_are_deployed(self):
        with tempfile.TemporaryDirectory() as directory:
            warehouse_dir = Path(directory)
            for name in ("20_silver.sql", "00_create_database.sql", "README.md", "10_external.sql"):
                (warehouse_dir / name).write_text("-- test", encoding="utf-8")

            original_dir = deploy_sql.WAREHOUSE_DIR
            try:
                deploy_sql.WAREHOUSE_DIR = warehouse_dir
                self.assertEqual(
                    [path.name for path in deploy_sql.sql_files()],
                    ["00_create_database.sql", "10_external.sql", "20_silver.sql"],
                )
            finally:
                deploy_sql.WAREHOUSE_DIR = original_dir

    def test_sqlcmd_targets_master_only_for_database_creation(self):
        master = deploy_sql.build_command("sqlcmd", "server", "warehouse", Path("00_create_database.sql"))
        warehouse = deploy_sql.build_command("sqlcmd", "server", "warehouse", Path("30_gold_star.sql"))

        self.assertEqual(master[master.index("-d") + 1], "master")
        self.assertEqual(warehouse[warehouse.index("-d") + 1], "warehouse")
        self.assertIn("ActiveDirectoryAzCli", warehouse)
        self.assertTrue(warehouse[-1].endswith("30_gold_star.sql"))

    def test_dry_run_needs_no_sqlcmd_or_azure_login(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = deploy_sql.main(["--dry-run", "--server", "example.sql.azuresynapse.net"])

        self.assertEqual(result, 0)
        self.assertIn("00_create_database.sql", output.getvalue())
        self.assertIn("30_gold_star.sql", output.getvalue())
        self.assertIn("-d master", output.getvalue())
        self.assertIn("-d megasale_warehouse", output.getvalue())


if __name__ == "__main__":
    unittest.main()
