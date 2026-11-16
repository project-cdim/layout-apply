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
"""Test of main routine"""

import io
import logging.config
import re
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import asdict
from time import sleep
from uuid import uuid4

import psycopg2
import pytest
from psycopg2.extras import DictCursor
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from layoutapply.common.logger import Logger
from layoutapply.const import Action, IdParameter, Operation, Result
from layoutapply.data import Details, Procedure, details_dict_factory, get_procedure_list
from layoutapply.db import DbAccess
from layoutapply.main import (
    _cancel_run,
    _change_operation,
    _clear_dependencies,
    _convert_to_rollback,
    _create_resume_proc,
    _create_rollback_proc,
    _create_task,
    _find_first_proc,
    _find_next_proc,
    _get_ids,
    _get_rollback_target_proc,
    _get_skip_ids,
    _swap_execution_order,
    _update_layoutapply,
    run,
)
from layoutapply.setting import LayoutApplyConfig, LayoutApplyLogConfig
from layoutapply.util import create_randomname
from tests.layoutapply.conftest import (
    DEVICE_INFO_URL,
    EXTENDED_PROCEDURE_URI,
    OPERATION_URL,
    OS_BOOT_URL,
    POWER_OPERATION_URL,
    WORKFLOW_MANAGER_HOST,
    WORKFLOW_MANAGER_PORT,
)
from tests.layoutapply.test_data import sql
from tests.layoutapply.test_data.procedure import multi_pattern, single_pattern, single_pattern_cancel

SELECT_SQL = "SELECT * FROM applystatus WHERE applyid = %s"
CHANGE_CANCEL_SQL = "UPDATE applystatus SET status='CANCELING', canceledat='2023/10/02 12:23:59', executerollback=FALSE WHERE applyid = %s"


