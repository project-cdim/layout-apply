# Copyright (C) 2026 NEC Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
#  under the License.
"""Test for cancel command"""

import re
import sys
from multiprocessing import Process

import psutil
import psycopg2
import pytest
from psycopg2.extras import DictCursor

from layoutapply.cli import main
from layoutapply.const import ExitCode, IdParameter, Result
from layoutapply.db import DbAccess
from layoutapply.util import create_randomname
from tests.layoutapply.conftest import SELECT_SQL, mock_run
from tests.layoutapply.test_data import sql


class TestCancelHelp:
    """Test cases for the cancel command help option."""

    @pytest.mark.parametrize(
        "args",
        [
            (
                [
                    "cancel",
                    "--help",
                ]
            ),
            (
                [
                    "cancel",
                    "-h",
                ]
            ),
        ],
    )
    def test_cmd_cancel_success_when_help(
        self,
        args,
        capfd,
    ):
        """Test that the cancel command displays help information successfully."""
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0
        out, _ = capfd.readouterr()

        # help message is displayed in the standard output
        assert "usage" in out
        assert "options:" in out
        assert "-h" in out
        assert "--help" in out
        assert "--apply-id" in out
        assert "APPLY_ID" in out


class TestCancelSuccess:
    """Test cases for the cancel command when it succeeds."""

    @pytest.mark.parametrize(
        "args, status",
        [
            (["cancel", "--apply-id"], Result.IN_PROGRESS),
            (["cancel", "--apply-id"], Result.CANCELING),
        ],
    )
    def test_cmd_cancel_cancelable_by_command(self, init_db_instance, args, status, capfd):
        """Test that the cancel command successfully cancels a layout apply that is in progress."""
        # arrange
        assert_print = "Success.\nstatus=CANCELING\n"
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        # Register the execution process in the database.
        proc_obj = psutil.Process(proc.pid)
        execution_cmd = proc_obj.cmdline()
        process_start = str(proc_obj.create_time())
        apply_id = create_randomname(IdParameter.LENGTH)
        query_str = """
            INSERT INTO applystatus
            (applyid, status, processid, executioncommand, processstartedat)
            VALUES (%s, %s, %s, %s, %s)
        """
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=query_str, vars=[apply_id, status, proc.pid, "".join(execution_cmd), process_start])
            init_db_instance.commit()

        # arrange
        args.append(apply_id)
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        # Delete the mock process.
        proc.terminate()
        proc.join()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # message indicating the change in reflection status due to cancellation is output to the standard output.
        assert out == assert_print
        # There is no standard error output.
        assert err == ""
        if proc.is_alive():
            proc.terminate()
            proc.join()

    def test_cmd_cancel_registered_in_db_when_auto_rollback_option_added(self, init_db_instance):
        """Test that the cancel command registers
        the cancellation in the database when the auto-rollback option is added."""
        # arrange
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        # Register the execution process in the database.
        proc_obj = psutil.Process(proc.pid)
        execution_cmd = proc_obj.cmdline()
        process_start = str(proc_obj.create_time())
        apply_id = create_randomname(IdParameter.LENGTH)
        query_str = """
            INSERT INTO applystatus
            (applyid, status, processid, executioncommand, processstartedat)
            VALUES (%s, %s, %s, %s, %s)
        """
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query=query_str, vars=[apply_id, Result.IN_PROGRESS, proc.pid, "".join(execution_cmd), process_start]
            )
            init_db_instance.commit()
        # arrange

        args = ["cancel", "--apply-id", apply_id, "--rollback-on-cancel"]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        # Delete the mock process.
        proc.terminate()
        proc.join()
        assert excinfo.value.code == ExitCode.NORMAL
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        cursor.execute(query=SELECT_SQL, vars=[apply_id])
        init_db_instance.commit()
        row = cursor.fetchone()
        assert row.get("executerollback")

        if proc.is_alive():
            proc.terminate()
            proc.join()

    @pytest.mark.parametrize("args", [["cancel", "--apply-id", "012345678c"]])
    def test_cmd_cancel_success_when_specified_canceled_config_id(self, init_db_instance, args, capfd):
        """Test that the cancel command successfully cancels a layout apply that is already canceled."""
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_status_canceled_sql, vars=[applyid])
            init_db_instance.commit()
        assert_print = "Success.\nstatus=CANCELED\n"

        args = ["cancel", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # message indicating the change in reflection status due to cancellation is output to the standard output.
        assert out == assert_print
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            (["cancel", "--apply-id"]),
        ],
    )
    def test_cmd_cancel_failure_when_no_failure_on_process_in_canceled_with_rollback_in_progress(
        self, init_db_instance, args, capfd
    ):
        """Test that the cancel command fails when no apply ID is provided."""

        assert_print = "[E40022]This layoutapply has already executed.\n"
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        # Register the execution process in the database.
        proc_obj = psutil.Process(proc.pid)
        execution_cmd = proc_obj.cmdline()
        process_start = str(proc_obj.create_time())
        apply_id = create_randomname(IdParameter.LENGTH)
        query_str = """
            INSERT INTO applystatus
            (applyid, status, processid, executioncommand, processstartedat)
            VALUES (%s, %s, %s, %s, %s)
        """
        r_query_str = """
            INSERT INTO rollbackstatus
            (applyid, status, processid, executioncommand, processstartedat)
            VALUES (%s, %s, %s, %s, %s)
        """
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query=query_str,
                vars=[apply_id, Result.CANCELED, proc.pid, "".join(execution_cmd), process_start],
            )
            cursor.execute(
                query=r_query_str,
                vars=[apply_id, Result.IN_PROGRESS, proc.pid, "".join(execution_cmd), process_start],
            )
            init_db_instance.commit()
        args.append(apply_id)
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        # Delete the mock process.
        proc.terminate()
        proc.join()
        assert excinfo.value.code == ExitCode.MULTIPLE_RUN_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # standard error output displays the E40022 error.
        assert err == assert_print
        if proc.is_alive():
            proc.terminate()
            proc.join()

    def test_cmd_cancel_rollback_in_progress_to_failed_ends_failure_when_subprocess_not_found(
        self, init_db_instance, capfd
    ):
        """Test that the cancel command changes
        the rollback status from IN_PROGRESS to FAILED when the subprocess is not found."""
        # arrange
        assert_print = (
            "[E40028]Since the process with the specified ID does not exist, "
            + "change the rollbackStatus from IN_PROGRESS to FAILED.\nstatus=CANCELED\nrollbackStatus=FAILED\n"
        )
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        # Register the execution process in the database.
        apply_id = create_randomname(IdParameter.LENGTH)
        query_str = """
            INSERT INTO applystatus
            (applyid, status, processid, executioncommand, processstartedat)
            VALUES (%s, %s, %s, %s, %s)
        """
        r_query_str = """
            INSERT INTO rollbackstatus
            (applyid, status, processid, executioncommand, processstartedat)
            VALUES (%s, %s, %s, %s, %s)
        """
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query=query_str,
                vars=[apply_id, Result.CANCELED, proc.pid, "dummy", 0],
            )
            cursor.execute(
                query=r_query_str,
                vars=[apply_id, Result.IN_PROGRESS, proc.pid, "dummy", 0],
            )
            init_db_instance.commit()

        # Delete the execution process.
        proc.terminate()
        proc.join()
        args = ["cancel", "--apply-id", apply_id]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.MULTIPLE_RUN_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # standard error output displays the error details and the changed reflection status.
        assert err == assert_print

        if proc.is_alive():
            proc.terminate()
            proc.join()

    def test_cmd_cancel_rollback_suspended_to_failed_possible(self, init_db_instance, capfd):
        """Test that the cancel command changes
        the rollback status from SUSPENDED to FAILED when the apply is already canceled."""
        # Data adjustment before testing.
        apply_id = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="INSERT INTO applyStatus (applyID,status,startedAt) "
                + f"VALUES('{apply_id}','{Result.CANCELED}',null)"
            )
            cursor.execute(
                query="INSERT INTO rollbackStatus (applyID,status,startedAt) "
                + f"VALUES('{apply_id}','{Result.SUSPENDED}',null)"
            )
            init_db_instance.commit()
        # arrange
        assert_print = "Success.\nstatus=CANCELED\nrollbackStatus=FAILED\n"

        args = ["cancel", "--apply-id", apply_id]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL

        # assert
        out, err = capfd.readouterr()
        # standard output displays the changed reflection status.
        assert out == assert_print
        # There is no standard error output.
        assert err == ""


