# Copyright (C) 2025 NEC Corporation.
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
import io
import json
import logging
import logging.config
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
from werkzeug import Response

from layoutapply.cli import LayoutApplyCommandLine, main
from layoutapply.common.logger import Logger
from layoutapply.const import Action, ExitCode, IdParameter, Result
from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.db import DbAccess
from layoutapply.main import run
from layoutapply.setting import LayoutApplyConfig, LayoutApplyLogConfig
from layoutapply.util import create_randomname
from tests.layoutapply.conftest import (
    DEVICE_INFO_URL,
    EXTENDED_PROCEDURE_URI,
    GET_INFORMATION_URI,
    HARDWARE_CONTROL_URI,
    OPERATION_URL,
    OS_BOOT_URL,
    POWER_OPERATION_URL,
    WORKFLOW_MANAGER_PORT,
)
from tests.layoutapply.test_data import checkvalid, procedure, sql

BASE_CONFIG = {
    "layout_apply": {"host": "0.0.0.0", "port": 8003, "request": {}},
    "db": {
        "dbname": "layoutapply",
        "user": "user01",
        "password": "P@ssw0rd",
        "host": "localhost",
        "port": 5435,
    },
    "get_information": {
        "host": "localhost",
        "port": 48889,
        "uri": "api/v1",
        "specs": {
            "poweroff": {
                "polling": {
                    "count": 5,
                    "interval": 1,
                },
            },
            "connect": {
                "polling": {
                    "count": 5,
                    "interval": 1,
                },
            },
            "disconnect": {
                "polling": {
                    "count": 5,
                    "interval": 1,
                },
            },
            "timeout": 10,
        },
    },
    "workflow_manager": {
        "host": "localhost",
        "port": 8008,
        "uri": "cdim/api/v1",
        "extended-procedure": {
            "retry": {
                "default": {
                    "interval": 5,
                    "max_count": 5,
                },
            },
            "polling": {
                "count": 5,
                "interval": 1,
            },
        },
        "timeout": 5,
    },
    "hardware_control": {
        "host": "localhost",
        "port": 48889,
        "uri": "cdim/api/v1",
        "disconnect": {
            "retry": {
                "targets": [
                    {
                        "status_code": 503,
                        "code": "ER005BAS001",
                        "interval": 5,
                        "max_count": 5,
                    },
                ],
                "default": {
                    "interval": 5,
                    "max_count": 5,
                },
            },
            "timeout": 10,
        },
        "isosboot": {
            "polling": {
                "count": 5,
                "interval": 1,
                "targets": [
                    {
                        "status_code": 204,
                    },
                ],
                "skip": [
                    {"status_code": 400, "code": "EF003BAS010"},
                ],
            },
            "request": {"timeout": 2},
            "timeout": 10,
        },
    },
    "migration_procedure_generator": {
        "host": "localhost",
        "port": 48889,
        "uri": "cdim/api/v1",
        "timeout": 30,
    },
    "configuration_manager": {
        "host": "localhost",
        "port": 48889,
        "uri": "cdim/api/v1",
        "timeout": 30,
    },
    "message_broker": {
        "host": "localhost",
        "port": 3500,
        "pubsub": "layout_apply_apply",
        "topic": "layout_apply_apply.completed",
    },
}


LOG_BASE_CONFIG = {
    "version": 1,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(message)s",
            "datefmt": "%Y/%m/%d %H:%M:%S.%f",
        }
    },
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "standard",
            "filename": "/var/log/cdim/app_layout_apply.log",
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
    "root": {
        "level": "INFO",
        "handlers": ["file"],
    },
}

SELECT_SQL = "SELECT * FROM applystatus WHERE applyid = %s"

get_list_assert_target = {
    "count": 9,
    "applyResults": [
        {
            "applyID": "000000001a",
            "status": "IN_PROGRESS",
            "startedAt": "2023-10-02T00:00:00Z",
            "procedures": {"procedures": "pre_test"},
        },
        {
            "status": "CANCELING",
            "applyID": "000000002b",
            "startedAt": "2023-10-01T23:59:59Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": True,
            "procedures": {"procedures": "pre_test"},
            "applyResult": [{"test": "test"}, {"test": "test"}],
            "rollbackProcedures": {"test": "test"},
        },
        {
            "status": "COMPLETED",
            "applyID": "000000003c",
            "procedures": {"procedures": "pre_test"},
            "applyResult": [{"test": "test"}, {"test": "test"}],
            "startedAt": "2023-10-02T00:00:00Z",
            "endedAt": "2023-10-02T12:23:59Z",
        },
        {
            "status": "FAILED",
            "applyID": "000000004d",
            "procedures": {"procedures": "pre_test"},
            "applyResult": [{"test": "test"}, {"test": "test"}],
            "startedAt": "2023-10-02T00:00:01Z",
            "endedAt": "2023-10-02T12:24:00Z",
        },
        {
            "status": "CANCELED",
            "applyID": "000000005e",
            "procedures": {"procedures": "pre_test"},
            "applyResult": [{"test": "test"}, {"test": "test"}],
            "rollbackProcedures": {"test": "test"},
            "startedAt": "2023-10-02T00:00:02Z",
            "endedAt": "2023-10-02T12:24:01Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": False,
        },
        {
            "status": "CANCELED",
            "applyID": "000000006f",
            "procedures": {"procedures": "pre_test"},
            "applyResult": [{"test": "test"}, {"test": "test"}],
            "rollbackProcedures": {"test": "test"},
            "startedAt": "2023-10-03T00:00:00Z",
            "endedAt": "2023-10-04T12:23:59Z",
            "canceledAt": "2023-10-03T12:00:00Z",
            "executeRollback": True,
            "rollbackStatus": "COMPLETED",
            "rollbackResult": [{"test": "test"}, {"test": "test"}],
            "rollbackStartedAt": "2023-10-03T12:20:00Z",
            "rollbackEndedAt": "2023-10-04T12:23:59Z",
        },
        {
            "status": "CANCELING",
            "applyID": "000000007a",
            "startedAt": "2023-10-01T23:59:59Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": True,
            "rollbackStartedAt": "2023-10-02T12:20:00Z",
            "procedures": {"procedures": "pre_test"},
            "applyResult": [{"test": "test"}, {"test": "test"}],
            "rollbackProcedures": {"test": "test"},
        },
        {
            "status": "CANCELING",
            "applyID": "000000008b",
            "startedAt": "2023-10-01T23:59:59Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": False,
            "procedures": {"procedures": "pre_test"},
            "applyResult": [{"test": "test"}, {"test": "test"}],
        },
        {
            "status": "SUSPENDED",
            "applyID": "000000009c",
            "procedures": {"procedures": "pre_test"},
            "applyResult": [{"test": "test"}, {"test": "test"}],
            "startedAt": "2023-10-02T00:00:01Z",
            "resumeProcedures": {"test": "pre_test"},
            "suspendedAt": "2024-01-02T12:23:00Z",
        },
    ],
}


@pytest.fixture
def get_list_assert_target_no_fields():
    # Create a deep copy to avoid modifying the original data.
    no_fields_target = copy.deepcopy(get_list_assert_target)

    # Delete the procedures of the IN_PROGRESS entry.
    for result_dict in no_fields_target["applyResults"]:
        if result_dict.get("status") == "IN_PROGRESS" and "procedures" in result_dict:
            del result_dict["procedures"]

    return no_fields_target


get_list_assert_target_default = {
    "count": 9,
    "applyResults": [
        {
            "applyID": "000000001a",
            "status": "IN_PROGRESS",
            "startedAt": "2023-10-02T00:00:00Z",
        },
        {
            "status": "CANCELING",
            "applyID": "000000002b",
            "startedAt": "2023-10-01T23:59:59Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": True,
        },
        {
            "status": "COMPLETED",
            "applyID": "000000003c",
            "startedAt": "2023-10-02T00:00:00Z",
            "endedAt": "2023-10-02T12:23:59Z",
        },
        {
            "status": "FAILED",
            "applyID": "000000004d",
            "startedAt": "2023-10-02T00:00:01Z",
            "endedAt": "2023-10-02T12:24:00Z",
        },
        {
            "status": "CANCELED",
            "applyID": "000000005e",
            "startedAt": "2023-10-02T00:00:02Z",
            "endedAt": "2023-10-02T12:24:01Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": False,
        },
        {
            "status": "CANCELED",
            "applyID": "000000006f",
            "startedAt": "2023-10-03T00:00:00Z",
            "endedAt": "2023-10-04T12:23:59Z",
            "canceledAt": "2023-10-03T12:00:00Z",
            "executeRollback": True,
            "rollbackStatus": "COMPLETED",
            "rollbackStartedAt": "2023-10-03T12:20:00Z",
            "rollbackEndedAt": "2023-10-04T12:23:59Z",
        },
        {
            "status": "CANCELING",
            "applyID": "000000007a",
            "startedAt": "2023-10-01T23:59:59Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": True,
            "rollbackStartedAt": "2023-10-02T12:20:00Z",
        },
        {
            "status": "CANCELING",
            "applyID": "000000008b",
            "startedAt": "2023-10-01T23:59:59Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": False,
        },
        {
            "status": "SUSPENDED",
            "applyID": "000000009c",
            "startedAt": "2023-10-02T00:00:01Z",
            "suspendedAt": "2024-01-02T12:23:00Z",
        },
    ],
}


def mock_run():
    cnt = 0
    while cnt < 3:
        sleep(1)
        cnt += 1
    return None


@pytest.fixture()
def get_applyID():
    return "".join([secrets.choice(string.hexdigits) for i in range(10)]).lower()


