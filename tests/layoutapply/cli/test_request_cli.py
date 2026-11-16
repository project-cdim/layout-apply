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
"""Test for command"""

import copy
import json
import logging
import logging.config  # pylint: disable=unused-import
import os
import re
import secrets
import string
import sys
import tempfile
from multiprocessing import Process
from time import sleep

import psutil
import psycopg2
import pytest
from psycopg2.extras import DictCursor

from layoutapply.cli import LayoutApplyCommandLine, main
from layoutapply.const import Action, IdParameter
from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.db import DbAccess
from layoutapply.main import run
from layoutapply.setting import LayoutApplyConfig, LayoutApplyLogConfig
from layoutapply.util import create_randomname
from tests.layoutapply.conftest import (
    BASE_CONFIG,
    EXTENDED_PROCEDURE_URI,
    LOG_BASE_CONFIG,
    OPERATION_URL,
    OS_BOOT_URL,
    POWER_OPERATION_URL,
    WORKFLOW_MANAGER_PORT,
)
from tests.layoutapply.test_data import checkvalid, procedure, sql


@pytest.fixture()
def get_applyID():  # pylint:disable=C0103
    """Fixture to generate a random apply ID."""
    return "".join([secrets.choice(string.hexdigits) for i in range(10)]).lower()


@pytest.mark.usefixtures("httpserver_listen_address")
class TestRequestSuccess:
    """Test class for request command successes."""

    @pytest.mark.skip
    @pytest.mark.usefixtures("hardwaremgr_fixture", "extended_procedure_fixture")
    def test_cmd_apply_success_when_migration_step_with_rel_path(
        self, capfd, mocker, init_db_instance, get_applyID
    ):  # pylint:disable=C0103
        """Test that the request command succeeds when the migration step is specified with a relative path."""
        # Ensure no active data exists before the test
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="UPDATE applystatus SET status = 'TEST_PROG' WHERE status = 'IN_PROGRESS'")
            cursor.execute(query="UPDATE applystatus SET status = 'TEST_CANC' WHERE status = 'CANCELING'")
            cursor.execute(query="UPDATE applystatus SET status = 'TEST_SUSPEND' WHERE status = 'SUSPENDED'")
            init_db_instance.commit()
        # arrange
        mocker.patch("layoutapply.db.create_randomname", return_value=get_applyID)

        for pattern in procedure.multi_pattern:
            procedures = pattern[0]

            with tempfile.TemporaryDirectory() as tempdir:
                arg_procedure = os.path.join(tempdir, "procedure.json")
                with open(arg_procedure, "w", encoding="utf-8") as file:
                    json.dump(procedures, file)
                # Obtain the relative path
                rel_path = os.path.relpath(arg_procedure, os.getcwd())
                sys.argv = ["cli.py", "request", "-p", rel_path]

                config = LayoutApplyConfig()
                config.load_log_configs()
                config.workflow_manager["host"] = "localhost"
                # act
                procces_mock = mocker.patch(
                    "subprocess.Popen",
                    return_value=Process(
                        target=run,
                        args=(procedures, config, get_applyID, Action.REQUEST),
                    ),
                )

                with pytest.raises(SystemExit) as excinfo:
                    main()
                out, err = capfd.readouterr()
                id_ = json.loads(out).get("applyID")
                procces_mock.return_value.start()
                with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                    try:
                        cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{id_}'")
                        init_db_instance.commit()
                        row = cursor.fetchone()
                    except psycopg2.ProgrammingError:
                        continue

                    # assert
                    assert excinfo.value.code == 0
                    assert "Request was successful. Start applying" in err
                    skip_next = False
                    assert json.loads(out) == {"applyID": id_}
                    # result of the operation completion list is 'IN_PROGRESS'
                    if row.get("status") == "IN_PROGRESS":
                        assert row.get("status") == "IN_PROGRESS"
                        for _ in range(15):
                            sleep(2)
                            try:
                                cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{id_}'")
                                init_db_instance.commit()
                                row = cursor.fetchone()
                            except psycopg2.ProgrammingError:
                                skip_next = True
                                break
                            if row.get("status") == "COMPLETED":
                                break
                        pid = row.get("processid")
                        if pid is not None:
                            process = psutil.Process(pid)
                            if process.is_running():
                                process.terminate()
                if skip_next:
                    continue
                assert row.get("status") == "COMPLETED"
                assert row.get("rollbackprocedures") is None
                details = row.get("result")
                assert details is not None
                assert len(details) == len(procedures["procedures"])
                host = config.hardware_control.get("host")
                port = config.hardware_control.get("port")
                uri = config.hardware_control.get("uri")
                for proc in procedures["procedures"]:
                    # Search for items corresponding to the migration procedure from
                    # result details using operationID as a condition
                    id_cnt = sum(1 for n in details if n["operationID"] == proc["operationID"])
                    detail = [i for i in details if i["operationID"] == proc["operationID"]][id_cnt - 1]
                    assert proc["operationID"] == detail["operationID"]
                    assert "COMPLETED" == detail["status"]
                    # Check the URI, etc. of the hardware control API

                    # Review the mockup method with hardwaremgr_fixture as well
                    match proc["operation"]:
                        case "connect":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",  # noqa:W605
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert "queryParameter" not in detail
                            assert detail["requestBody"] == {
                                "action": "connect",
                                "destinationDeviceID": proc["targetDeviceID"],
                            }
                            assert 200 == detail["statusCode"]

                        case "disconnect":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",  # noqa:W605
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {
                                "action": "disconnect",
                                "destinationDeviceID": proc["targetDeviceID"],
                            }
                            assert "queryParameter" not in detail
                            assert 200 == detail["statusCode"]

                        case "boot":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",  # noqa:W605
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {"action": "on"}
                            assert "queryParameter" not in detail
                            assert 200 == detail["statusCode"]
                            is_os_boot_detail = detail["isOSBoot"]
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OS_BOOT_URL}",  # noqa:W605
                                is_os_boot_detail["uri"],
                            )
                            assert "GET" == is_os_boot_detail["method"]
                            assert "queryParameter" in is_os_boot_detail
                            assert is_os_boot_detail["queryParameter"] == {"timeOut": 30}
                            assert is_os_boot_detail["statusCode"] == 200

                        case "shutdown":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",  # noqa:W605
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert {"action": "off"} == detail["requestBody"]
                            assert detail["getInformation"]["responseBody"] == {"powerState": "Off"}
                            assert "queryParameter" not in detail
                            assert 200 == detail["statusCode"]
                        case "start":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{WORKFLOW_MANAGER_PORT}\/{uri}\/{EXTENDED_PROCEDURE_URI}",  # noqa:W605
                                detail["uri"],
                            )
                            assert "POST" == detail["method"]
                            assert "start" == detail["requestBody"].get("operation")
                            assert "queryParameter" not in detail
                            assert 202 == detail["statusCode"]
                        case "stop":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{WORKFLOW_MANAGER_PORT}\/{uri}\/{EXTENDED_PROCEDURE_URI}",  # noqa:W605
                                detail["uri"],
                            )
                            assert "POST" == detail["method"]
                            assert "stop" == detail["requestBody"].get("operation")
                            assert "queryParameter" not in detail
                            assert 202 == detail["statusCode"]

        if procces_mock.return_value.is_alive():
            procces_mock.return_value.terminate()
            procces_mock.return_value.join()

    @pytest.mark.usefixtures("hardwaremgr_fixture", "extended_procedure_fixture")
    def test_cmd_apply_success_when_migration_step_with_rel_path_use_run_function(
        self, capfd, mocker, init_db_instance, get_applyID
    ):  # pylint:disable=C0103
        """Test that the request command succeeds when
        the migration step is specified with a relative path and the run function is used."""
        # Ensure no active data exists before the test
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="UPDATE applystatus SET status = 'TEST_PROG' WHERE status = 'IN_PROGRESS'")
            cursor.execute(query="UPDATE applystatus SET status = 'TEST_CANC' WHERE status = 'CANCELING'")
            cursor.execute(query="UPDATE applystatus SET status = 'TEST_SUSPEND' WHERE status = 'SUSPENDED'")
            init_db_instance.commit()
        # arrange
        mocker.patch("layoutapply.db.create_randomname", return_value=get_applyID)

        for pattern in procedure.multi_pattern:
            procedures = pattern[0]

            with tempfile.TemporaryDirectory() as tempdir:
                arg_procedure = os.path.join(tempdir, "procedure.json")
                with open(arg_procedure, "w", encoding="utf-8") as file:
                    json.dump(procedures, file)
                # Obtain the relative path
                rel_path = os.path.relpath(arg_procedure, os.getcwd())
                sys.argv = ["cli.py", "request", "-p", rel_path]

                config = LayoutApplyConfig()
                config.load_log_configs()
                config.workflow_manager["host"] = "localhost"

                # act
                with pytest.raises(SystemExit) as excinfo:
                    main()
                out, err = capfd.readouterr()
                id_ = json.loads(out).get("applyID")

                run(procedures, config, get_applyID, Action.REQUEST)

                with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                    try:
                        cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{id_}'")
                        init_db_instance.commit()
                        row = cursor.fetchone()
                    except psycopg2.ProgrammingError:
                        continue

                    # assert
                    assert excinfo.value.code == 0
                    assert "Request was successful. Start applying" in err
                    skip_next = False
                    assert json.loads(out) == {"applyID": id_}

                    # Check if status is COMPLETED (run function should have completed)
                    if row.get("status") != "COMPLETED":
                        skip_next = True

                if skip_next:
                    continue

                assert row.get("status") == "COMPLETED"
                assert row.get("rollbackprocedures") is None
                details = row.get("result")
                assert details is not None
                assert len(details) == len(procedures["procedures"])
                host = config.hardware_control.get("host")
                port = config.hardware_control.get("port")
                uri = config.hardware_control.get("uri")
                for proc in procedures["procedures"]:
                    # Search for items corresponding to the migration procedure from
                    # result details using operationID as a condition
                    id_cnt = sum(1 for n in details if n["operationID"] == proc["operationID"])
                    detail = [i for i in details if i["operationID"] == proc["operationID"]][id_cnt - 1]
                    assert proc["operationID"] == detail["operationID"]
                    assert "COMPLETED" == detail["status"]
                    # Check the URI, etc. of the hardware control API
                    # Review the mockup method with hardwaremgr_fixture as well
                    match proc["operation"]:
                        case "connect":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",  # noqa:W605
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert "queryParameter" not in detail
                            assert detail["requestBody"] == {
                                "action": "connect",
                                "destinationDeviceID": proc["targetDeviceID"],
                            }
                            assert 200 == detail["statusCode"]

                        case "disconnect":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",  # noqa:W605
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {
                                "action": "disconnect",
                                "destinationDeviceID": proc["targetDeviceID"],
                            }
                            assert "queryParameter" not in detail
                            assert 200 == detail["statusCode"]

                        case "boot":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",  # noqa:W605
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {"action": "on"}
                            assert "queryParameter" not in detail
                            assert 200 == detail["statusCode"]
                            is_os_boot_detail = detail["isOSBoot"]
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OS_BOOT_URL}",  # noqa:W605
                                is_os_boot_detail["uri"],
                            )
                            assert "GET" == is_os_boot_detail["method"]
                            assert "queryParameter" in is_os_boot_detail
                            assert is_os_boot_detail["queryParameter"] == {"timeOut": 30}
                            assert is_os_boot_detail["statusCode"] == 200

                        case "shutdown":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",  # noqa:W605
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert {"action": "off"} == detail["requestBody"]
                            assert detail["getInformation"]["responseBody"] == {"powerState": "Off"}
                            assert "queryParameter" not in detail
                            assert 200 == detail["statusCode"]
                        case "start":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{WORKFLOW_MANAGER_PORT}\/{uri}\/{EXTENDED_PROCEDURE_URI}",  # noqa:W605
                                detail["uri"],
                            )
                            assert "POST" == detail["method"]
                            assert "start" == detail["requestBody"].get("operation")
                            assert "queryParameter" not in detail
                            assert 202 == detail["statusCode"]
                        case "stop":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{WORKFLOW_MANAGER_PORT}\/{uri}\/{EXTENDED_PROCEDURE_URI}",  # noqa:W605
                                detail["uri"],
                            )
                            assert "POST" == detail["method"]
                            assert "stop" == detail["requestBody"].get("operation")
                            assert "queryParameter" not in detail
                            assert 202 == detail["statusCode"]

    @pytest.mark.usefixtures("hardwaremgr_fixture")
    def test_cmd_apply_success_when_migration_step_empty(
        self, capfd, mocker, init_db_instance, get_applyID
    ):  # pylint:disable=C0103
        """Test command apply success when migration step is empty."""
        # arrange

        mocker.patch("layoutapply.db.create_randomname", return_value=get_applyID)

        with tempfile.TemporaryDirectory() as tempdir:
            arg_procedure = os.path.join(tempdir, "procedure.json")
            for pattern in procedure.proc_empty_pattern:
                procedures = pattern[0]

                with open(arg_procedure, "w", encoding="utf-8") as file:
                    json.dump(procedures, file)
                sys.argv = ["cli.py", "request", "-p", arg_procedure]

                config = LayoutApplyConfig()
                log_config = LayoutApplyLogConfig()
                # act
                procces_mock = mocker.patch(
                    "subprocess.Popen",
                    return_value=Process(
                        target=run,
                        args=(procedures, config, log_config, get_applyID, Action.REQUEST),
                    ),
                )
                with pytest.raises(SystemExit) as excinfo:
                    main()
                out, err = capfd.readouterr()
                id_ = json.loads(out).get("applyID")
                procces_mock.return_value.start()

                with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                    cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{id_}'")
                    init_db_instance.commit()
                    row = cursor.fetchone()

                # assert

                assert excinfo.value.code == 0
                assert "Request was successful. Start applying" in err
                assert json.loads(out) == {"applyID": id_}
                assert row.get("status") == "COMPLETED"
                assert row.get("rollbackprocedures") is None
                assert row.get("procedures") == []
                details = row.get("result")
                assert details == []
                assert len(details) == len(procedures["procedures"])
        if procces_mock.return_value.is_alive():
            procces_mock.return_value.terminate()
            procces_mock.return_value.join()

    def test_cmd_apply_failure_when_migration_step_missing(self, capfd):
        """Test command apply failure when migration step is missing."""
        # arrange
        with tempfile.TemporaryDirectory() as tempdir:
            arg_procedure = os.path.join(tempdir, "procedure.json")
            # Do not create a migration plan file
            # with open(arg_procedure, "w", encoding="utf-8") as file:
            #     json.dump(procedures, file)
            sys.argv = ["cli.py", "request", "-p", arg_procedure]

            # act
            with pytest.raises(SystemExit) as excinfo:
                main()

            # assert

            assert excinfo.value.code == 1
            out, err = capfd.readouterr()
            # There is no standard output
            assert out == ""
            # There is an error message in the standard error output that starts with the specified error code
            regex = re.compile(r"^\[E40001\]")
            assert regex.search(err)

    @pytest.mark.parametrize("procedures", checkvalid.invalid_data_type)
    def test_cmd_apply_failure_when_invalid_migration_step(self, capfd, procedures):
        """Test command apply failure when migration step has an invalid data type."""
        # arrange
        with tempfile.TemporaryDirectory() as tempdir:
            arg_procedure = os.path.join(tempdir, "procedure.json")
            with open(arg_procedure, "w", encoding="utf-8") as file:
                json.dump(procedures, file)
            sys.argv = ["cli.py", "request", "-p", arg_procedure]

            # act
            with pytest.raises(SystemExit) as excinfo:
                main()

            # assert

            assert excinfo.value.code == 1
            out, err = capfd.readouterr()
            # There is no standard output
            assert out == ""
            # There is an error message in the standard error output that starts with the specified error code
            regex = re.compile(r"^\[E40001\]")
            assert regex.search(err)

    @pytest.mark.parametrize("procedures", checkvalid.without_required_key)
    def test_cmd_apply_failure_when_missing_required_migration_item(self, capfd, procedures):
        """Test command apply failure when a required migration item is missing."""
        # arrange
        with tempfile.TemporaryDirectory() as tempdir:
            arg_procedure = os.path.join(tempdir, "procedure.json")
            with open(arg_procedure, "w", encoding="utf-8") as file:
                json.dump(procedures, file)

            sys.argv = ["cli.py", "request", "-p", arg_procedure]

            # act
            with pytest.raises(SystemExit) as excinfo:
                main()

            # assert

            assert excinfo.value.code == 1
            out, err = capfd.readouterr()
            # There is no standard output
            assert out == ""
            # There is an error message in the standard error output that starts with the specified error code
            regex = re.compile(r"^\[E40001\]")
            assert regex.search(err)

    @pytest.mark.parametrize("procedures", checkvalid.any_key_combination)
    def test_cmd_apply_failure_when_any_key_combination(self, capfd, procedures):
        """Test command apply failure when any key combination is used."""
        # arrange
        with tempfile.TemporaryDirectory() as tempdir:
            arg_procedure = os.path.join(tempdir, "procedure.json")
            with open(arg_procedure, "w", encoding="utf-8") as file:
                json.dump(procedures, file)

            sys.argv = ["cli.py", "request", "-p", arg_procedure]

            # act
            with pytest.raises(SystemExit) as excinfo:
                main()

            # assert

            assert excinfo.value.code == 1
            out, err = capfd.readouterr()
            # There is no standard output
            assert out == ""
            # There is an error message in the standard error output that starts with the specified error code
            regex = re.compile(r"^\[E40001\]")
            assert regex.search(err)

    @pytest.mark.parametrize("procedures", checkvalid.invalid_value)
    def test_cmd_apply_failure_when_invalid_migration_value(self, capfd, procedures):
        """Test command apply failure when a migration item has an invalid value."""
        # arrange
        with tempfile.TemporaryDirectory() as tempdir:
            arg_procedure = os.path.join(tempdir, "procedure.json")
            with open(arg_procedure, "w", encoding="utf-8") as file:
                json.dump(procedures, file)
            sys.argv = ["cli.py", "request", "-p", arg_procedure]

            # act
            with pytest.raises(SystemExit) as excinfo:
                main()

            # assert

            assert excinfo.value.code == 1
            out, err = capfd.readouterr()
            # There is no standard output
            assert out == ""
            # There is an error message in the standard error output that starts with the specified error code
            regex = re.compile(r"^\[E40001\]")
            assert regex.search(err)

    def test_cmd_apply_failure_when_failed_to_load_config_file(self, mocker, capfd):
        """Test command apply failure when failed to load the configuration file."""
        mocker.patch(
            "yaml.safe_load", side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")]
        )
        with tempfile.TemporaryDirectory() as tempdir:
            procedure_path = os.path.join(tempdir, "procedure.json")
            with open(procedure_path, "w", encoding="utf-8") as file:
                json.dump(procedure.dummy_data, file)

            args = ["cli.py", "request", "-p", procedure_path]
            sys.argv = args
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

    def test_cmd_apply_failure_when_failed_to_read_secret_file(self, mocker, capfd):
        """Test command apply failure when failed to read the secret file."""
        mocker.patch.object(LayoutApplyConfig, "_get_secret", side_effect=[Exception("Dummy message")])
        with tempfile.TemporaryDirectory() as tempdir:
            procedure_path = os.path.join(tempdir, "procedure.json")
            with open(procedure_path, "w", encoding="utf-8") as file:
                json.dump(procedure.dummy_data, file)

            args = ["cli.py", "request", "-p", procedure_path]
            sys.argv = args
            # act
            with pytest.raises(SystemExit) as excinfo:
                main()

            # assert

            assert excinfo.value.code == 15
            out, err = capfd.readouterr()
            # There is no standard output
            assert out == ""
            # There is an error message in the standard error output that starts with the specified error code
            regex = re.compile(r"^\[E40030\]Failed to retrieve secret store")
            assert regex.search(err)

    @pytest.mark.parametrize(
        "update_config",
        [
            # log_dir is invalid
            {
                "version": 1,
                "formatters": {
                    "standard": {"format": "%(asctime)s %(levelname)s %(message)s", "datefmt": "%Y/%m/%d %H:%M:%S.%f"}
                },
                "handlers": {
                    "file": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "level": "INFO",
                        "formatter": "standard",
                        "filename": "/test/test/app_layout_apply.log",
                        "maxBytes": 100000000,
                        "backupCount": 72,
                        "encoding": "utf-8",
                    },
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO",
                        "formatter": "standard",
                        "stream": "ext://sys.stdout",
                    },
                },
                "root": {"level": "INFO", "handlers": ["file", "console"]},
            }
        ],
    )
    def test_cmd_apply_failure_when_failed_to_initialize_logger(
        self, mocker, capfd, update_config, docker_services
    ):  # pylint:disable=unused-argument
        """Test command apply failure when failed to initialize the logger."""
        mocker.patch.object(LayoutApplyLogConfig, "_validate_log_dir")
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        config = {**base_config, **update_config}
        mocker.patch("yaml.safe_load").side_effect = [BASE_CONFIG, config]
        with tempfile.TemporaryDirectory() as tempdir:
            procedure_path = os.path.join(tempdir, "procedure.json")
            with open(procedure_path, "w", encoding="utf-8") as file:
                json.dump(procedure.dummy_data, file)

            args = ["cli.py", "request", "-p", procedure_path]
            sys.argv = args
            # act
            with pytest.raises(SystemExit) as excinfo:
                main()

            # assert

            assert excinfo.value.code == 16
            out, err = capfd.readouterr()
            # There is no standard output
            assert out == ""
            # There is an error message in the standard error output that starts with the specified error code
            regex = re.compile(r"^\[E40031\]Internal server error. Failed in log initialization.")
            assert regex.search(err)

    def test_cmd_apply_failure_when_invalid_config_file(self, mocker, capfd):
        """Test command apply failure when the configuration file is invalid."""
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

        with tempfile.TemporaryDirectory() as tempdir:
            procedure_path = os.path.join(tempdir, "procedure.json")
            with open(procedure_path, "w", encoding="utf-8") as file:
                json.dump(procedure.dummy_data, file)

            args = ["cli.py", "request", "-p", procedure_path]
            sys.argv = args
            result_json = {
                "result": "COMPLETED",
                "details": [
                    {
                        "operationID": 1,
                        "status": "COMPLETED",
                        "uri": "http://cdim/api/v1/disconnect",
                        "method": "PUT",
                        "requestBody": "",
                        "queryParameter": {
                            "hostCpuId": "3B4EBEEA-B6DD-45DA-8C8A-2CA2F8F728D6",
                            "targetDeviceID": "895DFB43-68CD-41D6-8996-EAC8D1EA1E3F",
                        },
                        "statusCode": 200,
                        "responseBody": "",
                    }
                ],
            }
            mocker.patch.object(LayoutApplyCommandLine, "_exec_subprocess").return_value = result_json
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

    @pytest.mark.parametrize(
        "args",
        [
            (
                [
                    "request",
                    "--help",
                ]
            ),
            (
                [
                    "request",
                    "-h",
                ]
            ),
        ],
    )
    def test_cmd_apply_success_when_help(
        self,
        args,
        capfd,
    ):
        """Test command apply success when help option is used."""
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
        assert "-p" in out
        assert "--procedure" in out
        assert "PROCEDURE_FILE" in out

    def test_cmd_apply_failure_when_failed_to_acquire_mutex_on_start(
        self,
        capfd,
        init_db_instance,
    ):
        """Test command apply failure when failed to acquire mutex on start."""
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        # Ensure that IN_PROGRESS data exists before the test
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
            init_db_instance.commit()

        with tempfile.TemporaryDirectory() as tempdir:
            arg_procedure = os.path.join(tempdir, "procedure.json")
            for pattern in procedure.single_pattern:
                procedures = pattern[0]

                with open(arg_procedure, "w", encoding="utf-8") as file:
                    json.dump(procedures, file)
                sys.argv = ["cli.py", "request", "-p", arg_procedure]

                # act
                try:
                    with pytest.raises(SystemExit) as excinfo:
                        main()
                    _, err = capfd.readouterr()
                except psycopg2.ProgrammingError:
                    continue

        # assert
        assert excinfo.value.code == 4
        assert err == "[E40010]Already running. Cannot start multiple instances.\n"

    def test_cmd_apply_failure_when_rollback_in_progress_exists_on_start(
        self,
        capfd,
        init_db_instance,
    ):
        """Test command apply failure when rollback in progress exists on start."""
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        # Ensure that  SUSPENDED data exists before the test
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_resumed_get_target_sql_4, vars=[applyid])
            cursor.execute(query=sql.insert_resumed_get_target_sql_r_4, vars=[applyid])
            init_db_instance.commit()

        with tempfile.TemporaryDirectory() as tempdir:
            arg_procedure = os.path.join(tempdir, "procedure.json")
            for pattern in procedure.single_pattern:
                procedures = pattern[0]

                with open(arg_procedure, "w", encoding="utf-8") as file:
                    json.dump(procedures, file)
                sys.argv = ["cli.py", "request", "-p", arg_procedure]

                # act
                try:
                    with pytest.raises(SystemExit) as excinfo:
                        main()
                    _, err = capfd.readouterr()
                except psycopg2.ProgrammingError:
                    continue

        # assert
        assert excinfo.value.code == 4
        assert err == f"[E40027]Suspended data exist. Please resume layoutapply. applyID: {applyid}\n"

    def test_cmd_apply_failure_when_interrupted_data_exists_on_start(
        self,
        capfd,
        init_db_instance,
    ):
        """Test command apply failure when interrupted data exists on start."""
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        # Ensure that  SUSPENDED data exists before the test
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_status_suspended_sql, vars=[applyid])
            init_db_instance.commit()

        with tempfile.TemporaryDirectory() as tempdir:
            arg_procedure = os.path.join(tempdir, "procedure.json")
            for pattern in procedure.single_pattern:
                procedures = pattern[0]

                with open(arg_procedure, "w", encoding="utf-8") as file:
                    json.dump(procedures, file)
                sys.argv = ["cli.py", "request", "-p", arg_procedure]

                # act
                try:
                    with pytest.raises(SystemExit) as excinfo:
                        main()
                    _, err = capfd.readouterr()
                except psycopg2.ProgrammingError:
                    continue

        # assert
        assert excinfo.value.code == 4
        assert err == f"[E40027]Suspended data exist. Please resume layoutapply. applyID: {applyid}\n"

    def test_cmd_apply_failure_when_rollback_interrupted_on_start(
        self,
        capfd,
        init_db_instance,
    ):
        """Test command apply failure when rollback interrupted on start."""
        # Ensure no active data exists before the test
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_delete_target_sql_9, vars=[applyid])
            cursor.execute(query=sql.insert_delete_target_sql_r_9, vars=[applyid])
            init_db_instance.commit()
        # arrange

        with tempfile.TemporaryDirectory() as tempdir:
            arg_procedure = os.path.join(tempdir, "procedure.json")
            for pattern in procedure.single_pattern:
                procedures = pattern[0]

                with open(arg_procedure, "w", encoding="utf-8") as file:
                    json.dump(procedures, file)
                sys.argv = ["cli.py", "request", "-p", arg_procedure]

                # act
                try:
                    with pytest.raises(SystemExit) as excinfo:
                        main()
                    _, err = capfd.readouterr()
                except psycopg2.ProgrammingError:
                    continue

        # assert
        assert excinfo.value.code == 4
        assert err == f"[E40027]Suspended data exist. Please resume layoutapply. applyID: {applyid}\n"

    def test_cmd_apply_failure_when_failed_db_connection(
        self, capfd, mocker, init_db_instance
    ):  # pylint:disable=unused-argument
        """Test command apply failure when failed to connect to the database."""
        # arrange
        mocker.patch.object(DbAccess, "_get_running_data", side_effect=psycopg2.OperationalError)

        with tempfile.TemporaryDirectory() as tempdir:
            arg_procedure = os.path.join(tempdir, "procedure.json")
            procedures = procedure.single_pattern[0][0]

            with open(arg_procedure, "w", encoding="utf-8") as file:
                json.dump(procedures, file)
            sys.argv = ["cli.py", "request", "-p", arg_procedure]

            # act
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code == 10
            out, err = capfd.readouterr()
            # There is no standard output
            assert out == ""

            assert "[E40018]Could not connect to ApplyStatusDB." in err

    def test_cmd_apply_failure_when_query_failure_occurred(self, capfd, caplog, mocker):
        """Test command apply failure when a query failure occurred."""
        # arrange

        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)

        # psycopg2.extras.DictCursor is mocked
        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)
        with tempfile.TemporaryDirectory() as tempdir:
            arg_procedure = os.path.join(tempdir, "procedure.json")
            procedures = procedure.single_pattern[0][0]

            with open(arg_procedure, "w", encoding="utf-8") as file:
                json.dump(procedures, file)
            sys.argv = ["cli.py", "request", "-p", arg_procedure]

            # act
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code == 11
            out, err = capfd.readouterr()
            # There is no standard output
            assert out == ""

            assert "[E40019]Query failed." in err
            assert "[E40019]Query failed." in caplog.text

    def test_cmd_apply_failure_when_failed_to_start_subprocess(
        self,
        capfd,
        caplog,
        mocker,
        init_db_instance,
    ):  # pylint:disable=unused-argument
        """Test command apply failure when failed to start a subprocess."""
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        # psycopg2.connect is mocked
        mocker.patch(
            "subprocess.Popen",
            side_effect=Exception(),
        )

        with tempfile.TemporaryDirectory() as tempdir:
            arg_procedure = os.path.join(tempdir, "procedure.json")
            procedures = procedure.single_pattern[0][0]

            with open(arg_procedure, "w", encoding="utf-8") as file:
                json.dump(procedures, file)
            sys.argv = ["cli.py", "request", "-p", arg_procedure]

            # act
            with pytest.raises(SystemExit) as excinfo:
                main()
            out, err = capfd.readouterr()

            # assert
            assert excinfo.value.code == 5
            # There is no standard output
            assert out == ""

            assert "[E40026]Failed to start subprocess." in err
            assert "[E40026]Failed to start subprocess." in caplog.text