@pytest.mark.usefixtures("httpserver_listen_address")
class TestMain:

    @pytest.mark.usefixtures("hardwaremgr_fixture")
    def test_run_status_completed_when_single_migration_step(self, init_db_instance, mocker, caplog):
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.INFO)

        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
        init_db_instance.commit()
        config = LayoutApplyConfig()
        config.load_log_configs()

        # act
        for pattern in single_pattern:
            procedures = pattern[0]

            run(procedures, config, applyid)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=SELECT_SQL, vars=[applyid])
                init_db_instance.commit()
                row = cursor.fetchone()
            if row.get("status") == "IN_PROGRESS":
                assert row.get("status") == "IN_PROGRESS"
                for i in range(15):
                    sleep(0.5)
                    cursor.execute(query=SELECT_SQL, vars=[applyid])
                    init_db_instance.commit()
                    row = cursor.fetchone()
                    if row.get("status") != "IN_PROGRESS":
                        break

            # assert
            # result is COMPLETED
            assert row.get("status") == "COMPLETED"
            # execution results are dumped.
            details = row.get("applyresult")
            assert details is not None
            assert len(details) == len(procedures["procedures"])

            host = config.hardware_control.get("host")
            port = config.hardware_control.get("port")
            uri = config.hardware_control.get("uri")

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from the result details using operationID as a condition
                detail = [i for i in details if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                assert "COMPLETED" == detail["status"]
                # Check the URI, etc. of the hardware control API
                # Review the mockup method with hardwaremgr_fixture as well
                assert "responseBody" not in detail
                assert "queryParameter" not in detail
                match procedure["operation"]:
                    case "connect":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {
                            "action": "connect",
                            "deviceID": procedure["targetDeviceID"],
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
                            "deviceID": procedure["targetDeviceID"],
                        }
                        assert 200 == detail["statusCode"]

                    case "boot":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {"action": "on"}
                        assert 200 == detail["statusCode"]

                    case "shutdown":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]

        assert "Published message to topic " in caplog.text

    @pytest.mark.usefixtures("hardwaremgr_fixture", "extended_procedure_fixture")
    def test_run_status_completed_when_multiple_migration_steps(
        self,
        init_db_instance,
        mocker,
    ):
        """"""
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
        init_db_instance.commit()
        config = LayoutApplyConfig()
        config.load_log_configs()
        config.workflow_manager["host"] = "localhost"

        # act
        for pattern in multi_pattern:
            procedures = pattern[0]
            run(procedures, config, applyid)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=SELECT_SQL, vars=[applyid])
                init_db_instance.commit()
                row = cursor.fetchone()
                cursor.execute("SELECT * FROM applystatus WHERE applyid = %s", [applyid])
                full_row = cursor.fetchone()

            if row.get("status") == "IN_PROGRESS":
                assert row.get("status") == "IN_PROGRESS"
                for i in range(15):
                    sleep(0.5)
                    cursor.execute(query=SELECT_SQL, vars=[applyid])
                    init_db_instance.commit()
                    row = cursor.fetchone()
                    if row.get("status") != "IN_PROGRESS":
                        break
            # assert
            # result is COMPLETED
            assert row.get("status") == "COMPLETED"
            # execution results are dumped.
            details = row.get("applyresult")
            assert details is not None
            assert len(details) == len(procedures["procedures"])

            host = config.hardware_control.get("host")
            port = config.hardware_control.get("port")
            uri = config.hardware_control.get("uri")

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from the result details using operationID as a condition
                detail = [i for i in details if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                assert "COMPLETED" == detail["status"]
                # Check the URI, etc. of the hardware control API
                # Review the mockup method with hardwaremgr_fixture as well

                match procedure["operation"]:
                    case "connect":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {
                            "action": "connect",
                            "deviceID": procedure["targetDeviceID"],
                        }
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "disconnect":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert "queryParameter" not in detail
                        assert detail["requestBody"] == {
                            "action": "disconnect",
                            "deviceID": procedure["targetDeviceID"],
                        }
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "boot":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {"action": "on"}
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "shutdown":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "start":
                        assert re.fullmatch(
                            f"http:\/\/{WORKFLOW_MANAGER_HOST}:{WORKFLOW_MANAGER_PORT}\/{uri}\/{EXTENDED_PROCEDURE_URI}",
                            detail["uri"],
                        )
                        assert "POST" == detail["method"]
                        assert "queryParameter" not in detail
                        assert 202 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "stop":
                        assert re.fullmatch(
                            f"http:\/\/{WORKFLOW_MANAGER_HOST}:{WORKFLOW_MANAGER_PORT}\/{uri}\/{EXTENDED_PROCEDURE_URI}",
                            detail["uri"],
                        )
                        assert "POST" == detail["method"]
                        assert "queryParameter" not in detail
                        assert 202 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

    @pytest.mark.usefixtures("hardwaremgr_fixture", "extended_procedure_fixture")
    def test_run_status_completed_when_multiple_migration_steps_setting_valid_max_workers(
        self,
        init_db_instance,
        mocker,
    ):
        """"""
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
        init_db_instance.commit()
        config = LayoutApplyConfig()
        config.load_log_configs()
        del config.layout_apply["request"]
        config.workflow_manager["host"] = "localhost"

        # act
        for pattern in multi_pattern:
            procedures = pattern[0]
            run(procedures, config, applyid)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=SELECT_SQL, vars=[applyid])
                init_db_instance.commit()
                row = cursor.fetchone()
            if row.get("status") == "IN_PROGRESS":
                assert row.get("status") == "IN_PROGRESS"
                for i in range(15):
                    sleep(0.5)
                    cursor.execute(query=SELECT_SQL, vars=[applyid])
                    init_db_instance.commit()
                    row = cursor.fetchone()
                    if row.get("status") != "IN_PROGRESS":
                        break
            # assert
            # result is COMPLETED
            assert row.get("status") == "COMPLETED"
            # execution results are dumped.
            details = row.get("applyresult")
            assert details is not None
            assert len(details) == len(procedures["procedures"])

            host = config.hardware_control.get("host")
            port = config.hardware_control.get("port")
            uri = config.hardware_control.get("uri")

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from the result details using operationID as a condition
                detail = [i for i in details if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                assert "COMPLETED" == detail["status"]
                # Check the URI, etc. of the hardware control API
                # Review the mockup method with hardwaremgr_fixture as well

                match procedure["operation"]:
                    case "connect":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {
                            "action": "connect",
                            "deviceID": procedure["targetDeviceID"],
                        }
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "disconnect":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert "queryParameter" not in detail
                        assert detail["requestBody"] == {
                            "action": "disconnect",
                            "deviceID": procedure["targetDeviceID"],
                        }
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "boot":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {"action": "on"}
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "shutdown":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "start":
                        assert re.fullmatch(
                            f"http:\/\/{WORKFLOW_MANAGER_HOST}:{WORKFLOW_MANAGER_PORT}\/{uri}\/{EXTENDED_PROCEDURE_URI}",
                            detail["uri"],
                        )
                        assert "POST" == detail["method"]
                        assert "queryParameter" not in detail
                        assert 202 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "stop":
                        assert re.fullmatch(
                            f"http:\/\/{WORKFLOW_MANAGER_HOST}:{WORKFLOW_MANAGER_PORT}\/{uri}\/{EXTENDED_PROCEDURE_URI}",
                            detail["uri"],
                        )
                        assert "POST" == detail["method"]
                        assert "queryParameter" not in detail
                        assert 202 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

    @pytest.mark.usefixtures("hardwaremgr_fixture", "extended_procedure_fixture")
    def test_run_status_completed_when_multiple_migration_steps_setting_max_max_workers(
        self,
        init_db_instance,
        mocker,
    ):
        """"""
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
        init_db_instance.commit()
        config = LayoutApplyConfig()
        config.load_log_configs()
        config.layout_apply["request"] = {"max_workers": 128}
        config.workflow_manager["host"] = "localhost"

        # act
        for pattern in multi_pattern:
            procedures = pattern[0]
            run(procedures, config, applyid)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=SELECT_SQL, vars=[applyid])
                init_db_instance.commit()
                row = cursor.fetchone()
            if row.get("status") == "IN_PROGRESS":
                assert row.get("status") == "IN_PROGRESS"
                for i in range(15):
                    sleep(0.5)
                    cursor.execute(query=SELECT_SQL, vars=[applyid])
                    init_db_instance.commit()
                    row = cursor.fetchone()
                    if row.get("status") != "IN_PROGRESS":
                        break
            # assert
            # result is COMPLETED
            assert row.get("status") == "COMPLETED"
            # execution results are dumped.
            details = row.get("applyresult")
            assert details is not None
            assert len(details) == len(procedures["procedures"])

            host = config.hardware_control.get("host")
            port = config.hardware_control.get("port")
            uri = config.hardware_control.get("uri")

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from the result details using operationID as a condition
                detail = [i for i in details if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                assert "COMPLETED" == detail["status"]
                # Check the URI, etc. of the hardware control API
                # Review the mockup method with hardwaremgr_fixture as well

                match procedure["operation"]:
                    case "connect":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {
                            "action": "connect",
                            "deviceID": procedure["targetDeviceID"],
                        }
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "disconnect":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert "queryParameter" not in detail
                        assert detail["requestBody"] == {
                            "action": "disconnect",
                            "deviceID": procedure["targetDeviceID"],
                        }
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "boot":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {"action": "on"}
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "shutdown":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

    @pytest.mark.usefixtures("hardwaremgr_fixture", "extended_procedure_fixture")
    def test_run_status_completed_when_multiple_migration_steps_setting_min_max_workers(
        self,
        init_db_instance,
        mocker,
    ):
        """"""
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
        init_db_instance.commit()
        config = LayoutApplyConfig()
        config.load_log_configs()
        config.layout_apply["request"] = {"max_workers": 1}
        config.workflow_manager["host"] = "localhost"

        # act
        for pattern in multi_pattern:
            procedures = pattern[0]
            run(procedures, config, applyid)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=SELECT_SQL, vars=[applyid])
                init_db_instance.commit()
                row = cursor.fetchone()
            if row.get("status") == "IN_PROGRESS":
                assert row.get("status") == "IN_PROGRESS"
                for i in range(15):
                    sleep(0.5)
                    cursor.execute(query=SELECT_SQL, vars=[applyid])
                    init_db_instance.commit()
                    row = cursor.fetchone()
                    if row.get("status") != "IN_PROGRESS":
                        break
            # assert
            # result is COMPLETED
            assert row.get("status") == "COMPLETED"
            # execution results are dumped.
            details = row.get("applyresult")
            assert details is not None
            assert len(details) == len(procedures["procedures"])

            host = config.hardware_control.get("host")
            port = config.hardware_control.get("port")
            uri = config.hardware_control.get("uri")

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from the result details using operationID as a condition
                detail = [i for i in details if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                assert "COMPLETED" == detail["status"]
                # Check the URI, etc. of the hardware control API
                # Review the mockup method with hardwaremgr_fixture as well

                match procedure["operation"]:
                    case "connect":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {
                            "action": "connect",
                            "deviceID": procedure["targetDeviceID"],
                        }
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "disconnect":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert "queryParameter" not in detail
                        assert detail["requestBody"] == {
                            "action": "disconnect",
                            "deviceID": procedure["targetDeviceID"],
                        }
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "boot":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {"action": "on"}
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "shutdown":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "start":
                        assert re.fullmatch(
                            f"http:\/\/{WORKFLOW_MANAGER_HOST}:{WORKFLOW_MANAGER_PORT}\/{uri}\/{EXTENDED_PROCEDURE_URI}",
                            detail["uri"],
                        )
                        assert "POST" == detail["method"]
                        assert "queryParameter" not in detail
                        assert 202 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "stop":
                        assert re.fullmatch(
                            f"http:\/\/{WORKFLOW_MANAGER_HOST}:{WORKFLOW_MANAGER_PORT}\/{uri}\/{EXTENDED_PROCEDURE_URI}",
                            detail["uri"],
                        )
                        assert "POST" == detail["method"]
                        assert "queryParameter" not in detail
                        assert 202 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

    @pytest.mark.usefixtures("hardwaremgr_error_fixture")
    def test_run_status_failed_when_failed_single_migration_step(self, init_db_instance, mocker, caplog):
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.INFO)
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
            init_db_instance.commit()
        config = LayoutApplyConfig()
        config.load_log_configs()

        # act
        for pattern in single_pattern:
            procedures = pattern[0]

            run(procedures, config, applyid)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=SELECT_SQL, vars=[applyid])
                init_db_instance.commit()
                row = cursor.fetchone()
            if row.get("status") == "IN_PROGRESS":
                assert row.get("status") == "IN_PROGRESS"
                for i in range(15):
                    sleep(0.5)
                    cursor.execute(query=SELECT_SQL, vars=[applyid])
                    init_db_instance.commit()
                    row = cursor.fetchone()
                    if row.get("status") != "IN_PROGRESS":
                        break
            # assert
            # status is SUSPENDED
            assert row.get("status") == "SUSPENDED"
            # execution results are dumped.
            details = row.get("applyresult")
            assert details is not None
            assert len(details) == len(procedures["procedures"])

            host = config.hardware_control.get("host")
            port = config.hardware_control.get("port")
            uri = config.hardware_control.get("uri")

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from
                # result details using operationID as a condition
                detail = [i for i in details if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                # initially executed task results in 'Failed', and all other tasks are marked as 'SKIPPED'
                if not procedure["dependencies"]:
                    assert "FAILED" == detail["status"]
                    match procedure["operation"]:
                        case "connect":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert detail["requestBody"] == {
                                "action": "connect",
                                "deviceID": procedure["targetDeviceID"],
                            }
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                        case "disconnect":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {
                                "action": "disconnect",
                                "deviceID": procedure["targetDeviceID"],
                            }
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                        case "boot":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {"action": "on"}
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                        case "shutdown":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                            assert detail["startedAt"] is not None
                            assert detail["endedAt"] is not None

        assert "Published message to topic " in caplog.text

    @pytest.mark.usefixtures("hardwaremgr_error_fixture", "extended_procedure_error_fixture")
    def test_run_status_failed_when_failed_multiple_migration_steps(self, init_db_instance, mocker, caplog):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.INFO)
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
            init_db_instance.commit()
        config = LayoutApplyConfig()
        config.load_log_configs()
        # act
        for pattern in multi_pattern:
            procedures = pattern[0]

            run(procedures, config, applyid)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=SELECT_SQL, vars=[applyid])
                init_db_instance.commit()
                row = cursor.fetchone()
            if row.get("status") == "IN_PROGRESS":
                assert row.get("status") == "IN_PROGRESS"
                for i in range(15):
                    sleep(0.5)
                    cursor.execute(query=SELECT_SQL, vars=[applyid])
                    init_db_instance.commit()
                    row = cursor.fetchone()
                    if row.get("status") != "IN_PROGRESS":
                        break

            # assert
            # status is SUSPENDED
            assert row.get("status") == "SUSPENDED"
            # execution results are dumped.
            details = row.get("applyresult")
            assert details is not None
            assert len(details) == len(procedures["procedures"])

            host = config.hardware_control.get("host")
            port = config.hardware_control.get("port")
            uri = config.hardware_control.get("uri")

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from
                # result details using operationID as a condition
                detail = [i for i in details if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                # initially executed task results in 'Failed', and all other tasks are marked as 'SKIPPED'
                if not procedure["dependencies"]:
                    assert "FAILED" == detail["status"]

                    match procedure["operation"]:
                        case "connect":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {
                                "action": "connect",
                                "deviceID": procedure["targetDeviceID"],
                            }
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                            assert detail["startedAt"] is not None
                            assert detail["endedAt"] is not None
                        case "disconnect":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {
                                "action": "disconnect",
                                "deviceID": procedure["targetDeviceID"],
                            }
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                            assert detail["startedAt"] is not None
                            assert detail["endedAt"] is not None
                        case "boot":
                            assert detail["requestBody"] == {"action": "on"}
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                            assert detail["startedAt"] is not None
                            assert detail["endedAt"] is not None
                        case "shutdown":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                            assert detail["startedAt"] is not None
                            assert detail["endedAt"] is not None
                        case "start":
                            assert re.fullmatch(
                                f"http:\/\/{WORKFLOW_MANAGER_HOST}:{WORKFLOW_MANAGER_PORT}\/{uri}\/{EXTENDED_PROCEDURE_URI}",
                                detail["uri"],
                            )
                            assert "POST" == detail["method"]
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                            assert detail["startedAt"] is not None
                            assert detail["endedAt"] is not None
                        case "stop":
                            assert re.fullmatch(
                                f"http:\/\/{WORKFLOW_MANAGER_HOST}:{WORKFLOW_MANAGER_PORT}\/{uri}\/{EXTENDED_PROCEDURE_URI}",
                                detail["uri"],
                            )
                            assert "POST" == detail["method"]
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                            assert detail["startedAt"] is not None
                            assert detail["endedAt"] is not None
                else:
                    assert "SKIPPED" == detail["status"]
                    assert "requestBody" not in detail
                    assert "uri" not in detail
                    assert "method" not in detail
                    assert "queryParameter" not in detail
                    assert "statusCode" not in detail
                    assert "responseBody" not in detail
                    assert "startedAt" not in detail
                    assert "endedAt" not in detail

        assert "Published message to topic " in caplog.text

    def test_run_status_canceled_when_true_cancel_flag_before_execution(self, init_db_instance, mocker, caplog):
        """"""
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.INFO)

        # arrange
        config = LayoutApplyConfig()
        config.load_log_configs()

        # act
        for pattern in single_pattern_cancel:
            procedures = pattern[0]
            applyid = create_randomname(IdParameter.LENGTH)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid])
                init_db_instance.commit()

            run(procedures, config, applyid)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=SELECT_SQL, vars=[applyid])
                init_db_instance.commit()
                row = cursor.fetchone()
            if row.get("status") == "IN_PROGRESS":
                assert row.get("status") == "IN_PROGRESS"
                for i in range(15):
                    sleep(0.5)
                    cursor.execute(query=SELECT_SQL, vars=[applyid])
                    init_db_instance.commit()
                    row = cursor.fetchone()
                    if row.get("status") != "IN_PROGRESS":
                        break
            # assert
            # result is CANCELED
            assert row.get("status") == "CANCELED"
            # execution results are dumped.
            details = row.get("applyresult")
            assert details is not None
            assert len(details) == len(procedures["procedures"])

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from the result details using operationID as a condition
                detail = [i for i in details if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                assert "CANCELED" == detail["status"]
                assert "requestBody" not in detail
                assert "uri" not in detail
                assert "method" not in detail
                assert "queryParameter" not in detail
                assert "statusCode" not in detail
                assert "responseBody" not in detail
                assert "startedAt" not in detail
                assert "endedAt" not in detail
        assert "Published message to topic " in caplog.text

    def test_run_status_canceled_when_true_cancel_flag_on_first_api_execution(
        self,
        httpserver: HTTPServer,
        init_db_instance,
        mocker,
    ):
        """"""
        # arrange
        param_list = [
            # no APIs to execute in parallel.
            {
                "procedures": [
                    {
                        "operationID": 1,
                        "operation": "boot",
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "shutdown",
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "disconnect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [2],
                    },
                    {
                        "operationID": 4,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [3],
                    },
                    {
                        "operationID": 5,
                        "operation": "start",
                        "targetCPUID": str(uuid4()),
                        "targetServiceID": str(uuid4()),
                        "dependencies": [4],
                    },
                    {
                        "operationID": 6,
                        "operation": "shutdown",
                        "targetCPUID": str(uuid4()),
                        "targetServiceID": str(uuid4()),
                        "dependencies": [5],
                    },
                ],
                "applyID": "234567890e",
            },
            {
                "procedures": [
                    {
                        "operationID": 1,
                        "operation": "boot",
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "shutdown",
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "disconnect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [1, 2],
                    },
                    {
                        "operationID": 4,
                        "operation": "disconnect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [3],
                    },
                    {
                        "operationID": 5,
                        "operation": "start",
                        "targetCPUID": str(uuid4()),
                        "targetServiceID": str(uuid4()),
                        "dependencies": [4],
                    },
                    {
                        "operationID": 6,
                        "operation": "shutdown",
                        "targetCPUID": str(uuid4()),
                        "targetServiceID": str(uuid4()),
                        "dependencies": [5],
                    },
                ],
                "applyID": "234567890f",
            },
        ]
        config = LayoutApplyConfig()
        config.load_log_configs()
        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")

        def change_cancel_request(request: Request):
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=CHANGE_CANCEL_SQL, vars=[applyid])
                init_db_instance.commit()
            return Response("", status=200)

        httpserver.expect_oneshot_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_handler(
            change_cancel_request
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_handler(
            change_cancel_request
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_handler(
            change_cancel_request
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_handler(
            change_cancel_request
        )
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(
            Response(
                response=b'{"type": "CPU", "powerState": "Off", "powerCapability": false}',
                status=200,
            )
        )

        # act
        for param in param_list:
            procedures = {"procedures": param["procedures"]}
            applyid = create_randomname(IdParameter.LENGTH)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
                init_db_instance.commit()

            run(procedures, config, applyid)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=SELECT_SQL, vars=[applyid])
                init_db_instance.commit()
                row = cursor.fetchone()
            if row.get("status") == "IN_PROGRESS":
                assert row.get("status") == "IN_PROGRESS"
                for i in range(15):
                    sleep(0.5)
                    cursor.execute(query=SELECT_SQL, vars=[applyid])
                    init_db_instance.commit()
                    row = cursor.fetchone()
                    if row.get("status") != "IN_PROGRESS":
                        break

            # assert
            assert row.get("status") == "CANCELED"
            details = row.get("applyresult")
            assert row.get("rollbackprocedures") is not None
            rollback_proc_list = row.get("rollbackprocedures")
            for r_proc in rollback_proc_list:
                assert "operationID" in r_proc
                assert "dependencies" in r_proc
                assert "operation" in r_proc
                if r_proc["operation"] in ("shutdown", "boot"):
                    assert "targetCPUID" not in r_proc
                    assert "targetServiceID" not in r_proc
                    assert "targetDeviceID" in r_proc
                if r_proc["operation"] in ("connect", "disconnect"):
                    assert "targetDeviceID" in r_proc
                    assert "targetCPUID" in r_proc
                    assert "targetServiceID" not in r_proc
                if r_proc["operation"] in ("start", "stop"):
                    assert "targetDeviceID" not in r_proc
                    assert "targetCPUID" in r_proc
                    assert "targetServiceID" in r_proc
            assert details is not None
            assert len(details) == len(procedures["procedures"])

            uri = config.hardware_control.get("uri")

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from the result details using operationID as a condition
                detail = [i for i in details if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                assert "status" in detail
                assert "queryParameter" not in detail
                assert "responseBody" not in detail
                if detail["status"] == "COMPLETED":
                    assert "uri" in detail
                    assert "method" in detail
                    assert "statusCode" in detail
                    assert "startedAt" in detail
                    assert "endedAt" in detail
                elif detail["status"] == "CANCELED":
                    assert "uri" not in detail
                    assert "method" not in detail
                    assert "statusCode" not in detail
                    assert "startedAt" not in detail
                    assert "endedAt" not in detail
        httpserver.clear()

    def test_run_status_not_canceled_when_true_cancel_flag_on_last_api_execution(
        self,
        httpserver: HTTPServer,
        init_db_instance,
        mocker,
    ):
        # arrange
        param_list = [
            # no APIs to execute in parallel.
            {
                "procedures": [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [],
                    },
                    {
                        "operationID": 4,
                        "operation": "disconnect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [1, 2, 3],
                    },
                ],
                "applyID": "234567890e",
            },
            {
                "procedures": [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [],
                    },
                    {
                        "operationID": 4,
                        "operation": "disconnect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [1, 2, 3],
                    },
                ],
                "applyID": "234567890f",
            },
        ]
        config = LayoutApplyConfig()
        config.load_log_configs()
        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")

        def change_cancel_request(request: Request):
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=CHANGE_CANCEL_SQL, vars=[applyid])
                init_db_instance.commit()
            return Response("", status=200)

        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_oneshot_request(
            re.compile(f"\/{uri}\/{OPERATION_URL}"),
            method="PUT",
            data='{"action":"disconnect","deviceID":' + param_list[0]["procedures"][3]["targetDeviceID"] + "}",
        ).respond_with_handler(change_cancel_request)
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(
            Response(
                response=b'{"type": "CPU", "powerState": "Off", "powerCapability": false}',
                status=200,
            )
        )

        # act
        for param in param_list:
            procedures = {"procedures": param["procedures"]}
            applyid = create_randomname(IdParameter.LENGTH)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
                init_db_instance.commit()
            run(procedures, config, applyid)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=SELECT_SQL, vars=[applyid])
                init_db_instance.commit()
                row = cursor.fetchone()
            if row.get("status") == "IN_PROGRESS":
                assert row.get("status") == "IN_PROGRESS"
                for i in range(15):
                    sleep(0.5)
                    cursor.execute(query=SELECT_SQL, vars=[applyid])
                    init_db_instance.commit()
                    row = cursor.fetchone()
                    if row.get("status") != "IN_PROGRESS":
                        break
            # assert
            assert row.get("status") == "COMPLETED"
            details = row.get("applyresult")
            assert details is not None
            assert len(details) == len(procedures["procedures"])
            uri = config.hardware_control.get("uri")

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure
                # from the result details using operationID as a condition
                detail = [i for i in details if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                # Check the URI, etc. of the hardware control API
                # Review the mockup method with hardwaremgr_fixture as well
                assert "COMPLETED" == detail["status"]
        httpserver.clear()

    def test_run_status_suspended_when_true_cancel_flag_on_api_failure(
        self,
        httpserver: HTTPServer,
        init_db_instance,
        mocker,
    ):
        # arrange
        param_list = [
            {
                "procedures": [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [],
                    },
                ],
                "applyID": "234567890e",
            },
            {
                "procedures": [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [2],
                    },
                ],
                "applyID": "234567890f",
            },
        ]
        config = LayoutApplyConfig()
        config.load_log_configs()

        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")

        def change_cancel_request(request: Request):
            if request.json["action"] == "disconnect":
                with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                    cursor.execute(query=SELECT_SQL, vars=[applyid])
                    init_db_instance.commit()
                    row = cursor.fetchone()
                if row.get("status") == "IN_PROGRESS":
                    cursor.execute(query=CHANGE_CANCEL_SQL, vars=[applyid])
                    init_db_instance.commit()
                return Response("", status=500)
            else:
                return Response("", status=200)

        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_handler(
            change_cancel_request
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(
            Response(
                response=b'{"type": "CPU", "powerState": "Off", "powerCapability": false}',
                status=200,
            )
        )

        for param in param_list:
            procedures = {"procedures": param["procedures"]}
            applyid = create_randomname(IdParameter.LENGTH)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
                init_db_instance.commit()
            # act
            run(procedures, config, applyid)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=SELECT_SQL, vars=[applyid])
                init_db_instance.commit()
                row = cursor.fetchone()
            if row.get("status") == "IN_PROGRESS":
                assert row.get("status") == "IN_PROGRESS"
                for i in range(15):
                    sleep(0.5)
                    cursor.execute(query=SELECT_SQL, vars=[applyid])
                    init_db_instance.commit()
                    row = cursor.fetchone()
                    if row.get("status") != "IN_PROGRESS":
                        break
            # assert
            assert row.get("status") == "SUSPENDED"
        httpserver.clear()

    def test_find_first_proc_returns_first_migration_plan(self):

        # multiple dependencies set as empty
        proc_list = [
            Procedure(
                operationID=1,
                targetDeviceID=uuid4(),
                operation=Operation.CONNECT,
                dependencies=[],
            ),
            Procedure(
                operationID=2,
                targetDeviceID=uuid4(),
                operation=Operation.CONNECT,
                dependencies=[1],
            ),
            Procedure(
                operationID=3,
                targetDeviceID=uuid4(),
                operation=Operation.CONNECT,
                dependencies=[],
            ),
            Procedure(
                operationID=4,
                targetDeviceID=uuid4(),
                operation=Operation.CONNECT,
                dependencies=[3],
            ),
        ]
        for proc in _find_first_proc(proc_list):
            assert proc.dependencies == []

        # single dependencies set as empty
        proc_list = [
            Procedure(
                operationID=1,
                targetDeviceID=uuid4(),
                operation=Operation.CONNECT,
                dependencies=[],
            ),
        ]
        for proc in _find_first_proc(proc_list):
            assert proc.dependencies == []

        # no dependencies set as empty
        cnt = 0
        proc_list = [
            Procedure(
                operationID=1,
                targetDeviceID=uuid4(),
                operation=Operation.POWEROFF,
                dependencies=[0],
            ),
            Procedure(
                operationID=2,
                targetDeviceID=uuid4(),
                operation=Operation.POWERON,
                dependencies=[1],
            ),
            Procedure(
                operationID=3,
                targetDeviceID=uuid4(),
                operation=Operation.POWEROFF,
                dependencies=[2],
            ),
            Procedure(
                operationID=4,
                targetDeviceID=uuid4(),
                operation=Operation.POWERON,
                dependencies=[3],
            ),
        ]
        for proc in _find_first_proc(proc_list):
            cnt += 1
        assert cnt == 0

    def test_find_next_proc_returns_next_migration_plan(self):
        # dependencies has one item.
        proc_list = [
            Procedure(
                operationID=5,
                targetDeviceID=uuid4(),
                operation=Operation.POWERON,
                dependencies=[4],
            ),
            Procedure(
                operationID=6,
                targetDeviceID=uuid4(),
                operation=Operation.POWERON,
                dependencies=[5],
            ),
            Procedure(
                operationID=7,
                targetDeviceID=uuid4(),
                operation=Operation.POWERON,
                dependencies=[6],
            ),
        ]
        executed_list = [
            Details(
                operationID=4,
            )
        ]
        for proc in _find_next_proc(executed_list, proc_list):
            assert proc.operationID == 5

        # dependencies has any items.
        proc_list = [
            Procedure(
                operationID=5,
                targetDeviceID=uuid4(),
                operation=Operation.CONNECT,
                dependencies=[4],
            ),
            Procedure(
                operationID=6,
                targetDeviceID=uuid4(),
                operation=Operation.DISCONNECT,
                dependencies=[2, 3],
            ),
            Procedure(
                operationID=7,
                targetDeviceID=uuid4(),
                operation=Operation.CONNECT,
                dependencies=[6],
            ),
        ]
        executed_list = [
            Details(operationID=2, status=Result.COMPLETED),
            Details(operationID=3, status=Result.COMPLETED),
        ]
        for proc in _find_next_proc(executed_list, proc_list):
            assert proc.operationID == 6

        # ID in 'dependencies' matches, it cannot be retrieved due to failure.
        proc_list = [
            Procedure(
                operationID=5,
                targetDeviceID=uuid4(),
                operation=Operation.CONNECT,
                dependencies=[4],
            ),
            Procedure(
                operationID=6,
                targetDeviceID=uuid4(),
                operation=Operation.DISCONNECT,
                dependencies=[2, 3],
            ),
            Procedure(
                operationID=7,
                targetDeviceID=uuid4(),
                operation=Operation.POWEROFF,
                dependencies=[6],
            ),
        ]
        executed_list = [
            Details(operationID=2, status=Result.COMPLETED),
            Details(operationID=3, status=Result.FAILED),
        ]
        cnt = 0
        for proc in _find_next_proc(executed_list, proc_list):
            cnt += 1
        assert cnt == 0

    def test_get_ids_fetch_id_by_condition(self):
        # Ensure that the ID for the specified status can be retrieved.
        executed_list = [
            Details(operationID=2, status=Result.COMPLETED),
            Details(operationID=3, status=Result.FAILED),
        ]
        assert [2] == _get_ids(executed_list, Result.COMPLETED)
        assert [3] == _get_ids(executed_list, Result.FAILED)

        executed_list = [
            Details(operationID=2, status=Result.COMPLETED),
            Details(operationID=3, status=Result.FAILED),
            Details(operationID=4, status=Result.COMPLETED),
            Details(operationID=5, status=Result.FAILED),
        ]
        assert [2, 4] == _get_ids(executed_list, Result.COMPLETED)
        assert [3, 5] == _get_ids(executed_list, Result.FAILED)

    def test_get_skip_ids_returns_skipped_migration_plan(self):
        # tracing back the dependencies
        failed_ids = [1]
        proc_list = [
            Procedure(
                operationID=2,
                targetDeviceID=uuid4(),
                operation=Operation.POWEROFF,
                dependencies=[1],
            ),
            Procedure(
                operationID=3,
                targetDeviceID=uuid4(),
                operation=Operation.POWERON,
                dependencies=[2],
            ),
            Procedure(
                operationID=4,
                targetDeviceID=uuid4(),
                operation=Operation.CONNECT,
                dependencies=[3],
            ),
        ]
        assert [2, 3, 4] == _get_skip_ids(proc_list, failed_ids)
        # unrelated ID(5) not get.
        # dependencies match, it is detected as a target to be skipped.
        failed_ids = [1]
        proc_list = [
            Procedure(
                operationID=2,
                targetDeviceID=uuid4(),
                operation=Operation.CONNECT,
                dependencies=[1],
            ),
            Procedure(
                operationID=3,
                targetDeviceID=uuid4(),
                operation=Operation.POWEROFF,
                dependencies=[1, 2],
            ),
            Procedure(
                operationID=4,
                targetDeviceID=uuid4(),
                operation=Operation.DISCONNECT,
                dependencies=[1, 2, 3],
            ),
            Procedure(
                operationID=5,
                targetDeviceID=uuid4(),
                operation=Operation.POWERON,
                dependencies=[6],
            ),
        ]

        assert [2, 3, 4] == _get_skip_ids(proc_list, failed_ids)

    def test_create_task_create_task(self):
        with ProcessPoolExecutor() as executor:
            config = LayoutApplyConfig()
            config.workflow_manager["timeout"] = 3
            # specified type, a task (Future class) is generated.
            applyid = create_randomname(IdParameter.LENGTH)
            procedure = Procedure(
                operationID=1,
                targetDeviceID=uuid4(),
                operation=Operation.CONNECT,
                dependencies=[1],
            )
            assert isinstance(_create_task(procedure, executor, config, applyid), Future)

            procedure = Procedure(
                operationID=1,
                targetDeviceID=uuid4(),
                operation=Operation.DISCONNECT,
                dependencies=[1],
            )
            assert isinstance(_create_task(procedure, executor, config, applyid), Future)

            procedure = Procedure(
                operationID=1,
                targetDeviceID=uuid4(),
                operation=Operation.POWERON,
                dependencies=[1],
            )
            assert isinstance(_create_task(procedure, executor, config, applyid), Future)

            procedure = Procedure(
                operationID=1,
                targetDeviceID=uuid4(),
                operation=Operation.POWEROFF,
                dependencies=[1],
            )
            assert isinstance(_create_task(procedure, executor, config, applyid), Future)

            procedure = Procedure(
                operationID=1,
                targetCPUID=uuid4(),
                targetServiceID=uuid4(),
                operation=Operation.START,
                dependencies=[1],
            )
            assert isinstance(_create_task(procedure, executor, config, applyid), Future)

            procedure = Procedure(
                operationID=1,
                targetCPUID=uuid4(),
                targetServiceID=uuid4(),
                operation=Operation.STOP,
                dependencies=[1],
            )
            assert isinstance(_create_task(procedure, executor, config, applyid), Future)

            # error is raised in the case of an unknown operation.
            with pytest.raises(Exception):
                procedure = Procedure(
                    operationID=1,
                    targetDeviceID=uuid4(),
                    operation="dummy",
                    dependencies=[1],
                )
                assert isinstance(_create_task(procedure, executor, config, applyid), Future)

    @pytest.mark.parametrize(
        "procedure, expected_operation",
        [
            (
                {
                    "operationID": 1,
                    "operation": "connect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                },
                Operation.DISCONNECT,
            ),
            (
                {
                    "operationID": 1,
                    "operation": "disconnect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                },
                Operation.CONNECT,
            ),
            (
                {
                    "operationID": 1,
                    "operation": "boot",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                },
                Operation.POWEROFF,
            ),
            (
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                },
                Operation.POWERON,
            ),
            (
                {
                    "operationID": 1,
                    "operation": "start",
                    "targetCPUID": str(uuid4()),
                    "targetServiceID": str(uuid4()),
                    "dependencies": [],
                },
                Operation.STOP,
            ),
            (
                {
                    "operationID": 1,
                    "operation": "stop",
                    "targetCPUID": str(uuid4()),
                    "targetServiceID": str(uuid4()),
                    "dependencies": [],
                },
                Operation.START,
            ),
            (
                # unexpected string is not converted
                {
                    "operationID": 1,
                    "operation": "shutdowns",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                },
                "shutdowns",
            ),
        ],
    )
    def test_change_operation_convert_control_type(self, procedure, expected_operation):
        proc = Procedure(**procedure)
        _change_operation(proc)
        assert proc.operation == str(expected_operation)

    @pytest.mark.parametrize(
        "target_procedure, procedure",
        [
            (
                # dependencies is single
                {
                    "operationID": 1,
                    "operation": "connect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                },
                {
                    "operationID": 2,
                    "operation": "connect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [1],
                },
            ),
            (
                # dependencies is multi
                {
                    "operationID": 1,
                    "operation": "connect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [3, 4],
                },
                {
                    "operationID": 2,
                    "operation": "connect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [1, 3, 4],
                },
            ),
        ],
    )
    def test_swap_execution_order_swap_execution_order(self, target_procedure, procedure):
        proc = Procedure(**procedure)
        target_proc = Procedure(**target_procedure)
        assert target_proc.operationID in proc.dependencies
        assert proc.operationID not in target_proc.dependencies
        _swap_execution_order(target_proc, proc)
        # operation IDs of the rollback target migration steps are removed
        # from the detected migration steps' dependencies.
        assert target_proc.operationID not in proc.dependencies
        # operation ID of the detected migration step is added
        # to the dependencies of the rollback target migration steps.
        assert proc.operationID in target_proc.dependencies

    @pytest.mark.parametrize(
        "target_procedure_list, expected_id_list",
        [
            (
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [3],  # delete
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [1],
                    },
                ],
                [1],
            ),
            (
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [5],  # delete
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [4],  # delete
                    },
                ],
                [1, 3],
            ),
        ],
    )
    def test_clear_dependencies_clear_dependencies(
        self,
        target_procedure_list,
        expected_id_list,
    ):
        target_proc_list = [Procedure(**i) for i in target_procedure_list]
        _clear_dependencies(target_proc_list)
        # operation IDs of the rollback target migration steps are removed
        # from the dependencies of the detected migration steps.
        for target_proc in target_proc_list:
            if target_proc.operationID in expected_id_list:
                assert len(target_proc.dependencies) == 0
            else:
                assert len(target_proc.dependencies) > 0

    @pytest.mark.parametrize(
        "procedure_list, executed_list",
        [
            (
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [3],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [2],
                    },
                ],
                [
                    Details(operationID=1, status=Result.COMPLETED),
                    Details(operationID=2, status=Result.FAILED),
                    Details(operationID=3, status=Result.CANCELED),
                ],
            ),
            (
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [3],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [2],
                    },
                ],
                [
                    Details(operationID=1, status=Result.COMPLETED),
                    Details(operationID=2, status=Result.FAILED),
                    Details(operationID=3, status=Result.COMPLETED),
                ],
            ),
            (
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [3],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [2],
                    },
                ],
                [
                    Details(operationID=1, status=Result.FAILED),
                    Details(operationID=2, status=Result.COMPLETED),
                    Details(operationID=3, status=Result.CANCELED),
                ],
            ),
            # no rollback target
            (
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [3],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [2],
                    },
                ],
                [
                    Details(operationID=1, status=Result.FAILED),
                    Details(operationID=2, status=Result.FAILED),
                    Details(operationID=3, status=Result.CANCELED),
                ],
            ),
            ([], []),
            ([], [Details(operationID=1, status=Result.FAILED)]),
            (
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": str(uuid4()),
                        "targetDeviceID": str(uuid4()),
                        "dependencies": [3],
                    }
                ],
                [],
            ),
        ],
    )
    def test_get_rollback_target_proc_fetch_rollback_target(self, procedure_list, executed_list):
        proc_list = [Procedure(**i) for i in procedure_list]
        target_proc_list = _get_rollback_target_proc(proc_list, executed_list)
        completed_id_list = [i.operationID for i in executed_list if i.status == Result.COMPLETED]
        assert len(completed_id_list) == len(target_proc_list)
        for target_proc in target_proc_list:
            assert target_proc.operationID in completed_id_list

    @pytest.mark.parametrize(
        "target_procedure_list, expected_rollback_list",
        [
            (
                # asc
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [2],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [3],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [2],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
            ),
            (
                # pararell
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [2],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
            ),
            (
                # asc.multiple initial step
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [1, 2, 3],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
            ),
            (
                # asc.multiple final steps
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [1],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [2, 3, 4],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
            ),
            (
                # asc.branching in the middle
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [2, 3],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [2, 3],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
            ),
            (
                # parallel.multiple initial steps
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [1, 2],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
            ),
            (
                # parallel.multiple final steps
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [1, 2],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
            ),
            (
                # parallel.branching in the middle
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [2, 3],
                    },
                    {
                        "operationID": 5,
                        "operation": "disconnect",
                        "targetCPUID": "5-1",
                        "targetDeviceID": "5-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 6,
                        "operation": "boot",
                        "targetDeviceID": "6-1",
                        "dependencies": [5],
                    },
                    {
                        "operationID": 7,
                        "operation": "shutdown",
                        "targetDeviceID": "7-2",
                        "dependencies": [6, 4],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [2, 3],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [7],
                    },
                    {
                        "operationID": 5,
                        "operation": "connect",
                        "targetCPUID": "5-1",
                        "targetDeviceID": "5-2",
                        "dependencies": [6],
                    },
                    {
                        "operationID": 6,
                        "operation": "shutdown",
                        "targetDeviceID": "6-1",
                        "dependencies": [7],
                    },
                    {
                        "operationID": 7,
                        "operation": "boot",
                        "targetDeviceID": "7-2",
                        "dependencies": [],
                    },
                ],
            ),
            (
                # element order does not match operation ID
                [
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [2],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [2],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
            ),
        ],
    )
    def test_convert_to_rollback_swap_order_and_convert_control_type(
        self, target_procedure_list, expected_rollback_list
    ):
        target_proc_list = [Procedure(**i) for i in target_procedure_list]
        rollback_list = [Procedure(**i) for i in expected_rollback_list]
        result_list = []
        for _ in range(len(target_proc_list)):
            target_proc = target_proc_list.pop()
            _convert_to_rollback(target_proc, target_proc_list)
            result_list.append(target_proc)
        assert len(rollback_list) == len(result_list)
        result_list = sorted(result_list, key=lambda i: i.operationID)
        rollback_list = sorted(rollback_list, key=lambda i: i.operationID)
        for tmp in result_list:
            tmp.dependencies = sorted(tmp.dependencies)
        for tmp in rollback_list:
            tmp.dependencies = sorted(tmp.dependencies)
        assert result_list == rollback_list

    @pytest.mark.parametrize(
        "target_procedure_list, expected_rollback_list, executed_list",
        [
            (
                # asc
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [2],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 5,
                        "operation": "shutdown",
                        "targetDeviceID": "5-2",
                        "dependencies": [4],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [2],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
                [
                    Details(operationID=1, status=Result.COMPLETED),
                    Details(operationID=2, status=Result.COMPLETED),
                    Details(operationID=3, status=Result.COMPLETED),
                    Details(operationID=4, status=Result.COMPLETED),
                    Details(operationID=5, status=Result.CANCELED),
                ],
            ),
            (
                # pararell
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [2],
                    },
                    {
                        "operationID": 5,
                        "operation": "boot",
                        "targetDeviceID": "5-1",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 6,
                        "operation": "shutdown",
                        "targetDeviceID": "6-2",
                        "dependencies": [4],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
                [
                    Details(operationID=1, status=Result.COMPLETED),
                    Details(operationID=2, status=Result.COMPLETED),
                    Details(operationID=3, status=Result.COMPLETED),
                    Details(operationID=4, status=Result.COMPLETED),
                    Details(operationID=5, status=Result.CANCELED),
                    Details(operationID=6, status=Result.CANCELED),
                ],
            ),
            (
                # asc: Multiple initial steps
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [1, 2, 3],
                    },
                    {
                        "operationID": 5,
                        "operation": "shutdown",
                        "targetDeviceID": "5-2",
                        "dependencies": [4],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
                [
                    Details(operationID=1, status=Result.COMPLETED),
                    Details(operationID=2, status=Result.COMPLETED),
                    Details(operationID=3, status=Result.COMPLETED),
                    Details(operationID=4, status=Result.COMPLETED),
                    Details(operationID=5, status=Result.CANCELED),
                ],
            ),
            (
                # asc: Multiple final steps
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [1, 6],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [1, 5],
                    },
                    {
                        "operationID": 5,
                        "operation": "shutdown",
                        "targetDeviceID": "5-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 6,
                        "operation": "shutdown",
                        "targetDeviceID": "6-2",
                        "dependencies": [],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [2, 3, 4],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
                [
                    Details(operationID=1, status=Result.COMPLETED),
                    Details(operationID=2, status=Result.COMPLETED),
                    Details(operationID=3, status=Result.COMPLETED),
                    Details(operationID=4, status=Result.COMPLETED),
                    Details(operationID=5, status=Result.FAILED),
                    Details(operationID=6, status=Result.CANCELED),
                ],
            ),
            (
                # asc.branching in the middle
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [5, 6, 2, 3],
                    },
                    {
                        "operationID": 5,
                        "operation": "disconnect",
                        "targetCPUID": "5-1",
                        "targetDeviceID": "5-2",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 6,
                        "operation": "boot",
                        "targetDeviceID": "6-1",
                        "dependencies": [1],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [2, 3],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
                [
                    Details(operationID=1, status=Result.COMPLETED),
                    Details(operationID=2, status=Result.COMPLETED),
                    Details(operationID=3, status=Result.COMPLETED),
                    Details(operationID=4, status=Result.COMPLETED),
                    Details(operationID=5, status=Result.FAILED),
                    Details(operationID=6, status=Result.CANCELED),
                ],
            ),
            (
                # parallel.multiple initial steps
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [1, 2, 5, 6],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 5,
                        "operation": "disconnect",
                        "targetCPUID": "5-1",
                        "targetDeviceID": "5-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 6,
                        "operation": "boot",
                        "targetDeviceID": "6-1",
                        "dependencies": [],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
                [
                    Details(operationID=1, status=Result.COMPLETED),
                    Details(operationID=2, status=Result.COMPLETED),
                    Details(operationID=3, status=Result.COMPLETED),
                    Details(operationID=4, status=Result.COMPLETED),
                    Details(operationID=5, status=Result.FAILED),
                    Details(operationID=6, status=Result.CANCELED),
                ],
            ),
            (
                # parallel.multiple final steps
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [1, 2, 5],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 5,
                        "operation": "shutdown",
                        "targetDeviceID": "5-2",
                        "dependencies": [2],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
                [
                    Details(operationID=1, status=Result.COMPLETED),
                    Details(operationID=2, status=Result.COMPLETED),
                    Details(operationID=3, status=Result.COMPLETED),
                    Details(operationID=4, status=Result.COMPLETED),
                    Details(operationID=5, status=Result.CANCELED),
                ],
            ),
            (
                # parallel.branching in the middle
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [2, 3],
                    },
                    {
                        "operationID": 5,
                        "operation": "disconnect",
                        "targetCPUID": "5-1",
                        "targetDeviceID": "5-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 6,
                        "operation": "boot",
                        "targetDeviceID": "6-1",
                        "dependencies": [5],
                    },
                    {
                        "operationID": 7,
                        "operation": "shutdown",
                        "targetDeviceID": "7-2",
                        "dependencies": [6, 4],
                    },
                    {
                        "operationID": 8,
                        "operation": "shutdown",
                        "targetDeviceID": "8-2",
                        "dependencies": [6, 4],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [2, 3],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [7],
                    },
                    {
                        "operationID": 5,
                        "operation": "connect",
                        "targetCPUID": "5-1",
                        "targetDeviceID": "5-2",
                        "dependencies": [6],
                    },
                    {
                        "operationID": 6,
                        "operation": "shutdown",
                        "targetDeviceID": "6-1",
                        "dependencies": [7],
                    },
                    {
                        "operationID": 7,
                        "operation": "boot",
                        "targetDeviceID": "7-2",
                        "dependencies": [],
                    },
                ],
                [
                    Details(operationID=1, status=Result.COMPLETED),
                    Details(operationID=2, status=Result.COMPLETED),
                    Details(operationID=3, status=Result.COMPLETED),
                    Details(operationID=4, status=Result.COMPLETED),
                    Details(operationID=5, status=Result.COMPLETED),
                    Details(operationID=6, status=Result.COMPLETED),
                    Details(operationID=7, status=Result.COMPLETED),
                    Details(operationID=8, status=Result.CANCELED),
                ],
            ),
            (
                # element order does not match operation ID
                [
                    {
                        "operationID": 4,
                        "operation": "shutdown",
                        "targetDeviceID": "4-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 5,
                        "operation": "disconnect",
                        "targetCPUID": "5-1",
                        "targetDeviceID": "5-2",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [2],
                    },
                ],
                # Expected rollback procedure
                [
                    {
                        "operationID": 1,
                        "operation": "disconnect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [2],
                    },
                    {
                        "operationID": 2,
                        "operation": "connect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [3],
                    },
                    {
                        "operationID": 3,
                        "operation": "shutdown",
                        "targetDeviceID": "3-1",
                        "dependencies": [4],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-2",
                        "dependencies": [],
                    },
                ],
                [
                    Details(operationID=1, status=Result.COMPLETED),
                    Details(operationID=2, status=Result.COMPLETED),
                    Details(operationID=3, status=Result.COMPLETED),
                    Details(operationID=4, status=Result.COMPLETED),
                    Details(operationID=5, status=Result.CANCELED),
                ],
            ),
        ],
    )
    def test_create_rollback_proc_create_rollback_procedure(
        self, target_procedure_list, expected_rollback_list, executed_list
    ):
        target_proc_list = [Procedure(**i) for i in target_procedure_list]
        rollback_list = [Procedure(**i) for i in expected_rollback_list]
        result_list = _create_rollback_proc(target_proc_list, executed_list)
        result_list = sorted(result_list, key=lambda i: i.operationID)
        rollback_list = sorted(rollback_list, key=lambda i: i.operationID)
        for tmp in result_list:
            tmp.dependencies = sorted(tmp.dependencies)
        for tmp in rollback_list:
            tmp.dependencies = sorted(tmp.dependencies)
        assert result_list == rollback_list

    def test_run_failure_when_failure_on_db_update(
        self,
        mocker,
    ):
        # arrange
        config = LayoutApplyConfig()
        config.load_log_configs()
        mock_cursor = mocker.MagicMock()
        # mock_cursor.execute.side_effect = [psycopg2.ProgrammingError]
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

        # act
        pattern = single_pattern[0]
        procedures = pattern[0]
        applyID = pattern[2]  # pylint: disable=C0103

        run(procedures, config, applyID)
        assert mock_cursor.execute.call_count == 1

    def test_update_layoutapply_rollback_when_auto_rollback_selected(
        self,
        httpserver: HTTPServer,
        init_db_instance,
    ):
        # arrange
        base_procedures = {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "disconnect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                },
                {
                    "operationID": 2,
                    "operation": "shutdown",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [1],
                },
                {
                    "operationID": 3,
                    "operation": "connect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [2],
                },
                {
                    "operationID": 4,
                    "operation": "disconnect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [3],
                },
            ],
            "applyID": "234567890e",
        }
        executed_list = [
            Details(operationID=1, status=Result.COMPLETED),
            Details(operationID=2, status=Result.COMPLETED),
            Details(operationID=3, status=Result.CANCELED),
            Details(operationID=4, status=Result.CANCELED),
        ]
        origin_proc_list: list[Procedure] = get_procedure_list(base_procedures)
        config = LayoutApplyConfig()
        config.load_log_configs()
        logger = Logger(config.log_config)
        database = DbAccess(logger)

        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_json(
            {"type": "CPU", "powerState": "Off", "powerCapability": False},
            status=200,
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )

        procedures = {"procedures": base_procedures["procedures"]}
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
            init_db_instance.commit()
        # act
        # rollback_status, rollback_result = _update_layoutapply(
        _update_layoutapply(
            executed_list,
            origin_proc_list,
            applyid,
            procedures,
            logger,
            config,
            True,
            database,
            False,
            Action.REQUEST,
        )
        # assert
        # assert rollback_status == "COMPLETED"
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()
        assert row.get("status") == Result.CANCELED
        assert row.get("rollbackstatus") == Result.COMPLETED
        httpserver.clear()

    def test_update_layoutapply_rollback_state_suspended_when_failure_on_rollback(
        self,
        httpserver: HTTPServer,
        init_db_instance,
    ):
        # Data adjustment before testing.
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        cursor.execute(
            query="""
                INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
                )
                VALUES 
                ('310000001a','IN_PROGRESS',null,null,null,'2023/10/02 00:00:00',null,null,null,null,null,null,null,null,null,null,null,null,null,null);
            """
        )
        init_db_instance.commit()
        # arrange
        base_procedures = {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "disconnect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                },
                {
                    "operationID": 2,
                    "operation": "shutdown",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [1],
                },
                {
                    "operationID": 3,
                    "operation": "connect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [2],
                },
                {
                    "operationID": 4,
                    "operation": "disconnect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [3],
                },
            ],
            "applyID": "310000001a",
        }
        executed_list = [
            Details(operationID=1, status=Result.COMPLETED),
            Details(operationID=2, status=Result.COMPLETED),
            Details(operationID=3, status=Result.CANCELED),
            Details(operationID=4, status=Result.CANCELED),
        ]
        origin_proc_list: list[Procedure] = get_procedure_list(base_procedures)
        config = LayoutApplyConfig()
        config.load_log_configs()
        logger = Logger(config.log_config)
        database = DbAccess(logger)

        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_json(
            {"type": "CPU", "powerState": "Off", "powerCapability": False},
            status=200,
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=500)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )

        procedures = {"procedures": base_procedures["procedures"]}
        applyID = base_procedures["applyID"]  # pylint: disable=C0103
        # act
        # rollback_status, rollback_result = _update_layoutapply(
        _update_layoutapply(
            executed_list,
            origin_proc_list,
            applyID,
            procedures,
            logger,
            config,
            True,
            database,
            False,
            Action.REQUEST,
        )
        # assert
        # assert rollback_status == "SUSPENDED"
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyID}'")
            init_db_instance.commit()
            row = cursor.fetchone()
            assert row.get("status") == Result.CANCELED
            assert row.get("rollbackstatus") == Result.SUSPENDED
            cursor.execute(query=f"DELETE FROM applystatus WHERE applyid = '{applyID}';")
            init_db_instance.commit()
        httpserver.clear()

    @pytest.mark.usefixtures("hardwaremgr_fixture")
    def test_cancel_run_status_completed_when_single_migration_step(
        self,
        get_db_instance,
        init_db_instance,
    ):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid])
        init_db_instance.commit()
        config = LayoutApplyConfig()
        config.load_log_configs()
        # act
        for pattern in single_pattern:
            procedures = pattern[0]

            executed_list, _ = _cancel_run(
                applyid, procedures, get_db_instance, config, Logger(config.log_config), Action.REQUEST
            )
            applyresult = [asdict(i, dict_factory=details_dict_factory) for i in executed_list]

            # assert
            assert applyresult is not None
            assert len(applyresult) == len(procedures["procedures"])

            host = config.hardware_control.get("host")
            port = config.hardware_control.get("port")
            uri = config.hardware_control.get("uri")

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from
                # result details using operationID as a condition
                detail = [i for i in applyresult if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                assert "COMPLETED" == detail["status"]
                # Check the URI, etc. of the hardware control API
                # Review the mockup method with hardwaremgr_fixture as well

                assert "queryParameter" not in detail
                match procedure["operation"]:
                    case "connect":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {
                            "action": "connect",
                            "deviceID": procedure["targetDeviceID"],
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
                            "deviceID": procedure["targetDeviceID"],
                        }
                        assert 200 == detail["statusCode"]

                    case "boot":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {"action": "on"}
                        assert 200 == detail["statusCode"]

                    case "shutdown":
                        # assert re.fullmatch(
                        #     f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                        #     detail["uri"],
                        # )
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

    @pytest.mark.usefixtures("hardwaremgr_fixture", "extended_procedure_fixture")
    def test_cancel_run_status_completed_when_multiple_migration_steps(
        self,
        get_db_instance,
        init_db_instance,
    ):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid])
        init_db_instance.commit()
        config = LayoutApplyConfig()
        config.load_log_configs()
        config.workflow_manager["host"] = "localhost"

        # act
        for pattern in multi_pattern:
            procedures = pattern[0]
            executed_list, _ = _cancel_run(
                applyid, procedures, get_db_instance, config, Logger(config.log_config), Action.REQUEST
            )
            applyresult = [asdict(i, dict_factory=details_dict_factory) for i in executed_list]

            # assert
            assert applyresult is not None
            assert len(applyresult) == len(procedures["procedures"])

            host = config.hardware_control.get("host")
            port = config.hardware_control.get("port")
            uri = config.hardware_control.get("uri")

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from
                # result details using operationID as a condition
                detail = [i for i in applyresult if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                assert "COMPLETED" == detail["status"]
                # Check the URI, etc. of the hardware control API
                # Review the mockup method with hardwaremgr_fixture as well

                match procedure["operation"]:
                    case "connect":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {
                            "action": "connect",
                            "deviceID": procedure["targetDeviceID"],
                        }
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "disconnect":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {
                            "action": "disconnect",
                            "deviceID": procedure["targetDeviceID"],
                        }
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "boot":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {"action": "on"}
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "shutdown":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

    @pytest.mark.usefixtures("hardwaremgr_fixture", "extended_procedure_fixture")
    def test_cancel_run_status_completed_when_multiple_migration_steps_setting_valid_max_workers(
        self,
        get_db_instance,
        init_db_instance,
    ):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid])
        init_db_instance.commit()
        config = LayoutApplyConfig()
        config.load_log_configs()
        del config.layout_apply["request"]
        config.workflow_manager["host"] = "localhost"
        # act
        for pattern in multi_pattern:
            procedures = pattern[0]
            executed_list, _ = _cancel_run(
                applyid, procedures, get_db_instance, config, Logger(config.log_config), Action.REQUEST
            )
            applyresult = [asdict(i, dict_factory=details_dict_factory) for i in executed_list]

            # assert
            assert applyresult is not None
            assert len(applyresult) == len(procedures["procedures"])

            host = config.hardware_control.get("host")
            port = config.hardware_control.get("port")
            uri = config.hardware_control.get("uri")

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from
                # result details using operationID as a condition
                detail = [i for i in applyresult if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                assert "COMPLETED" == detail["status"]
                # Check the URI, etc. of the hardware control API
                # Review the mockup method with hardwaremgr_fixture as well

                match procedure["operation"]:
                    case "connect":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {
                            "action": "connect",
                            "deviceID": procedure["targetDeviceID"],
                        }
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "disconnect":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {
                            "action": "disconnect",
                            "deviceID": procedure["targetDeviceID"],
                        }
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "boot":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert detail["requestBody"] == {"action": "on"}
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

                    case "shutdown":
                        assert re.fullmatch(
                            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            detail["uri"],
                        )
                        assert "PUT" == detail["method"]
                        assert "queryParameter" not in detail
                        assert 200 == detail["statusCode"]
                        assert detail["startedAt"] is not None
                        assert detail["endedAt"] is not None

    def test_cancel_run_status_failed_when_migration_step_failed(
        self, get_db_instance, init_db_instance, httpserver: HTTPServer
    ):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid])
        init_db_instance.commit()
        config = LayoutApplyConfig()
        config.load_log_configs()
        uri = config.hardware_control.get("uri")

        err_msg = {"code": "xxxx", "message": "Internal Server Error."}
        err_code = 500
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_json(
            err_msg, status=err_code
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_json(
            err_msg, status=err_code
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_json(
            err_msg, status=err_code
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_json(
            err_msg, status=err_code
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_json(
            err_msg, status=err_code
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU", "powerState": "Off", "powerCapability": False},
            status=200,
        )
        # act
        for pattern in single_pattern:
            procedures = pattern[0]
            executed_list, _ = _cancel_run(
                applyid, procedures, get_db_instance, config, Logger(config.log_config), Action.REQUEST
            )
            applyresult = [asdict(i, dict_factory=details_dict_factory) for i in executed_list]

            # assert
            assert applyresult is not None
            assert len(applyresult) == len(procedures["procedures"])

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from
                # result details using operationID as a condition
                detail = [i for i in applyresult if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                assert "FAILED" == detail["status"]
                assert detail["statusCode"] == 500
                assert detail["method"] == "PUT"
                assert detail["responseBody"] == {
                    "code": "xxxx",
                    "message": "Internal Server Error.",
                }
                assert detail["startedAt"] is not None
                assert detail["endedAt"] is not None
        httpserver.clear()

    @pytest.mark.usefixtures("hardwaremgr_error_fixture")
    def test_cancel_run_status_failed_when_failed_single_migration_step(
        self,
        get_db_instance,
        init_db_instance,
    ):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid])
        init_db_instance.commit()
        config = LayoutApplyConfig()
        config.load_log_configs()
        # act
        for pattern in single_pattern:
            procedures = pattern[0]
            executed_list, _ = _cancel_run(
                applyid, procedures, get_db_instance, config, Logger(config.log_config), Action.REQUEST
            )
            applyresult = [asdict(i, dict_factory=details_dict_factory) for i in executed_list]

            # assert
            assert applyresult is not None
            assert len(applyresult) == len(procedures["procedures"])

            host = config.hardware_control.get("host")
            port = config.hardware_control.get("port")
            uri = config.hardware_control.get("uri")

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from
                # result details using operationID as a condition
                detail = [i for i in applyresult if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                # initially executed task results in 'Failed', and all other tasks are marked as 'SKIPPED'
                if not procedure["dependencies"]:
                    assert "FAILED" == detail["status"]

                    match procedure["operation"]:
                        case "connect":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {
                                "action": "connect",
                                "deviceID": procedure["targetDeviceID"],
                            }
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                        case "disconnect":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {
                                "action": "disconnect",
                                "deviceID": procedure["targetDeviceID"],
                            }
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                        case "boot":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {"action": "on"}
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                        case "shutdown":
                            # assert re.fullmatch(
                            #     f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            #     detail["uri"],
                            # )
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]

    @pytest.mark.usefixtures("hardwaremgr_error_fixture")
    def test_cancel_run_status_failed_when_failed_multiple_migration_steps(
        self,
        get_db_instance,
        init_db_instance,
    ):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid])
        init_db_instance.commit()
        config = LayoutApplyConfig()
        config.load_log_configs()
        # act
        for pattern in multi_pattern:
            procedures = pattern[0]
            executed_list, _ = _cancel_run(
                applyid, procedures, get_db_instance, config, Logger(config.log_config), Action.REQUEST
            )
            applyresult = [asdict(i, dict_factory=details_dict_factory) for i in executed_list]

            # assert
            assert applyresult is not None
            assert len(applyresult) == len(procedures["procedures"])

            host = config.hardware_control.get("host")
            port = config.hardware_control.get("port")
            uri = config.hardware_control.get("uri")

            for procedure in procedures["procedures"]:
                # Search for items corresponding to the migration procedure from
                # result details using operationID as a condition
                detail = [i for i in applyresult if i["operationID"] == procedure["operationID"]][0]
                assert procedure["operationID"] == detail["operationID"]
                # initially executed task results in 'Failed', and all other tasks are marked as 'SKIPPED'
                if not procedure["dependencies"]:
                    assert "FAILED" == detail["status"]

                    match procedure["operation"]:
                        case "connect":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {
                                "action": "connect",
                                "deviceID": procedure["targetDeviceID"],
                            }
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                            assert detail["startedAt"] is not None
                            assert detail["endedAt"] is not None
                        case "disconnect":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {
                                "action": "disconnect",
                                "deviceID": procedure["targetDeviceID"],
                            }
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                            assert detail["startedAt"] is not None
                            assert detail["endedAt"] is not None
                        case "boot":
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert detail["requestBody"] == {"action": "on"}
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                            assert detail["startedAt"] is not None
                            assert detail["endedAt"] is not None
                        case "shutdown":
                            # assert re.fullmatch(
                            #     f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                            #     detail["uri"],
                            # )
                            assert re.fullmatch(
                                f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
                                detail["uri"],
                            )
                            assert "PUT" == detail["method"]
                            assert "queryParameter" not in detail
                            assert 500 == detail["statusCode"]
                            assert {
                                "code": "xxxx",
                                "message": "Internal Server Error.",
                            } == detail["responseBody"]
                            assert detail["startedAt"] is not None
                            assert detail["endedAt"] is not None
                else:
                    assert "SKIPPED" == detail["status"]
                    assert "requestBody" not in detail
                    assert "uri" not in detail
                    assert "method" not in detail
                    assert "queryParameter" not in detail
                    assert "statusCode" not in detail
                    assert "responseBody" not in detail
                    assert "startedAt" not in detail
                    assert "endedAt" not in detail

    def test_update_layoutapply_success_when_resume(
        self,
        httpserver: HTTPServer,
        init_db_instance,
        mocker,
    ):
        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="""
                INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
                )
                VALUES 
                ('300000009d','SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,null,null,null,null,null,null,'{"procedures": [{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]}',null,null,null,null,'2023/10/02 12:23:59',null);
            """
            )
            init_db_instance.commit()
        # arrange
        base_procedures = {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "disconnect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                },
                {
                    "operationID": 2,
                    "operation": "shutdown",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [1],
                },
                {
                    "operationID": 3,
                    "operation": "connect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [2],
                },
                {
                    "operationID": 4,
                    "operation": "disconnect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [3],
                },
            ],
            "applyID": "300000009d",
        }
        executed_list = [
            Details(operationID=1, status=Result.COMPLETED),
            Details(operationID=2, status=Result.COMPLETED),
            Details(operationID=3, status=Result.COMPLETED),
            Details(operationID=4, status=Result.COMPLETED),
        ]
        origin_proc_list: list[Procedure] = get_procedure_list(base_procedures)
        config = LayoutApplyConfig()
        config.load_log_configs()
        logger = Logger(config.log_config)
        database = DbAccess(logger)

        uri = config.hardware_control.get("uri")

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

        procedures = {"procedures": base_procedures["procedures"]}
        applyID = base_procedures["applyID"]  # pylint: disable=C0103
        # act
        _update_layoutapply(
            executed_list,
            origin_proc_list,
            applyID,
            procedures,
            logger,
            config,
            False,
            database,
            False,
            Action.RESUME,
        )
        # assert
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyID}'")
            init_db_instance.commit()
            row = cursor.fetchone()
        assert row.get("status") == Result.COMPLETED
        assert row.get("resumeresult") == [
            {"operationID": 1, "status": "COMPLETED"},
            {"operationID": 2, "status": "COMPLETED"},
            {"operationID": 3, "status": "COMPLETED"},
            {"operationID": 4, "status": "COMPLETED"},
        ]

        httpserver.clear()

    def test_update_layoutapply_success_when_resume_rollback(
        self,
        httpserver: HTTPServer,
        init_db_instance,
        mocker,
    ):
        """"""
        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="""
                INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
                )
                VALUES 
                ('300000022b','CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]','{"test": "pre_test"}','2023/10/02 00:00:00','2023/10/02 01:00:00','2023/10/02 00:30:00',TRUE,'SUSPENDED',null,'2023/10/02 00:40:00',null,'[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',null,null,null,null,'2023/10/02 00:50:00',null);
            """
            )
            init_db_instance.commit()
        # arrange
        base_procedures = {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "disconnect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                },
                {
                    "operationID": 2,
                    "operation": "shutdown",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [1],
                },
                {
                    "operationID": 3,
                    "operation": "connect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [2],
                },
                {
                    "operationID": 4,
                    "operation": "disconnect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [3],
                },
            ],
            "applyID": "300000022b",
        }
        executed_list = [
            Details(operationID=1, status=Result.COMPLETED),
            Details(operationID=2, status=Result.COMPLETED),
            Details(operationID=3, status=Result.COMPLETED),
            Details(operationID=4, status=Result.COMPLETED),
        ]
        origin_proc_list: list[Procedure] = get_procedure_list(base_procedures)
        config = LayoutApplyConfig()
        config.load_log_configs()
        logger = Logger(config.log_config)
        database = DbAccess(logger)

        uri = config.hardware_control.get("uri")

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

        procedures = {"procedures": base_procedures["procedures"]}
        applyID = base_procedures["applyID"]  # pylint: disable=C0103
        # act
        _update_layoutapply(
            executed_list,
            origin_proc_list,
            applyID,
            procedures,
            logger,
            config,
            False,
            database,
            False,
            Action.ROLLBACK_RESUME,
        )
        httpserver.clear()
        # assert
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyID}'")
            init_db_instance.commit()
            row = cursor.fetchone()
        assert row.get("status") == Result.CANCELED
        assert row.get("rollbackstatus") == Result.COMPLETED
        assert row.get("resumeresult") == [
            {"operationID": 1, "status": "COMPLETED"},
            {"operationID": 2, "status": "COMPLETED"},
            {"operationID": 3, "status": "COMPLETED"},
            {"operationID": 4, "status": "COMPLETED"},
        ]

    def test_create_result_status_failed_when_system_failure_occurred(
        self, httpserver: HTTPServer, init_db_instance, mocker, caplog
    ):
        """"""
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        # arrange
        param = {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "boot",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                },
            ],
            "applyID": "234567890e",
        }

        config = LayoutApplyConfig()
        config.load_log_configs()

        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")
        config.hardware_control["poweron"]["timeout"] = 5

        # raise timeout by sleeping longer than the timeout duration (5s).
        timeout_sec = 8

        def sleeping(request: Request):
            sleep(timeout_sec)

        err_msg = {"message": "Exxxxx", "code": "ER005BAS001"}
        uri = config.hardware_control.get("uri")
        # Initial execution with 0 retries, executed only once.
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(
            Response(
                response=b'{"type": "CPU", "powerState": "Off", "powerCapability": false}',
                status=200,
            )
        )
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_handler(sleeping)
        # message is not called.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json(err_msg, status=503)

        procedures = {"procedures": param["procedures"]}
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_resumed_target_sql_1, vars=[applyid])
            init_db_instance.commit()
        # act
        run(procedures, config, applyid)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=SELECT_SQL, vars=[applyid])
            init_db_instance.commit()
            row = cursor.fetchone()
        httpserver.clear()

        if row.get("status") == "IN_PROGRESS":
            assert row.get("status") == "IN_PROGRESS"
            for i in range(15):
                sleep(0.5)
                cursor.execute(query=SELECT_SQL, vars=[applyid])
                init_db_instance.commit()
                row = cursor.fetchone()
                if row.get("status") != "IN_PROGRESS":
                    break
        # assert
        assert row.get("status") == "FAILED"
        # Error logs are being output.
        assert "[E40005]Failed to execute LayoutApply." in caplog.text

    @pytest.mark.parametrize(
        "target_procedure_list, expected_resume_list, executed_list",
        [
            (
                # asc
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [2],
                    },
                ],
                # resume procedure
                [
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [2],
                    },
                ],
                [
                    Details(operationID=1, status=Result.COMPLETED),
                    Details(operationID=2, status=Result.FAILED),
                    Details(operationID=3, status=Result.SKIP),
                ],
            ),
            (
                # removal from multiple dependencies
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [1, 2],
                    },
                ],
                # resume procedure
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "boot",
                        "targetDeviceID": "3-1",
                        "dependencies": [1],
                    },
                ],
                [
                    Details(operationID=1, status=Result.FAILED),
                    Details(operationID=2, status=Result.COMPLETED),
                    Details(operationID=3, status=Result.SKIP),
                ],
            ),
            (
                # pararell
                [
                    {
                        "operationID": 1,
                        "operation": "connect",
                        "targetCPUID": "1-1",
                        "targetDeviceID": "1-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 3,
                        "operation": "connect",
                        "targetCPUID": "3-1",
                        "targetDeviceID": "3-2",
                        "dependencies": [1],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-1",
                        "dependencies": [2],
                    },
                ],
                # resume procedure
                [
                    {
                        "operationID": 2,
                        "operation": "disconnect",
                        "targetCPUID": "2-1",
                        "targetDeviceID": "2-2",
                        "dependencies": [],
                    },
                    {
                        "operationID": 4,
                        "operation": "boot",
                        "targetDeviceID": "4-1",
                        "dependencies": [2],
                    },
                ],
                [
                    Details(operationID=1, status=Result.COMPLETED),
                    Details(operationID=2, status=Result.FAILED),
                    Details(operationID=3, status=Result.COMPLETED),
                    Details(operationID=4, status=Result.SKIP),
                ],
            ),
        ],
    )
    def test_resume_proc_create_resume_procedure(self, target_procedure_list, expected_resume_list, executed_list):
        target_proc_list = [Procedure(**i) for i in target_procedure_list]
        resume_list = [Procedure(**i) for i in expected_resume_list]
        result_list = _create_resume_proc(target_proc_list, executed_list)
        result_list = sorted(result_list, key=lambda i: i.operationID)
        resume_list = sorted(resume_list, key=lambda i: i.operationID)
        for tmp in result_list:
            tmp.dependencies = sorted(tmp.dependencies)
        for tmp in resume_list:
            tmp.dependencies = sorted(tmp.dependencies)
        assert result_list == resume_list