@pytest.mark.usefixtures("httpserver_listen_address")
class TestApplyCli:

    def insert_list_data(self, init_db_instance):
        """Data registration for apply status list"""
        id_list = []
        get_applystatus_list = [
            sql.get_list_insert_sql_1,
            sql.get_list_insert_sql_2,
            sql.get_list_insert_sql_3,
            sql.get_list_insert_sql_4,
            sql.get_list_insert_sql_5,
            sql.get_list_insert_sql_6,
            sql.get_list_insert_sql_7,
            sql.get_list_insert_sql_8,
            sql.get_list_insert_sql_9,
        ]
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            for insert_sql in get_applystatus_list:
                applyid = create_randomname(IdParameter.LENGTH)
                id_list.append(applyid)
                cursor.execute(query=insert_sql, vars=[applyid])
        init_db_instance.commit()
        return id_list

    @pytest.mark.usefixtures("hardwaremgr_fixture", "extended_procedure_fixture")
    def test_cmd_apply_success_when_migration_step_with_rel_path(self, capfd, mocker, init_db_instance, get_applyID):
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
                details = row.get("applyresult")
                assert details is not None
                assert len(details) == len(procedures["procedures"])
                host = config.hardware_control.get("host")
                port = config.hardware_control.get("port")
                uri = config.hardware_control.get("uri")
                for proc in procedures["procedures"]:
                    # Search for items corresponding to the migration procedure from
                    # result details using operationID as a condition
                    detail = [i for i in details if i["operationID"] == proc["operationID"]][0]
                    assert proc["operationID"] == detail["operationID"]
                    assert "COMPLETED" == detail["status"]
                    # Check the URI, etc. of the hardware control API

                    # Review the mockup method with hardwaremgr_fixture as well
                    match proc["operation"]:
                        case "connect":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert "queryParameter" not in detail
                            assert detail["requestBody"] == {
                                "action": "connect",
                                "deviceID": proc["targetDeviceID"],
                            }
                            assert 200 == detail["statusCode"]

                        case "disconnect":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {
                                "action": "disconnect",
                                "deviceID": proc["targetDeviceID"],
                            }
                            assert "queryParameter" not in detail
                            assert 200 == detail["statusCode"]

                        case "boot":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {"action": "on"}
                            assert "queryParameter" not in detail
                            assert 200 == detail["statusCode"]
                            is_os_boot_detail = detail["isOSBoot"]
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OS_BOOT_URL}",
                                is_os_boot_detail["uri"],
                            )
                            assert "GET" == is_os_boot_detail["method"]
                            assert "queryParameter" in is_os_boot_detail
                            assert is_os_boot_detail["queryParameter"] == {"timeOut": 2}
                            assert is_os_boot_detail["statusCode"] == 200

                        case "shutdown":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert {"action": "off"} == detail["requestBody"]
                            assert detail["getInformation"]["responseBody"] == {"powerState": "Off"}
                            assert "queryParameter" not in detail
                            assert 200 == detail["statusCode"]
                        case "start":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{WORKFLOW_MANAGER_PORT}\/{uri}\/{EXTENDED_PROCEDURE_URI}",
                                detail["uri"],
                            )
                            assert "POST" == detail["method"]
                            assert "start" == detail["requestBody"].get("operation")
                            assert "queryParameter" not in detail
                            assert 202 == detail["statusCode"]
                        case "stop":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{WORKFLOW_MANAGER_PORT}\/{uri}\/{EXTENDED_PROCEDURE_URI}",
                                detail["uri"],
                            )
                            assert "POST" == detail["method"]
                            assert "stop" == detail["requestBody"].get("operation")
                            assert "queryParameter" not in detail
                            assert 202 == detail["statusCode"]

        if procces_mock.return_value.is_alive():
            procces_mock.return_value.terminate()
            procces_mock.return_value.join()

    @pytest.mark.usefixtures("hardwaremgr_fixture")
    def test_cmd_apply_success_when_migration_step_empty(self, capfd, mocker, init_db_instance, get_applyID):
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
                details = row.get("applyresult")
                assert details == []
                assert len(details) == len(procedures["procedures"])
        if procces_mock.return_value.is_alive():
            procces_mock.return_value.terminate()
            procces_mock.return_value.join()

    def test_cmd_apply_failure_when_migration_step_missing(self, capfd):
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
    def test_cmd_apply_failure_when_failed_to_initialize_logger(self, mocker, capfd, update_config, docker_services):
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
        mocker,
        init_db_instance,
    ):
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
        mocker,
        init_db_instance,
    ):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        # Ensure that  SUSPENDED data exists before the test
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_resumed_get_target_sql_4, vars=[applyid])
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
        mocker,
        init_db_instance,
    ):
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
        mocker,
        init_db_instance,
    ):
        # Ensure no active data exists before the test
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_delete_target_sql_9, vars=[applyid])
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

    def test_cmd_apply_failure_when_failed_db_connection(self, capfd, mocker, init_db_instance):
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
    ):
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

    @pytest.mark.parametrize(
        "args, status",
        [
            (["cancel", "--apply-id"], Result.IN_PROGRESS),
            (["cancel", "--apply-id"], Result.CANCELING),
        ],
    )
    def test_cmd_cancel_cancelable_by_command(self, mocker, init_db_instance, args, status, capfd):
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
        query_str = f"INSERT INTO applystatus (applyid, status, processid, executioncommand, processstartedat) VALUES ('{apply_id}', '{status}', {proc.pid}, '{"".join(execution_cmd)}', '{process_start}')"
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=query_str)
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

    def test_cmd_cancel_registered_in_db_when_auto_rollback_option_added(self, mocker, init_db_instance):
        # arrange
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        # Register the execution process in the database.
        proc_obj = psutil.Process(proc.pid)
        execution_cmd = proc_obj.cmdline()
        process_start = str(proc_obj.create_time())
        apply_id = create_randomname(IdParameter.LENGTH)
        query_str = f"INSERT INTO applystatus (applyid, status, processid, executioncommand, processstartedat) VALUES ('{apply_id}', '{Result.IN_PROGRESS}', {proc.pid}, '{"".join(execution_cmd)}', '{process_start}')"
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=query_str)
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
    def test_cmd_cancel_success_when_specified_canceled_config_id(self, mocker, init_db_instance, args, capfd):
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

    def test_cmd_cancel_failure_when_specified_completed_config_id(self, mocker, init_db_instance, capfd):
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
    def test_cmd_cancel_failure_when_not_exist_id_specified(self, mocker, init_db_instance, args, capfd):
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

    def test_cmd_cancel_failure_changes_to_failure_when_mismatched_subprocess_info(
        self, mocker, init_db_instance, capfd
    ):
        # Ensure no active data exists before the test

        assert_print = "[E40028]Since the process with the specified ID does not exist, change the status from IN_PROGRESS to FAILED.\nstatus=FAILED\n"
        # arrange
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        # Register data that does not match the execution process in the database.
        apply_id = create_randomname(IdParameter.LENGTH)
        query_str = f"INSERT INTO applystatus (applyid, status, processid, executioncommand, processstartedat) VALUES ('{apply_id}', '{Result.IN_PROGRESS}', {proc.pid}, 'dummy', '0')"
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
        # arrange

        assert_print = "[E40028]Since the process with the specified ID does not exist, change the status from IN_PROGRESS to FAILED.\nstatus=FAILED\n"
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        # Register the execution process in the database.
        apply_id = create_randomname(IdParameter.LENGTH)
        query_str = f"INSERT INTO applystatus (applyid, status, processid, executioncommand, processstartedat) VALUES ('{apply_id}', '{Result.IN_PROGRESS}', {proc.pid}, 'dummy', '0')"
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

    @pytest.mark.parametrize(
        "args",
        [
            (["cancel", "--apply-id"]),
        ],
    )
    def test_cmd_cancel_failure_when_no_failure_on_process_in_canceled_with_rollback_in_progress(
        self, mocker, init_db_instance, args, capfd
    ):
        # arrange

        assert_print = "[E40022]This layoutapply has already executed.\n"
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        # Register the execution process in the database.
        proc_obj = psutil.Process(proc.pid)
        execution_cmd = proc_obj.cmdline()
        process_start = str(proc_obj.create_time())
        apply_id = create_randomname(IdParameter.LENGTH)
        query_str = f"INSERT INTO applystatus (applyid, status, rollbackstatus, processid, executioncommand, processstartedat) VALUES ('{apply_id}', '{Result.CANCELED}', '{Result.IN_PROGRESS}', {proc.pid}, '{"".join(execution_cmd)}', '{process_start}')"
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=query_str)
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
        # arrange
        assert_print = "[E40028]Since the process with the specified ID does not exist, change the rollbackStatus from IN_PROGRESS to FAILED.\nstatus=CANCELED\nrollbackStatus=FAILED\n"
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        # Register the execution process in the database.
        apply_id = create_randomname(IdParameter.LENGTH)
        query_str = f"INSERT INTO applystatus (applyid, status, rollbackstatus, processid, executioncommand, processstartedat) VALUES ('{apply_id}', '{Result.CANCELED}', '{Result.IN_PROGRESS}', {proc.pid}, 'dummy', '0')"
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
        # There is no standard output
        assert out == ""
        # standard error output displays the error details and the changed reflection status.
        assert err == assert_print

        if proc.is_alive():
            proc.terminate()
            proc.join()

    def test_cmd_cancel_rollback_suspended_to_failed_possible(self, init_db_instance, capfd):
        # Data adjustment before testing.
        apply_id = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query=f"INSERT INTO applyStatus (applyID,status,rollbackstatus,startedAt) VALUES('{apply_id}','{Result.CANCELED}','{Result.SUSPENDED}',null)"
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

    @pytest.mark.parametrize(
        "args",
        [
            (
                [
                    "--help",
                ]
            ),
            (
                [
                    "-h",
                ]
            ),
        ],
    )
    def test_common_usage_displayed_when_help_specified(
        self,
        args,
        capfd,
    ):
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0
        out, _ = capfd.readouterr()

        # help message is displayed in the standard output
        assert "usage" in out
        assert "positional arguments" in out
        assert "request" in out
        assert "cancel" in out
        assert "get" in out
        assert "delete" in out
        assert "resume" in out
        assert "options:" in out
        assert "-h" in out
        assert "--help" in out

    def test_common_usage_displayed_when_no_subcommand_specified(
        self,
        capfd,
    ):
        sys.argv = ["cli.py"]
        main()
        out, _ = capfd.readouterr()

        # help message is displayed in the standard output
        assert "usage" in out
        assert "positional arguments" in out
        assert "request" in out
        assert "cancel" in out
        assert "get" in out
        assert "delete" in out
        assert "resume" in out
        assert "options:" in out
        assert "-h" in out
        assert "--help" in out

    def test_cmd_get_failure_when_failed_file_output(self, mocker, init_db_instance, capfd, caplog):
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        # Ensure that IN_PROGRESS data exists before the test
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
            init_db_instance.commit()
        # error occurs during file output.
        mocker.patch("json.dump", side_effect=Exception)

        with tempfile.TemporaryDirectory() as tempdir:
            arg_out = os.path.join(tempdir, "result.json")
            args = ["get", "--apply-id", applyid, "--output", arg_out]
            # act
            sys.argv = ["cli.py", *args]
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code == 13
            # assert
            _, err = capfd.readouterr()

            # error message is displayed in the standard error output.
            assert err == "[E40006]Failed to output file.\n"
            # error log contains the error message.
            assert "[E40006]Failed to output file." in caplog.text

    def test_cmd_get_failure_when_directory_specified(self, mocker, init_db_instance, capfd):
        # arrange

        for addition_path in ["", os.path.sep]:
            with tempfile.TemporaryDirectory() as tempdir:
                arg_out = tempdir + addition_path
                args = ["get", "--apply-id", "123456789e", "--output", arg_out]
                # act
                sys.argv = ["cli.py", *args]
                with pytest.raises(SystemExit) as excinfo:
                    main()
                assert excinfo.value.code == 1
                # assert
                out, err = capfd.readouterr()
                assert out == ""
                # error message is displayed in the standard error output.
                assert err == "[E40001]Out path points to a directory.\n"

    @pytest.mark.parametrize("args", [["get", "--apply-id", "123456789a"]])
    def test_cmd_get_failure_when_failed_db_connection(self, args, mocker, capfd):
        mocker.patch.object(DbAccess, "get_apply_status", side_effect=psycopg2.OperationalError)
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 10
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""

        assert "[E40018]Could not connect to ApplyStatusDB." in err

    @pytest.mark.parametrize("args", [["get", "--apply-id", "123456789a"]])
    def test_cmd_get_failure_when_query_failure_occurred(self, args, mocker, capfd, caplog):
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
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 11
        out, err = capfd.readouterr()

        # There is no standard output
        assert out == ""

        assert "[E40019]Query failed." in err
        assert "[E40019]Query failed." in caplog.text

    @pytest.mark.parametrize("args", [["get", "--apply-id", "a0b1c2d3ef"]])
    def test_cmd_get_failure_when_specified_config_id_not_found(self, args, mocker, init_db_instance, capfd, caplog):
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        # arrange

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 12
        out, err = capfd.readouterr()

        # There is no standard output
        assert out == ""

        assert err == "[E40020]Specified a0b1c2d3ef is not found.\n"
        assert "[E40020]Specified a0b1c2d3ef is not found." in caplog.text

    @pytest.mark.parametrize(
        ("insert_sql", "assert_target"),
        [
            (
                sql.get_list_insert_sql_1,
                {
                    "status": "IN_PROGRESS",
                    "applyID": "000000001a",
                    "startedAt": "2023-10-02T00:00:00Z",
                    "procedures": {"procedures": "pre_test"},
                },
            ),
            (
                sql.get_list_insert_sql_2,
                {
                    "status": "CANCELING",
                    "applyID": "000000002b",
                    "startedAt": "2023-10-01T23:59:59Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": True,
                    "rollbackProcedures": {"test": "test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "procedures": {"procedures": "pre_test"},
                },
            ),
            (
                sql.get_list_insert_sql_3,
                {
                    "status": "COMPLETED",
                    "applyID": "000000003c",
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "startedAt": "2023-10-02T00:00:00Z",
                    "endedAt": "2023-10-02T12:23:59Z",
                },
            ),
            (
                sql.get_list_insert_sql_4,
                {
                    "status": "FAILED",
                    "applyID": "000000004d",
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "startedAt": "2023-10-02T00:00:01Z",
                    "endedAt": "2023-10-02T12:24:00Z",
                },
            ),
            (
                sql.get_list_insert_sql_5,
                {
                    "status": "CANCELED",
                    "applyID": "000000005e",
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"test": "test"},
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ),
            (
                sql.get_list_insert_sql_6,
                {
                    "status": "CANCELED",
                    "applyID": "000000006f",
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"test": "test"},
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                    "rollbackStatus": "COMPLETED",
                    "rollbackResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackStartedAt": "2023-10-03T12:20:00Z",
                    "rollbackEndedAt": "2023-10-04T12:23:59Z",
                },
            ),
            (
                sql.get_list_insert_sql_7,
                {
                    "status": "CANCELING",
                    "applyID": "000000007a",
                    "startedAt": "2023-10-01T23:59:59Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": True,
                    "rollbackStartedAt": "2023-10-02T12:20:00Z",
                    "rollbackProcedures": {"test": "test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "procedures": {"procedures": "pre_test"},
                },
            ),
            (
                sql.get_list_insert_sql_8,
                {
                    "status": "CANCELING",
                    "applyID": "000000008b",
                    "startedAt": "2023-10-01T23:59:59Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "procedures": {"procedures": "pre_test"},
                },
            ),
        ],
    )
    def test_cmd_get_can_output_file(self, mocker, init_db_instance, insert_sql, assert_target, capfd):
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()

        assert_target["applyID"] = applyid
        args = ["get", "--apply-id", applyid, "--output", "applystatus.json"]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()

        # assert
        # standard output is being displayed.
        assert out == "Success.\n"
        # There is no standard error output.
        assert err == ""
        out_path = args[4]
        assert os.path.exists(out_path)
        with open(out_path, "r", encoding="utf-8") as file:
            assert assert_target == json.load(file)
            try:
                os.remove(out_path)
            except Exception:
                pass

    def test_cmd_get_success_when_status_is_in_progress(self, mocker, init_db_instance, capfd):
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
            init_db_instance.commit()
        assert_target = {
            "status": "IN_PROGRESS",
            "applyID": "000000001a",
            "startedAt": "2023-10-02T00:00:00Z",
            "procedures": {"procedures": "pre_test"},
        }
        assert_target["applyID"] = applyid

        args = ["get", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays the information about the reflection status of the configuration proposal specified by the applyID.
        assert json.loads(out) == assert_target
        # There is no standard error output.
        assert err == ""

    def test_cmd_get_success_when_procedure_valid(self, init_db_instance, capfd):
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_valid_insert_sql, vars=[applyid])
            init_db_instance.commit()
        assert_target = {
            "status": "COMPLETED",
            "applyID": "999999999a",
            "procedures": [],
            "applyResult": [],
            "startedAt": "2023-10-02T00:00:00Z",
            "endedAt": "2023-10-02T12:23:59Z",
        }
        assert_target["applyID"] = applyid

        args = ["get", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays the information about the reflection status of the configuration proposal specified by the applyID.
        assert json.loads(out) == assert_target
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "--apply-id", "a21bc21587", "b51b1215ce"]),  # multi ids
            (["get", "--apply-id"]),  # no id
            (["get", "a21bc21587"]),  # no id option
            (["get", "--apply-ids", "a21bc21587"]),  # invalid option
            (["--apply-id", "a21bc21587"]),  # no subcommand
            (["gets", "--apply-id", "a21bc21587"]),  # invalid subcommand
            (["a21bc21587"]),  # no id option and subcommand
            (["get", "--apply-id"]),  # no id
            (["get", "--apply-id", "a21bc21587", "--outputs"]),  # invalid output
            (["get", "--apply-id", "a21bc21587", "--utput"]),  # invalid output
            (["get", "--apply-id", "a21bc21587", "-p"]),  # invalid output
            (["get", "--apply-id", "a21bc21587", "-n"]),  # invalid output
            (["get", "--apply-id", "a21bc21587", "-oo", "test"]),  # invalid output
        ],
    )
    def test_cmd_get_usage_displayed(self, args, capfd):
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit):
            main()
        _, err = capfd.readouterr()
        # An error message is displayed.
        assert "usage:" in err

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "--apply-id", "g21bc21587"]),  # invalid character
            (["get", "--apply-id", "ABCDEF0123"]),  # invalid character type
            (["get", "--apply-id", "あBCDEF0123"]),  # invalid character type
            (["get", "--apply-id", "a21bc2158"]),  # invalid length
            (["get", "--apply-id", "a21bc215871"]),  # invalid length
            (["get", "--apply-id", "a"]),  # invalid length
        ],
    )
    def test_cmd_get_failure_when_invalid_config_id(self, args, capfd):
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out == ""
        assert err.startswith("[E40001]")

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "--apply-id", "123456789a", "-f", "procedures,applyResult"]),
            (["get", "--apply-id", "123456789a", "--fields", "procedures,applyResult"]),
            (["get", "--apply-id", "123456789a", "-s", "TEST"]),
            (["get", "--apply-id", "123456789a", "--status", "TEST"]),
            (["get", "--apply-id", "123456789a", "-ss", "2023-11-22T11:11:11Z"]),
            (
                [
                    "get",
                    "--apply-id",
                    "123456789a",
                    "--started-at-since",
                    "2023-11-22T11:11:11Z",
                ]
            ),
            (["get", "--apply-id", "123456789a", "-su", "2023-11-22T11:11:11Z"]),
            (
                [
                    "get",
                    "--apply-id",
                    "123456789a",
                    "--started-at-until",
                    "2023-11-22T11:11:11Z",
                ]
            ),
            (["get", "--apply-id", "123456789a", "-es", "2023-11-22T11:11:11Z"]),
            (
                [
                    "get",
                    "--apply-id",
                    "123456789a",
                    "--ended-at-since",
                    "2023-11-22T11:11:11Z",
                ]
            ),
            (["get", "--apply-id", "123456789a", "-eu", "2023-11-22T11:11:11Z"]),
            (
                [
                    "get",
                    "--apply-id",
                    "123456789a",
                    "--ended-at-until",
                    "2023-11-22T11:11:11Z",
                ]
            ),
            (
                [
                    "get",
                    "--apply-id",
                    "123456789a",
                    "-s",
                    "TEST",
                    "-ss",
                    "2023-11-22T11:11:11Z",
                    "-su",
                    "2023-11-22T11:11:11Z",
                    "-es",
                    "2023-11-22T11:11:11Z",
                    "-eu",
                    "2023-11-22T11:11:11Z",
                ]
            ),
            (
                [
                    "get",
                    "--apply-id",
                    "123456789a",
                    "--status",
                    "TEST",
                    "--started-at-since",
                    "2023-11-22T11:11:11Z",
                    "--started-at-until",
                    "2023-11-22T11:11:11Z",
                    "--ended-at-since",
                    "2023-11-22T11:11:11Z",
                    "--ended-at-until",
                    "2023-11-22T11:11:11Z",
                ]
            ),
            (["get", "--apply-id", "123456789a", "--sort-by", "startedAt"]),
            (["get", "--apply-id", "123456789a", "--order-by", "desc"]),
            (["get", "--apply-id", "123456789a", "--limit", "1"]),
            (["get", "--apply-id", "123456789a", "--offset", "0"]),
        ],
    )
    def test_cmd_get_failure_when_id_and_invalid_option(self, args, capfd):
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out == ""
        assert (
            "[E40001]Not allowed with argument --fields, --status, --started-at-since, --started-at-until, --ended-at-since, --ended-at-until, --sort-by, --order-by, --limit, --offset."
        ) in err

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "--help"]),
            (["get", "-h"]),
        ],
    )
    def test_cmd_get_help_displayed(self, args, capfd):
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit):
            main()
        out, err = capfd.readouterr()

        assert_out = out.replace("\n", "")
        assert_out = re.sub("\s+", " ", assert_out)
        assert err == ""
        assert "usage:" in assert_out
        assert "get" in assert_out
        assert "[-h]" in assert_out
        assert "--apply-id" in assert_out
        assert "APPLY_ID" in assert_out
        assert "[-o OUTPUT_FILE]" in assert_out
        assert "[-f ITEM,ITEM....ITEM]" in assert_out
        assert "-h, --help" in assert_out
        assert "show this help message and exit" in assert_out
        assert "--apply-id" in assert_out
        assert "APPLY_ID" in assert_out
        assert "get ID as a string. If not specified, get all apply status." in assert_out
        assert (
            "specify the items to be included in the return information. If not specified, that items are not included."
            in assert_out
        )
        assert (
            "not allowed with argument --fields, --status, --started-at-since, --started-at-until, --ended-at- since, --ended-at-until, --sort-by, --order-by, --limit, --offset."
            in assert_out
        )
        assert (
            "specify the status for return information. set [IN_PROGRESS | COMPLETED | FAILED | CANCELING | CANCELED | SUSPENDED]"
            in assert_out
        )
        assert "-s," in assert_out
        assert "--status STATUS" in assert_out
        assert "specify the startpoint of started time for return information." in assert_out
        assert "-ss," in assert_out
        assert "--started-at-since STARTED_AT_SINCE" in assert_out
        assert "specify the endpoint of started time for return information." in assert_out
        assert "-su," in assert_out
        assert "--started-at-until STARTED_AT_UNTIL" in assert_out
        assert "specify the startpoint of ended time for return information." in assert_out
        assert "-es," in assert_out
        assert "--ended-at-since ENDED_AT_SINCE" in assert_out
        assert "specify the endpoint of ended time for return information." in assert_out
        assert "-eu," in assert_out
        assert "--ended-at-until ENDED_AT_UNTIL" in assert_out
        assert "--order-by ORDER_BY" in assert_out
        assert "--sort-by SORT_BY" in assert_out
        assert "--limit NUMBER" in assert_out
        assert "--offset NUMBER" in assert_out
        assert "-o," in assert_out
        assert "--output OUTPUT_FILE" in assert_out

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "-ss", "2023"]),
            (["get", "-ss", "2023-11"]),
            (["get", "-ss", "20231122"]),
            (["get", "-ss", "2023-11-22T11"]),
            (["get", "-ss", "2023-11-22T1122"]),
            (["get", "-ss", "2023-11-22T11:22"]),
            (["get", "-ss", "2023-11-22T112233.11"]),
            (["get", "-ss", "2023-11-22T11:22:33.11"]),
            (["get", "-ss", "20231122T11:11:11Z"]),
            (["get", "-ss", "2023-11-22"]),
            (["get", "-ss", "20231122T111111Z"]),
            (["get", "-ss", "2023-11-22 11:11:11"]),
            (["get", "-su", "20231122T11:11:11Z"]),
            (["get", "-su", "2023-11-22"]),
            (["get", "-su", "20231122T111111Z"]),
            (["get", "-su", "2023-11-22 11:11:11"]),
            (["get", "--ended-at-since", "20231122T11:11:11Z"]),
            (["get", "-es", "2023-11-22"]),
            (["get", "-es", "20231122T111111Z"]),
            (["get", "-es", "2023-11-22 11:11:11"]),
            (["get", "--ended-at-until", "20231122T11:11:11Z"]),
            (["get", "-eu", "2023-11-22"]),
            (["get", "-eu", "20231122T111111Z"]),
            (["get", "-eu", "2023-11-22 11:11:11"]),
            (["get", "-ss", "2023-11-22T11:11:11+09:00"]),
            (["get", "-ss", "2023-11-22T11:11:11-08:00"]),
            (["get", "-ss", "2023-11-22T11:11:11+0555"]),
            (["get", "-ss", "2023-11-22T11:11:11-11"]),
        ],
    )
    def test_cmd_get_all_success_when_valid_start_and_end_time_specified(self, mocker, init_db_instance, args, capfd):
        # Data adjustment before testing.
        assert_target = {
            "totalCount": 0,
            "count": 0,
            "applyResults": [],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == assert_target
        # There is no standard error output.
        assert err == ""

    def test_cmd_get_all_failure_when_failed_file_output(self, mocker, init_db_instance, capfd, caplog):
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.ERROR)
        # arrange
        # error occurs during file output.
        mocker.patch("json.dump", side_effect=Exception)

        with tempfile.TemporaryDirectory() as tempdir:
            arg_out = os.path.join(tempdir, "result.json")
            args = ["get", "--output", arg_out]
            # act
            sys.argv = ["cli.py", *args]
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code == 13
            # assert
            _, err = capfd.readouterr()
            # error message is displayed in the standard error output.
            assert err == "[E40006]Failed to output file.\n"
            # error log contains the error message.
            assert "[E40006]Failed to output file." in caplog.text

    def test_cmd_get_all_failure_when_directory_specified(self, mocker, init_db_instance, capfd):
        # arrange

        for addition_path in ["", os.path.sep]:
            with tempfile.TemporaryDirectory() as tempdir:
                arg_out = tempdir + addition_path
                args = ["get", "--output", arg_out]
                # act
                sys.argv = ["cli.py", *args]
                with pytest.raises(SystemExit) as excinfo:
                    main()
                assert excinfo.value.code == 1
                # assert
                out, err = capfd.readouterr()
                assert out == ""
                # error message is displayed in the standard error output.
                assert err == "[E40001]Out path points to a directory.\n"

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "-s", "IN_PROGRES"]),
            (["get", "--status", "IN_PROGRES"]),
            (["get", "--sort-by", "status"]),
            (["get", "--order-by", "new"]),
            (["get", "--order-by", "dsc"]),
            (["get", "--limit", "0"]),
            (["get", "--limit", "-1"]),
            (["get", "--offset", "-1"]),
        ],
    )
    def test_cmd_get_failure_when_specified_id_is_invalid(self, args, capfd):
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out == ""
        assert "[E40001]" in err

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "--started-at-since", "2023-11-2211:11:11Z"]),
            (["get", "-ss", "T11:11:11Z"]),
            (["get", "-ss", "2023/11/22T11:11:11Z"]),
            (["get", "--started-at-until", "2023-11-2211:11:11Z"]),
            (["get", "-su", "T11:11:11Z"]),
            (["get", "-su", "2023/11/22T11:11:11Z"]),
            (["get", "-es", "2023-11-2211:11:11Z"]),
            (["get", "-es", "T11:11:11Z"]),
            (["get", "-es", "2023/11/22T11:11:11Z"]),
            (["get", "-eu", "2023-11-2211:11:11Z"]),
            (["get", "-eu", "T11:11:11Z"]),
            (["get", "-eu", "2023/11/22T11:11:11Z"]),
            (["get", "-eu", "2023-11-22T11:11:11Z+09:00"]),
            (["get", "-eu", "0000-11-22T11:11:11Z+09:00"]),
        ],
    )
    def test_cmd_get_all_failure_when_invalid_start_and_end_time_specified(self, args, capfd):
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out == ""
        assert err.startswith("[E40001]")

    @pytest.mark.parametrize("args", [["get"]])
    def test_cmd_get_all_failure_when_failed_db_connection(self, args, mocker, capfd):
        mocker.patch.object(DbAccess, "get_apply_status_list", side_effect=psycopg2.OperationalError)
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 10
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""

        assert "[E40018]Could not connect to ApplyStatusDB." in err

    @pytest.mark.parametrize("args", [["get"]])
    def test_cmd_get_all_failure_when_query_failure_occurred(self, args, mocker, capfd, caplog):
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.ERROR)

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
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 11
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""

        assert "[E40019]Query failed." in err
        assert "[E40019]Query failed." in caplog.text

    def test_cmd_get_all_success_when_no_fields_and_out_file(self, mocker, init_db_instance, capfd):
        # Data adjustment before testing.
        id_list = self.insert_list_data(init_db_instance)
        for i, result_dict in enumerate(get_list_assert_target_default["applyResults"]):
            result_dict["applyID"] = id_list[i]

        args = ["get", "--output", "applystatus_list.json"]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()

        # assert
        # standard output is being displayed.
        assert out == "Success.\n"
        # There is no standard error output.
        assert err == ""
        out_path = args[2]
        assert os.path.exists(out_path)
        with open(out_path, "r", encoding="utf-8") as file:
            output = json.load(file)
            assert get_list_assert_target_default["count"] == output["count"]
            for apply in output["applyResults"]:
                assert apply in get_list_assert_target_default["applyResults"]

            try:
                os.remove(out_path)
            except Exception:
                pass

    def test_cmd_get_all_success_when_no_fields_and_no_out_file(self, mocker, init_db_instance, capfd):
        # arrange
        id_list = self.insert_list_data(init_db_instance)
        for i, result_dict in enumerate(get_list_assert_target_default["applyResults"]):
            result_dict["applyID"] = id_list[i]

        args = ["get"]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        a = json.loads(out)
        for apply in a["applyResults"]:
            assert apply in get_list_assert_target_default["applyResults"]
        # There is no standard error output.
        assert err == ""

    def test_cmd_get_all_success_when_file_output_made(self, mocker, init_db_instance, capfd):
        # Data adjustment before testing.
        id_list = self.insert_list_data(init_db_instance)
        for i, result_dict in enumerate(get_list_assert_target["applyResults"]):
            result_dict["applyID"] = id_list[i]
        args = [
            "get",
            "--fields",
            "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
            "--output",
            "applystatus_list.json",
        ]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()

        # assert
        # standard output is being displayed.
        assert out == "Success.\n"
        # There is no standard error output.
        assert err == ""

        out_path = args[4]
        assert os.path.exists(out_path)
        with open(out_path, "r", encoding="utf-8") as file:
            output = json.load(file)
            assert get_list_assert_target["count"] == output["count"]
            for apply in output["applyResults"]:
                assert apply in get_list_assert_target["applyResults"]

            try:
                os.remove(out_path)
            except Exception:
                pass

    def test_cmd_get_all_success_when_no_file_output(self, mocker, init_db_instance, capfd):
        # arrange
        id_list = self.insert_list_data(init_db_instance)
        for i, result_dict in enumerate(get_list_assert_target["applyResults"]):
            result_dict["applyID"] = id_list[i]
        args = [
            "get",
            "--fields",
            "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
        ]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        a = json.loads(out)
        for apply in a["applyResults"]:
            assert apply in get_list_assert_target["applyResults"]
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize("args", [["get"]])
    def test_cmd_get_all_success_when_no_results_fetched(self, mocker, init_db_instance, args, capfd):
        assert_target = {
            "totalCount": 0,
            "count": 0,
            "applyResults": [],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == assert_target
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            (["gets", "a21bc21587"]),  # invalid subcommand
            (["get", "--outputs"]),  # invalid output
            (["get", "--utput"]),  # invalid output
            (["get", "-p"]),  # invalid output
            (["get", "-n"]),  # invalid output
            (["get", "-oo", "test"]),  # invalid output
            (["get", "--status"]),  # status option has no value
            (["get", "--stasus"]),  # status is invalid
            (["get", "--tatus"]),  # status is invalid
            (["get", "-r"]),  # status is invalid
            (["get", "-t"]),  # status is invalid
            (["get", "--started-at-since"]),  # started-at-since option has no value
            (["get", "--started-at-sinci"]),  # started-at-since is invalid
            (["get", "--tarted-at-since"]),  # started-at-since is invalid
            (["get", "-sss", "test"]),  # ss is invalid
            (["get", "--started-at-until"]),  # started-at-until option has no value
            (["get", "--started-at-untii"]),  # started-at-until is invalid
            (["get", "--tarted-at-until"]),  # started-at-until is invalid
            (["get", "-sus", "test"]),  # su is invalid
            (["get", "--ended-at-since"]),  # ended-at-since option has no value
            (["get", "--ended-at-sinci"]),  # ended-at-since is invalid
            (["get", "--nded-at-since"]),  # ended-at-since is invalid
            (["get", "-ess", "test"]),  # es is invalid
            (["get", "--ended-at-until"]),  # ended-at-until option has no value
            (["get", "--ended-at-untii"]),  # ended-at-until is invalid
            (["get", "--nded-at-until"]),  # ended-at-until is invalid
            (["get", "-eus", "test"]),  # eu is invalid
            (["get", "-ob", "endedat"]),  # order-by is invalid
            (["get", "--orderBy", "endedat"]),  # order-by is invalid
            (["get", "-sb", "asc"]),  # sort-by is invalid
            (["get", "--sortBy", "asc"]),  # sort-by is invalid
            (["get", "-l", "5"]),  # limit is invalid
            (["get", "--limits", "5"]),  # limit is invalid
            (["get", "-of", "2"]),  # offset is invalid
            (["get", "-ofset", "2"]),  # offset is invalid
        ],
    )
    def test_cmd_get_all_usage_displayed_when_invalid_option(self, args, capfd):
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit):
            main()
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out in "usage:"
        assert "usage:" in err

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "--fields", ","]),  # empty
            (["get", "--fields", "procedure"]),  # invalid value
            (["get", "--fields", "applyresult"]),  # invalid value
            (["get", "--fields", "rollbackProcedure"]),  # invalid value
            (["get", "--fields", "rollbackresult"]),  # invalid value
            (
                [
                    "get",
                    "--fields",
                    "procedures/applyResult",
                ]
            ),  # invalid sperator
            (
                [
                    "get",
                    "--fields",
                    "procedure,sapplyResult",
                ]
            ),  # invalid sperator
        ],
    )
    def test_cmd_get_all_failure_when_invalid_fields(self, args, capfd):
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out == ""
        assert err.startswith("[E40001]")

    @pytest.mark.parametrize(
        ("assert_target", "insert_sql"),
        [
            (
                {
                    "status": "IN_PROGRESS",
                    "applyID": "300000004d",
                    "procedures": {"procedures": "pre_test"},
                    "startedAt": "2023-10-02T00:00:00Z",
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "resumedAt": "2023-10-03T12:23:59Z",
                    "resumeProcedures": {"test": "pre_test"},
                },
                sql.insert_resumed_get_target_sql_1,
            ),
            (
                {
                    "status": "CANCELING",
                    "applyID": "300000005e",
                    "procedures": {"procedures": "pre_test"},
                    "startedAt": "2023-10-02T00:00:00Z",
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "canceledAt": "2023-10-02T00:00:01Z",
                    "executeRollback": True,
                    "rollbackResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackStartedAt": "2023-10-02T00:00:02Z",
                    "resumeResult": [{"test": "test"}],
                    "resumedAt": "2023-10-03T12:23:59Z",
                    "resumeProcedures": {"test": "pre_test"},
                },
                sql.insert_resumed_get_target_sql_2,
            ),
            (
                {
                    "status": "IN_PROGRESS",
                    "applyID": "300000004d",
                    "procedures": {"procedures": "pre_test"},
                    "startedAt": "2023-10-02T00:00:00Z",
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "resumeResult": [{"test": "test"}],
                    "resumedAt": "2023-10-03T12:23:59Z",
                    "resumeProcedures": {"test": "pre_test"},
                },
                sql.insert_resumed_get_target_sql_5,
            ),
        ],
    )
    def test_cmd_get_success_when_state_in_progress_or_canceling(
        self, mocker, init_db_instance, assert_target, insert_sql, capfd
    ):
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()

        assert_target["applyID"] = applyid
        args = ["get", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays the information regarding
        # reflection status of the configuration proposal specified by the applyID.
        assert json.loads(out) == assert_target
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                "-s",
                "CANCELED",
                "-ss",
                "2023-10-02T00:00:03Z",
                "-su",
                "2023-10-03T00:00:01Z",
                "-es",
                "2023-10-02T12:24:01Z",
                "-eu",
                "2023-10-04T12:24:00Z",
            ]
        ],
    )
    def test_cmd_get_all_success_when_start_date_only_not_in_range(self, mocker, init_db_instance, args, capfd):
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_1])
            init_db_instance.commit()
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid_2])
            init_db_instance.commit()

        # "applyID": "000000006f"（target）"applyID": "000000005e"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": applyid_2,
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"test": "test"},
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                    "rollbackStatus": "COMPLETED",
                    "rollbackResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackStartedAt": "2023-10-03T12:20:00Z",
                    "rollbackEndedAt": "2023-10-04T12:23:59Z",
                },
            ],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == get_list_assert_target_all

        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                "-s",
                "CANCELED",
                "-ss",
                "2023-10-02T00:00:02Z",
                "-su",
                "2023-10-02T23:59:59Z",
                "-es",
                "2023-10-02T12:24:01Z",
                "-eu",
                "2023-10-04T12:24:00Z",
            ]
        ],
    )
    def test_cmd_get_all_success_when_end_date_only_not_in_range(self, mocker, init_db_instance, args, capfd):
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_1])
            init_db_instance.commit()
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid_2])
            init_db_instance.commit()

        # "applyID": "000000005e"（target）"applyID": "000000006f"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": applyid_1,
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"test": "test"},
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == get_list_assert_target_all
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                "-s",
                "CANCELED",
                "-ss",
                "2023-10-02T00:00:02Z",
                "-su",
                "2023-10-03T00:00:00Z",
                "-es",
                "2023-10-02T12:24:02Z",
                "-eu",
                "2023-10-04T12:24:00Z",
            ]
        ],
    )
    def test_cmd_get_all_success_when_end_date_start_only_not_in_range(self, mocker, init_db_instance, args, capfd):
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_1])
            init_db_instance.commit()
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid_2])
            init_db_instance.commit()

        # "applyID": "000000006f"（target）"applyID": "000000005e"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": applyid_2,
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"test": "test"},
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                    "rollbackStatus": "COMPLETED",
                    "rollbackResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackStartedAt": "2023-10-03T12:20:00Z",
                    "rollbackEndedAt": "2023-10-04T12:23:59Z",
                },
            ],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == get_list_assert_target_all
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args, fields",
        [
            (
                ["get", "--fields", "procedures"],
                ["procedures"],
            ),  # fields:procedures
            (
                ["get", "--fields", "applyResult"],
                ["applyResult"],
            ),  # fields:applyResult
            (
                ["get", "--fields", "rollbackProcedures"],
                ["rollbackProcedures"],
            ),  # fields:rollbackProcedures
            (
                ["get", "--fields", "rollbackResult"],
                ["rollbackResult"],
            ),  # fields:rollbackResult
            (
                ["get", "--fields", "procedures,applyResult"],
                ["procedures", "applyResult"],
            ),  # fields:procedures/applyResult
            (
                ["get", "--fields", "procedures,rollbackProcedures"],
                ["procedures", "rollbackProcedures"],
            ),  # fields:procedures/rollbackProcedures
            (
                ["get", "--fields", "procedures,rollbackResult"],
                ["procedures", "rollbackResult"],
            ),  # fields:procedures/rollbackResult
            (
                ["get", "--fields", "applyResult,rollbackProcedures"],
                ["applyResult", "rollbackProcedures"],
            ),  # fields:applyResult/rollbackProcedures
            (
                ["get", "--fields", "applyResult,rollbackResult"],
                ["applyResult", "rollbackResult"],
            ),  # fields:applyResult/rollbackResult
            (
                ["get", "--fields", "rollbackProcedures,rollbackResult"],
                ["rollbackProcedures", "rollbackResult"],
            ),  # fields:rollbackProcedures/rollbackResult
            (
                ["get", "--fields", "procedures,applyResult,rollbackProcedures"],
                ["procedures", "applyResult", "rollbackProcedures"],
            ),  # fields:procedures/applyResult/rollbackProcedures
            (
                ["get", "--fields", "procedures,applyResult,rollbackResult"],
                ["procedures", "applyResult", "rollbackResult"],
            ),  # fields:procedures/applyResult/rollbackResult
            (
                ["get", "--fields", "procedures,rollbackProcedures,rollbackResult"],
                ["procedures", "rollbackProcedures", "rollbackResult"],
            ),  # fields:procedures/rollbackProcedures/rollbackResult
            (
                ["get", "--fields", "applyResult,rollbackProcedures,rollbackResult"],
                ["applyResult", "rollbackProcedures", "rollbackResult"],
            ),  # fields:applyResult/rollbackProcedures/rollbackResult
            (
                [
                    "get",
                    "--fields",
                    "procedures,applyResult,rollbackProcedures,rollbackResult",
                ],
                ["procedures", "applyResult", "rollbackProcedures", "rollbackResult"],
            ),  # fields:procedures/applyResult/rollbackProcedures/rollbackResult
        ],
    )
    def test_cmd_get_all_success_when_fields_specified(self, mocker, init_db_instance, args, fields, capfd):
        def _fields_check(check_targets: list, fields: list, result: dict):
            for target in check_targets:
                if target in fields:
                    assert target in result
                else:
                    assert target not in result

        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        applyid_3 = create_randomname(IdParameter.LENGTH)
        applyid_4 = create_randomname(IdParameter.LENGTH)
        applyid_5 = create_randomname(IdParameter.LENGTH)
        applyid_6 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_fields_insert_sql_1, vars=[applyid_1])
            cursor.execute(query=sql.get_fields_insert_sql_2, vars=[applyid_2])
            cursor.execute(query=sql.get_fields_insert_sql_3, vars=[applyid_3])
            cursor.execute(query=sql.get_fields_insert_sql_4, vars=[applyid_4])
            cursor.execute(query=sql.get_fields_insert_sql_5, vars=[applyid_5])
            cursor.execute(query=sql.get_fields_insert_sql_6, vars=[applyid_6])
            init_db_instance.commit()

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        applyResults = json.loads(out).get("applyResults")
        # standard output displays only the items specified by fields, and items not specified are not displayed.
        for result in applyResults:
            match result.get("status"):
                case "COMPLETED" | "FAILED":
                    # no rollback data
                    assert "rollbackProcedures" not in result
                    assert "rollbackResult" not in result
                    _fields_check(["procedures", "applyResult"], fields, result)
                case "IN_PROGRESS":
                    # no items that can be specified in fields
                    assert "applyResult" not in result
                    assert "rollbackProcedures" not in result
                    assert "rollbackResult" not in result
                case "CANCELING":
                    # no items that can be specified in fields
                    assert "rollbackProcedures" not in result
                    assert "rollbackResult" not in result
                case "CANCELED":
                    if result.get("executeRollback") is False:
                        assert "rollbackResult" not in result
                        _fields_check(
                            ["procedures", "applyResult", "rollbackProcedures"],
                            fields,
                            result,
                        )
                    else:
                        _fields_check(
                            [
                                "procedures",
                                "applyResult",
                                "rollbackProcedures",
                                "rollbackResult",
                            ],
                            fields,
                            result,
                        )

        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                "-s",
                "CANCELED",
                "-ss",
                "2023-10-02T00:00:02Z",
                "-su",
                "2023-10-03T00:00:00Z",
                "-es",
                "2023-10-02T12:24:01Z",
                "-eu",
                "2023-10-04T12:23:58Z",
            ]
        ],
    )
    def test_cmd_get_all_success_when_end_date_end_only_not_in_range(self, mocker, init_db_instance, args, capfd):
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_1])
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid_2])
            init_db_instance.commit()

        # "applyID": "000000005e"（target）"applyID": "000000006f"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": applyid_1,
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"test": "test"},
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == get_list_assert_target_all
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                "-s",
                "CANCELED",
                "-ss",
                "2023-10-05T00:00:00Z",
                "-su",
                "2023-10-06T00:00:00Z",
                "-es",
                "2023-10-05T00:00:00Z",
                "-eu",
                "2023-10-06T23:59:59Z",
            ]
        ],
    )
    def test_cmd_get_all_success_when_both_start_and_end_date_outside_range(
        self, mocker, init_db_instance, args, capfd
    ):
        # arrange
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_1])
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid_2])
            init_db_instance.commit()

        # "applyID": "000000005e"、"applyID": "000000006f"（no target）
        get_list_assert_target_all = {
            "totalCount": 0,
            "count": 0,
            "applyResults": [],
        }

        sys.argv = ["cli.py", *args]

        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == get_list_assert_target_all
        # There is no standard error output.
        assert err == ""

    def test_cmd_get_all_success_when_state_specified(self, mocker, init_db_instance, capfd):
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid_1])
            cursor.execute(query=sql.get_list_insert_sql_3, vars=[applyid_2])
            init_db_instance.commit()

        get_list_assert_target_status = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "applyID": applyid_1,
                    "status": "IN_PROGRESS",
                    "startedAt": "2023-10-02T00:00:00Z",
                },
            ],
        }

        args = ["get", "--status", "IN_PROGRESS"]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == get_list_assert_target_status
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                "--started-at-since",
                "2023-10-02T00:00:01Z",
                "--started-at-until",
                "2023-10-02T00:00:02Z",
                "--ended-at-since",
                "2023-10-02T12:24:00Z",
                "--ended-at-until",
                "2023-10-02T12:24:01Z",
            ]
        ],
    )
    def test_cmd_get_all_success_when_time_equals_for_time_specification(self, mocker, init_db_instance, args, capfd):
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        applyid_3 = create_randomname(IdParameter.LENGTH)
        applyid_4 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_3, vars=[applyid_1])
            cursor.execute(query=sql.get_list_insert_sql_4, vars=[applyid_2])
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_3])
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid_4])
            init_db_instance.commit()
        get_list_assert_target_equal = {
            "totalCount": 2,
            "count": 2,
            "applyResults": [
                {
                    "status": "FAILED",
                    "applyID": applyid_2,
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "startedAt": "2023-10-02T00:00:01Z",
                    "endedAt": "2023-10-02T12:24:00Z",
                },
                {
                    "status": "CANCELED",
                    "applyID": applyid_3,
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"test": "test"},
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        res = json.loads(out)
        assert res["count"] == get_list_assert_target_equal["count"]
        assert res["totalCount"] == get_list_assert_target_equal["totalCount"]
        for a in res["applyResults"]:
            assert a in get_list_assert_target_equal["applyResults"]
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                "--started-at-since",
                "2023-10-02T00:00:02Z",
                "--started-at-until",
                "2023-10-02T00:00:03Z",
                "--ended-at-since",
                "2023-10-02T12:24:01Z",
                "--ended-at-until",
                "2023-10-02T12:24:02Z",
            ]
        ],
    )
    def test_cmd_get_all_failure_when_add_second_to_upper_time_limit(self, mocker, init_db_instance, args, capfd):
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        applyid_3 = create_randomname(IdParameter.LENGTH)
        applyid_4 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_3, vars=[applyid_1])
            cursor.execute(query=sql.get_list_insert_sql_4, vars=[applyid_2])
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_3])
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid_4])
            init_db_instance.commit()

        get_list_assert_target_plus1 = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": applyid_3,
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"test": "test"},
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == get_list_assert_target_plus1
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                "--started-at-since",
                "2023-10-02T00:00:00Z",
                "--started-at-until",
                "2023-10-02T00:00:01Z",
                "--ended-at-since",
                "2023-10-02T12:23:59Z",
                "--ended-at-until",
                "2023-10-02T12:24:00Z",
            ]
        ],
    )
    def test_cmd_get_all_success_when_subtract_second_from_lower_time_limit(
        self, mocker, init_db_instance, args, capfd
    ):
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        applyid_3 = create_randomname(IdParameter.LENGTH)
        applyid_4 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid_1])
            cursor.execute(query=sql.get_list_insert_sql_3, vars=[applyid_2])
            cursor.execute(query=sql.get_list_insert_sql_4, vars=[applyid_3])
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_4])
            init_db_instance.commit()

        get_list_assert_target_minus1 = {
            "totalCount": 2,
            "count": 2,
            "applyResults": [
                {
                    "status": "COMPLETED",
                    "applyID": applyid_2,
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "startedAt": "2023-10-02T00:00:00Z",
                    "endedAt": "2023-10-02T12:23:59Z",
                },
                {
                    "status": "FAILED",
                    "applyID": applyid_3,
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "startedAt": "2023-10-02T00:00:01Z",
                    "endedAt": "2023-10-02T12:24:00Z",
                },
            ],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        res = json.loads(out)
        assert res["count"] == get_list_assert_target_minus1["count"]
        assert res["totalCount"] == get_list_assert_target_minus1["totalCount"]
        for a in res["applyResults"]:
            a in get_list_assert_target_minus1["applyResults"]
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        ["args", "count"],
        [
            (
                [
                    "get",
                    "--fields",
                    "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                    "--sort-by",
                    "startedAt",
                ],
                9,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                    "--sort-by",
                    "endedAt",
                ],
                9,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                    "--order-by",
                    "asc",
                ],
                9,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                    "--order-by",
                    "desc",
                ],
                9,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                    "--limit",
                    "5",
                ],
                5,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                    "--limit",
                    "100",
                ],
                9,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                    "--offset",
                    "0",
                ],
                9,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                    "--offset",
                    "8",
                ],
                1,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                    "--order-by",
                    "desc",
                    "--sort-by",
                    "endedAt",
                    "--limit",
                    "10",
                    "--offset",
                    "0",
                ],
                9,
            ),
        ],
    )
    def test_cmd_get_all_success_when_specified_sortby_and_orderby_and_count_offset(
        self, init_db_instance, count, args, capfd
    ):
        id_list = self.insert_list_data(init_db_instance)
        for i, result_dict in enumerate(get_list_assert_target["applyResults"]):
            result_dict["applyID"] = id_list[i]

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        a = json.loads(out)
        assert a["totalCount"] == len(id_list)
        assert a["count"] == count
        for apply in a["applyResults"]:
            assert apply in get_list_assert_target["applyResults"]
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "-s", "IN_PROGRESS"]),
        ],
    )
    def test_cmd_get_all_success_when_no_specified_sortby_and_orderby_and_count_offset(
        self, init_db_instance, args, capfd, get_list_assert_target_no_fields, mocker, caplog, docker_services
    ):
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger()
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        id_list = self.insert_list_data(init_db_instance)
        for i, result_dict in enumerate(get_list_assert_target_no_fields["applyResults"]):
            result_dict["applyID"] = id_list[i]

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        a = json.loads(out)
        assert a["totalCount"] == 1
        for apply in a["applyResults"]:
            assert apply in get_list_assert_target_no_fields["applyResults"]
        # There is no standard error output.
        assert err == ""

        assert "ORDER BY startedAt desc " in caplog.text
        assert "LIMIT 20 " in caplog.text
        assert "OFFSET 0" in caplog.text

    @pytest.mark.parametrize(
        "args",
        [
            (
                [
                    "get",
                    "--fields",
                    "procedures,applyResult,rollbackProcedures,rollbackResult,resumeProcedures,resumeResult",
                    "--offset",
                    "10",
                ]
            ),
        ],
    )
    def test_cmd_get_all_success_when_specified_offset_exceed_data_count_registered_database(
        self, init_db_instance, args, capfd
    ):
        id_list = self.insert_list_data(init_db_instance)
        for i, result_dict in enumerate(get_list_assert_target["applyResults"]):
            result_dict["applyID"] = id_list[i]

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        a = json.loads(out)
        assert a["totalCount"] == 9
        assert a["count"] == 0
        assert a["applyResults"] == []
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            (
                [
                    "delete",
                    "--help",
                ]
            ),
            (
                [
                    "delete",
                    "-h",
                ]
            ),
        ],
    )
    def test_cmd_delete_success_when_help(
        self,
        args,
        capfd,
    ):
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
        assert "specified applyID for delete. applyID as a string." in out

    @pytest.mark.parametrize(
        ("insert_sql"),
        [
            (sql.get_list_insert_sql_3),
            (sql.get_list_insert_sql_4),
            (sql.get_list_insert_sql_5),
            (sql.get_list_insert_sql_6),
        ],
    )
    def test_cmd_delete_success_when_id_not_in_execution(self, mocker, init_db_instance, insert_sql, capfd):
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()
        assert_print = "Success.\n"

        args = ["delete", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # message indicating the change in reflection status due to cancellation is output to the standard output.
        assert out == assert_print
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        ("insert_sql"),
        [
            (sql.get_list_insert_sql_1),
            (sql.get_list_insert_sql_2),
            (sql.get_list_insert_sql_7),
        ],
    )
    def test_cmd_delete_failure_when_id_in_execution(self, mocker, init_db_instance, insert_sql, capfd):
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()
        assert_print = "[E40024]Apply ID cannot be deleted because it is currently being running. Try later again.\n"

        args = ["delete", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.DELETE_CONFLICT_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # standard error outputs the E40024 error.
        assert err == assert_print

    @pytest.mark.parametrize(
        ("insert_sql"),
        [
            (sql.insert_delete_target_sql_8),
            (sql.insert_delete_target_sql_9),
        ],
    )
    def test_cmd_delete_failure_when_rollback_id_in_progress(self, mocker, init_db_instance, insert_sql, capfd):

        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()

        assert_print = "[E40024]Apply ID cannot be deleted because it is currently being running. Try later again.\n"

        args = ["delete", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.DELETE_CONFLICT_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # standard error outputs the E40024 error.
        assert err == assert_print

    @pytest.mark.parametrize("args", [["delete", "--apply-id", "012345678g"]])
    def test_cmd_delete_failure_when_invalid_option(self, args, capfd):
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

    @pytest.mark.parametrize("args", [["delete", "--apply-id", "012345678a"]])
    def test_cmd_delete_failure_when_invalid_config_file(self, mocker, args, capfd):
        config = {
            "log": {
                "logging_level": "INFO",
                "log_dir": "./",
                "rotation_size": 1000000,
                "backup_files": 3,
            },
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

    @pytest.mark.parametrize("args", [["delete", "--apply-id", "012345678a"]])
    def test_cmd_delete_failure_when_failed_db_connection(self, mocker, args, capfd):
        assert_print = "[E40018]Could not connect to ApplyStatusDB."
        mocker.patch.object(DbAccess, "get_apply_status", side_effect=psycopg2.OperationalError)
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

    @pytest.mark.parametrize("args", [["delete", "--apply-id", "012345678d"]])
    def test_cmd_delete_failure_when_query_failure_occurred(self, mocker, args, capfd):
        assert_print = "[E40019]Query failed."
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

    @pytest.mark.parametrize("args", [["delete", "--apply-id", "abcdeabcde"]])
    def test_cmd_delete_failure_when_nonexistent_id(self, mocker, init_db_instance, args, capfd, docker_services):
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

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "300000004d"]])
    def test_cmd_resume_success(self, mocker, init_db_instance, args, httpserver):
        uri = HARDWARE_CONTROL_URI

        httpserver.clear()
        httpserver.clear_all_handlers()

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="""
                    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES 
                    ('300000004d','SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,null,null,null,null,null,null,'[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',null,null,null,null,'2023/10/02 12:23:59',null);
                """
            )
            init_db_instance.commit()
        # arrange

        applyid = "300000004d"

        sys.argv = ["cli.py", *args]

        config = LayoutApplyConfig()
        config.load_log_configs()
        # act
        procces_mock = mocker.patch(
            "subprocess.Popen",
            return_value=Process(
                target=run,
                args=(
                    {
                        "procedures": [
                            {
                                "operationID": 1,
                                "operation": "shutdown",
                                "targetDeviceID": "0001",
                                "dependencies": [],
                            }
                        ]
                    },
                    config,
                    applyid,
                    Action.RESUME,
                ),
            ),
        )
        with pytest.raises(SystemExit) as excinfo:
            procces_mock.return_value.start()
            main()
        # with httpserver.wait(stop_on_nohandler=False, timeout=0.1) as waiter:
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        httpserver.expect_request(
            re.compile(f"\/{GET_INFORMATION_URI}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_json(
            {"type": "CPU", "powerState": "Off", "powerCapability": False},
            status=200,
        )
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()

        # assert

        assert excinfo.value.code == 0

        # result of the operation completion list is 'IN_PROGRESS'
        if row.get("status") == "IN_PROGRESS":
            assert row.get("status") == "IN_PROGRESS"
            for i in range(15):
                sleep(0.5)
                try:
                    with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                        cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
                        init_db_instance.commit()
                        row = cursor.fetchone()
                except psycopg2.ProgrammingError:
                    break
                if row.get("status") == "COMPLETED":
                    break

        assert row.get("status") == "COMPLETED"
        assert row.get("rollbackprocedures") is None
        assert row.get("applyresult") != row.get("resumeresult")
        details = row.get("resumeresult")
        procedures = row.get("resumeprocedures")
        assert details is not None
        assert len(details) == len(procedures)
        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")
        for proc in procedures:
            # Search for items corresponding to the migration procedure from
            # result details using operationID as a condition
            detail = [i for i in details if i["operationID"] == proc["operationID"]][0]
            assert proc["operationID"] == detail["operationID"]
            assert "COMPLETED" == detail["status"]
            # Check the URI, etc. of the hardware control API
            match proc["operation"]:
                case "shutdown":
                    assert re.fullmatch(
                        f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                        detail["uri"],
                    )
                    assert "PUT" == detail["method"]
                    assert "queryParameter" not in detail
                    assert 200 == detail["statusCode"]
                    assert {"action": "off"} == detail["requestBody"]
                    get_information = detail["getInformation"]
                    assert {"powerState": "Off"} == get_information["responseBody"]

        if procces_mock.return_value.is_alive():
            procces_mock.return_value.terminate()
            procces_mock.return_value.join()
        sleep(1)
        httpserver.clear()
        httpserver.clear_all_handlers()

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "300000013d"]])
    def test_cmd_resume_success_when_rollback_state_suspended(self, mocker, init_db_instance, args, httpserver):
        uri = HARDWARE_CONTROL_URI

        httpserver.clear()
        httpserver.clear_all_handlers()

        # with httpserver.wait(stop_on_nohandler=False, timeout=0.1) as waiter:
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        httpserver.expect_request(
            re.compile(f"\/{GET_INFORMATION_URI}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_json(
            {"type": "CPU", "powerState": "Off", "powerCapability": False},
            status=200,
        )
        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="""
                    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES 
                    ('300000013d','CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]','{"test": "pre_test"}','2023/10/02 00:00:00','2023/10/02 01:00:00','2023/10/02 00:30:00',TRUE,'SUSPENDED',null,'2023/10/02 00:40:00',null,'[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',null,null,null,null,'2023/10/02 00:50:00',null);
                """
            )
        init_db_instance.commit()
        # arrange

        applyid = "300000013d"

        sys.argv = ["cli.py", *args]

        config = LayoutApplyConfig()
        config.load_log_configs()
        # act
        procces_mock = mocker.patch(
            "subprocess.Popen",
            return_value=Process(
                target=run,
                args=(
                    {
                        "procedures": [
                            {
                                "operationID": 1,
                                "operation": "shutdown",
                                "targetDeviceID": "0001",
                                "dependencies": [],
                            }
                        ]
                    },
                    config,
                    applyid,
                    Action.ROLLBACK_RESUME,
                ),
            ),
        )
        with pytest.raises(SystemExit) as excinfo:
            procces_mock.return_value.start()
            main()
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()
        init_db_instance.commit()
        # assert
        assert excinfo.value.code == 0

        # result of the operation completion list is 'IN_PROGRESS'
        if row.get("rollbackstatus") == "IN_PROGRESS":
            assert row.get("rollbackstatus") == "IN_PROGRESS"
            for i in range(15):
                sleep(0.5)
                try:
                    with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                        cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
                        init_db_instance.commit()
                        row = cursor.fetchone()
                except psycopg2.ProgrammingError:
                    break
                if row.get("rollbackstatus") == "COMPLETED":
                    break

        assert row.get("rollbackstatus") == "COMPLETED"
        assert row.get("applyresult") != row.get("resumeresult")
        details = row.get("resumeresult")
        procedures = row.get("resumeprocedures")
        assert details is not None
        assert len(details) == len(procedures)
        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")
        for proc in procedures:
            # Search for items corresponding to the migration procedure from
            # result details using operationID as a condition
            detail = [i for i in details if i["operationID"] == proc["operationID"]][0]
            assert proc["operationID"] == detail["operationID"]
            assert "COMPLETED" == detail["status"]
            # Check the URI, etc. of the hardware control API
            match proc["operation"]:
                case "shutdown":
                    assert re.fullmatch(
                        f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                        detail["uri"],
                    )
                    assert "PUT" == detail["method"]
                    assert "queryParameter" not in detail
                    assert 200 == detail["statusCode"]
                    assert {"action": "off"} == detail["requestBody"]
                    get_information = detail["getInformation"]
                    assert {"powerState": "Off"} == get_information["responseBody"]

        if procces_mock.return_value.is_alive():
            procces_mock.return_value.terminate()
            procces_mock.return_value.join()
        sleep(1)
        httpserver.clear()
        httpserver.clear_all_handlers()

    @pytest.mark.parametrize(
        "args",
        [
            (
                [
                    "resume",
                    "--help",
                ]
            ),
            (
                [
                    "resume",
                    "-h",
                ]
            ),
        ],
    )
    def test_cmd_resume_success_when_help(
        self,
        args,
        capfd,
    ):
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
        assert "specified applyID for resume. applyID as a string." in out

    @pytest.mark.parametrize(
        "args",
        [
            (["resume", "--apply-id", "g21bc21587"]),  # character type violation
            (["resume", "--apply-id", "ABCDEF0123"]),  # character type violation
            (["resume", "--apply-id", "あBCDEF0123"]),  # character type violation
            (["resume", "--apply-id", "a21bc2158"]),  # character length violation
            (["resume", "--apply-id", "a21bc215871"]),  # character length violation
            (["resume", "--apply-id", "a"]),  # character length violation
        ],
    )
    def test_cmd_resume_failure_when_invalid_id(self, args, capfd):
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out == ""
        assert err.startswith("[E40001]")

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "012345678a"]])
    def test_cmd_resume_failure_when_invalid_config_file(self, mocker, args, capfd):
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

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "012345678d"]])
    def test_cmd_resume_failure_when_failed_db_connection(self, mocker, args, capfd):
        assert_print = "[E40018]Could not connect to ApplyStatusDB."
        mocker.patch.object(DbAccess, "proc_resume", side_effect=psycopg2.OperationalError)
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

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "012345678d"]])
    def test_cmd_resume_failure_when_query_failure_occurred(self, mocker, args, capfd):
        assert_print = "[E40019]Query failed."
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

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "abcdeabcde"]])
    def test_cmd_resume_failure_when_nonexistent_id(self, mocker, init_db_instance, args, capfd):
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

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "300000007b"]])
    def test_cmd_resume_failure_when_failed_to_start_subprocess(self, capfd, mocker, init_db_instance, args, caplog):
        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="""
                    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES 
                    ('300000007b','SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,null,null,null,null,null,null,'{"procedures": [{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]}',null,null,null,null,'2023/10/02 12:23:59',null);
                """
            )
            init_db_instance.commit()
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.ERROR)

        # arrange

        # Mock the subprocess
        mocker.patch(
            "subprocess.Popen",
            side_effect=Exception(),
        )

        sys.argv = ["cli.py", *args]

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

    def test_cmd_resume_success_when_rollback_id_executed(self, mocker, init_db_instance, capfd):
        # arrage
        applyid = create_randomname(IdParameter.LENGTH)
        # Ensure that IN_PROGRESS data exists before the test
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_fields_insert_sql_6, vars=[applyid])
            init_db_instance.commit()

        args = ["resume", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]

        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # Ensure that a successful completion log is output to standard output.
        assert "Success" in out
        assert "status=CANCELED" in out
        assert "rollbackStatus=COMPLETED" in out
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "insert_sql",
        [
            (sql.get_list_insert_sql_3),  # COMPLETED
            (sql.get_list_insert_sql_4),  # FAILED
            (sql.get_list_insert_sql_5),  # CANCELED
        ],
    )
    def test_cmd_resume_success_when_executed_id(self, mocker, init_db_instance, insert_sql, capfd):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()

        args = ["resume", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]

        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # Ensure that a successful completion log is output to standard output.
        assert "Success" in out
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "insert_sql",
        [
            (sql.get_list_insert_sql_1),  # IN_PROGRESS
            (sql.get_list_insert_sql_2),  # CANCELING
        ],
    )
    def test_cmd_resume_success_when_id_in_execution(self, mocker, init_db_instance, insert_sql, capfd):
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()

        args = ["resume", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # arrange
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()

        args = ["resume", "--apply-id", applyid]
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
        assert "[E40022]This layoutapply has already executed." in err

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "300000012c"]])
    def test_cmd_resume_failure_when_rollback_id_in_progress(self, mocker, init_db_instance, args, capfd):
        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="""
                    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES 
                    ('300000012c','CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]','{"test": "pre_test"}','2023/10/02 00:00:00','2023/10/02 01:00:00','2023/10/02 00:30:00',TRUE,'IN_PROGRESS',null,'2023/10/02 00:40:00',null,'[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',null,null,null,null,'2023/10/02 00:50:00',null);
                """
            )
            init_db_instance.commit()
        assert_print = "[E40022]This layoutapply has already executed.\n"

        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="DELETE FROM applystatus WHERE applyid = '300000012c'")
            init_db_instance.commit()
        # assert
        assert excinfo.value.code == ExitCode.MULTIPLE_RUN_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # error E40022 is output to the standard error.
        assert err == assert_print

    def test_cmd_resume_failure_when_db_access_failure_during_subprocess_registration(self, mocker, capfd):

        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = psycopg2.OperationalError
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)
        config = LayoutApplyLogConfig().log_config
        logger = Logger(config)
        db = DbAccess(logger)
        # act
        sys.argv = ["cli.py", "resume", "--apply-id", "dummy"]
        with pytest.raises(SystemExit) as excinfo:
            LayoutApplyCommandLine()._update_subporcess_info(db, os.getpid(), "dummy")

        # assert
        assert excinfo.value.code == ExitCode.DB_CONNECT_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # Ensure that the E40018 error is output to the standard error.
        assert "[E40018]Could not connect to ApplyStatusDB." in err

    def test_cmd_resume_failure_when_query_failure_during_subprocess_registration(self, mocker, capfd, docker_services):

        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)
        config = LayoutApplyLogConfig()
        logger = Logger(config.log_config)
        db = DbAccess(logger)
        # act
        sys.argv = ["cli.py", "resume", "--apply-id", "123456789a"]
        with pytest.raises(SystemExit) as excinfo:
            LayoutApplyCommandLine()._update_subporcess_info(db, os.getpid(), "123456789a")

        # assert
        assert excinfo.value.code == ExitCode.QUERY_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # error E40019 is output to the standard error.
        assert "[E40019]Query failed." in err