class TestCancelFailure:
    """Test cases for cancel command failures."""

    def test_cmd_cancel_failure_when_specified_completed_config_id(self, init_db_instance, capfd):
        """Test that the cancel command fails when the specified layout apply has already been completed."""
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_status_completed_sql, vars=[applyid])
            init_db_instance.commit()
        assert_print = "[E40022]This layoutapply has already executed.\n"

        args = ["cancel", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.MULTIPLE_RUN_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # error E40022 is output to the standard error.
        assert err == assert_print

    @pytest.mark.parametrize("args", [["cancel", "--apply-id", "012345678g"]])
    def test_cmd_cancel_usage_displayed_when_invalid_option(self, args, capfd):
        """Test that the cancel command displays usage information when an invalid option is provided."""
        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.VALIDATION_ERR
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out == ""
        assert err.startswith("[E40001]")

    @pytest.mark.parametrize("args", [["cancel", "--apply-id", "012345678a"]])
    def test_cmd_cancel_failure_when_invalid_config_file(self, mocker, args, capfd):
        """Test that the cancel command fails when the configuration file is invalid."""
        config = {
            "layout_apply": {
                "host": "0.0.0.0",
                "port": 8003,
            },
            "db": {
                "dbname": "ApplyStatusDB",
                "user": "user01",
                "password": "P@ssw0rd",
                "host": "localhost",
                "port": 5432,
            },
            "hardware_control": {
                # No required item
                # "host": "localhost",
                "port": 8888,
                "uri": "api/v1",
                "disconnect": {
                    "retry": {
                        "interval": 5,
                        "max_count": 5,
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                            },
                        ],
                        "skip": [
                            {"status_code": 400, "code": "EF003BAS010"},
                        ],
                    }
                },
            },
            "message_broker": {
                "host": "localhost",
                "port": 3500,
                "pubsub": "layout_apply_apply",
                "topic": "layout_apply_apply.completed",
            },
        }

        mocker.patch("yaml.safe_load").return_value = config
        sys.argv = ["cli.py", *args]

        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert

        assert excinfo.value.code == 2
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # There is an error message in the standard error output that starts with the specified error code
        regex = re.compile(r"^\[E40002\]Failed to load layoutapply_config.yaml.")
        assert regex.search(err)

    @pytest.mark.parametrize("args", [["cancel", "--apply-id", "012345678d"]])
    def test_cmd_cancel_failure_when_failed_db_connection(self, mocker, args, capfd):
        """Test that the cancel command fails when the database connection cannot be established."""
        assert_print = "[E40018]Could not connect to ApplyStatusDB."
        mocker.patch.object(DbAccess, "proc_cancel", side_effect=psycopg2.OperationalError)
        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.DB_CONNECT_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""

        assert assert_print in err

    @pytest.mark.parametrize("args", [["cancel", "--apply-id", "012345678d"]])
    def test_cmd_cancel_failure_when_query_failure_occurred(self, mocker, args, capfd):
        """Test that the cancel command fails when a query failure occurs."""
        assert_print = "[E40019]Query failed."
        # mocker.patch("psycopg2.connect", return_value=init_db_instance)
        # mocker.patch.object(DbAccess, "close", return_value=None)
        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)
        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.QUERY_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # error E40019 is output to the standard error.
        assert assert_print in err

    @pytest.mark.parametrize("args", [["cancel", "--apply-id", "abcdeabcde"]])
    def test_cmd_cancel_failure_when_not_exist_id_specified(
        self, init_db_instance, args, capfd
    ):  # pylint: disable=W0613
        """Test that the cancel command fails when a non-existent apply ID is specified."""
        assert_print = "[E40020]Specified abcdeabcde is not found.\n"

        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.ID_NOT_FOUND_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # standard error outputs the E40020 error.
        assert err == assert_print

    def test_cmd_cancel_failure_changes_to_failure_when_mismatched_subprocess_info(self, init_db_instance, capfd):
        """Test that the cancel command changes
        the status to FAILED when there is a mismatch in subprocess information."""
        # Ensure no active data exists before the test

        assert_print = (
            "[E40028]Since the process with the specified ID does not exist, "
            + "change the status from IN_PROGRESS to FAILED.\nstatus=FAILED\n"
        )
        # arrange
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        # Register data that does not match the execution process in the database.
        apply_id = create_randomname(IdParameter.LENGTH)
        query_str = (
            "INSERT INTO applystatus (applyid, status, processid, executioncommand, processstartedat)"
            f"VALUES ('{apply_id}', '{Result.IN_PROGRESS}', {proc.pid}, 'dummy', '0')"
        )
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=query_str)
            init_db_instance.commit()
        # arrange

        args = ["cancel", "--apply-id", apply_id]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        proc.terminate()
        proc.join()
        assert excinfo.value.code == ExitCode.MULTIPLE_RUN_ERR
        out, err = capfd.readouterr()
        # message indicating the change in reflection status due to cancellation is output to the standard output.
        assert out == ""
        # There is no standard error output.
        assert err == assert_print

        if proc.is_alive():
            proc.terminate()
            proc.join()

    def test_cmd_cancel_failure_changes_to_failure_when_subprocess_not_found(self, init_db_instance, capfd):
        """Test that the cancel command changes the status to FAILED when the subprocess is not found."""

        assert_print = (
            "[E40028]Since the process with the specified ID does not exist, "
            + "change the status from IN_PROGRESS to FAILED.\nstatus=FAILED\n"
        )
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        # Register the execution process in the database.
        apply_id = create_randomname(IdParameter.LENGTH)
        query_str = (
            "INSERT INTO applystatus (applyid, status, processid, executioncommand, processstartedat)"
            f"VALUES ('{apply_id}', '{Result.IN_PROGRESS}', {proc.pid}, 'dummy', '0')"
        )
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=query_str)
            init_db_instance.commit()

        # Delete the execution process.
        proc.terminate()
        proc.join()
        args = ["cancel", "--apply-id", apply_id]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.MULTIPLE_RUN_ERR
        out, err = capfd.readouterr()
        # message indicating the change in reflection status due to cancellation is output to the standard output.
        assert out == ""
        # There is no standard error output.
        assert err == assert_print

        if proc.is_alive():
            proc.terminate()
            proc.join()
