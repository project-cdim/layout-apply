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
"""Test for get api"""

import json
import logging
from logging.config import dictConfig  # pylint: disable=W0611 # noqa: F401

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2.extras import DictCursor

from layoutapply.common.dateutil import get_str_now
from layoutapply.const import IdParameter, Result
from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.db import DbAccess
from layoutapply.server import app
from layoutapply.setting import LayoutApplyLogConfig
from layoutapply.util import create_randomname
from tests.layoutapply.test_data import sql

client = TestClient(app)


def _case_id_from_assert_target(params):
    """Return stable short ids for parametrized tests."""
    if isinstance(params, tuple) and len(params) > 1 and isinstance(params[1], dict):
        apply_id = params[1].get("applyID")
        if isinstance(apply_id, str) and apply_id:
            return apply_id
    return "case"


@pytest.mark.usefixtures("httpserver_listen_address")
class TestGetAPIServerSuccess:
    """Test class for successful GET API responses."""

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
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "rollback": {
                        "procedures": {"procedures": "pre_test"},
                        "startedAt": "started_at",
                    },
                },
            ),
            (
                sql.get_list_insert_sql_3,
                {
                    "status": "COMPLETED",
                    "applyID": "000000003c",
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
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
                    "result": [{"test": "test"}, {"test": "test"}],
                    "startedAt": "2023-10-02T00:00:01Z",
                    "endedAt": "2023-10-02T12:24:00Z",
                },
            ),
            (
                sql.get_list_insert_sql_10,
                {
                    "status": "FAILED",
                    "applyID": "00000000fa",
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "startedAt": "2023-10-05T00:00:01Z",
                    "endedAt": "2023-10-05T12:24:00Z",
                    "canceledAt": "2023-10-05T12:00:00Z",
                    "executeRollback": True,
                },
            ),
            (
                sql.get_list_insert_sql_5,
                {
                    "status": "CANCELED",
                    "applyID": "000000005e",
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ),
            (
                sql.get_list_insert_sql_9,
                {
                    "status": "SUSPENDED",
                    "applyID": "000000009c",
                    "startedAt": "2023-10-02T00:00:01Z",
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "resumeProcedures": {"procedures": "pre_test"},
                    "suspendedAt": "2024-01-02T12:23:00Z",
                },
            ),
            (
                sql.get_list_insert_sql_6,
                {
                    "status": "CANCELED",
                    "applyID": "000000006f",
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                    "rollback": {
                        "status": "COMPLETED",
                        "procedures": {"procedures": "pre_test"},
                        "result": [{"test": "test"}, {"test": "test"}],
                        "startedAt": "2023-10-03T12:20:00Z",
                        "endedAt": "2023-10-04T12:23:59Z",
                    },
                },
            ),
            (
                sql.get_list_insert_sql_6,
                {
                    "status": "CANCELED",
                    "applyID": "000000007g",
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                    "rollback": {
                        "status": "FAILED",
                        "procedures": {"procedures": "pre_test"},
                        "result": [{"test": "test"}, {"test": "test"}],
                        "startedAt": "2023-10-03T12:20:00Z",
                        "endedAt": "2023-10-04T12:23:59Z",
                    },
                },
            ),
            (
                sql.get_list_insert_sql_11,
                {
                    "status": "CANCELED",
                    "applyID": "000000008h",
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "startedAt": "2023-10-03T00:00:00Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                    "rollback": {
                        "status": "SUSPENDED",
                        "procedures": {"procedures": "pre_test"},
                        "result": [{"test": "test"}, {"test": "test"}],
                        "startedAt": "2023-10-03T12:20:00Z",
                        "suspendedAt": "2023-10-04T12:23:59Z",
                        "resumeProcedures": {"procedures": "pre_test"},
                    },
                },
            ),
        ],
        ids=_case_id_from_assert_target,
    )
    def test_get_applystatus_success(
        self, mocker, init_db_instance, insert_sql, assert_target, caplog, docker_services
    ):  # pylint: disable=W0613
        """Test get apply status success."""
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.INFO)

        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        started_at = get_str_now()
        check_flg = False
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            if assert_target["applyID"] == "000000002b":
                cursor.execute(
                    query=sql.get_list_insert_sql_r_2,
                    vars=[Result.IN_PROGRESS, '{"procedures": "pre_test"}', started_at, applyid],
                )
            if assert_target["applyID"] == "000000006f":
                # check_flg = True
                cursor.execute(query=sql.get_list_insert_sql_r_6, vars=[applyid])
            if assert_target["applyID"] == "000000007g":
                # check_flg = True
                cursor.execute(query=sql.get_list_insert_sql_r_6_failed, vars=[applyid])
            if assert_target["applyID"] == "000000008h":
                # check_flg = True
                cursor.execute(query=sql.get_list_insert_sql_r_6_suspended, vars=[applyid])
        init_db_instance.commit()
        if assert_target["applyID"] == "000000002b":
            assert_target["rollback"]["startedAt"] = started_at
        assert_target["applyID"] = applyid

        # act
        response = client.get(f"/cdim/api/v1/layout-apply/{applyid}")

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        if check_flg:
            print(get_response)
            print("-----------------")
            print(assert_target)
        assert get_response == assert_target
        assert "Completed successfully." in caplog.text
        # data adjustment after testing
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.delete_for_applyid_sql, vars=[applyid])
            cursor.execute(query=sql.delete_for_applyid_r_sql, vars=[applyid])
        init_db_instance.commit()

    @pytest.mark.parametrize(
        ("insert_sql", "assert_target"),
        [
            (
                sql.get_valid_insert_sql,
                {
                    "status": "COMPLETED",
                    "applyID": "999999999a",
                    "procedures": [],
                    "result": [],
                    "startedAt": "2023-10-02T00:00:00Z",
                    "endedAt": "2023-10-02T12:23:59Z",
                },
            )
        ],
        ids=_case_id_from_assert_target,
    )
    def test_get_applystatus_success_when_valid_data(
        self, mocker, init_db_instance, insert_sql, assert_target, caplog, docker_services
    ):  # pylint: disable=W0613
        """Test get apply status success when valid data."""
        mocker.patch("logging.config.dictConfig")

        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
        init_db_instance.commit()
        assert_target["applyID"] = applyid

        # act
        response = client.get(f"/cdim/api/v1/layout-apply/{applyid}")

        # assert

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == assert_target
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        ("insert_sql", "assert_target"),
        [
            (
                sql.insert_resumed_get_target_sql_1,
                {
                    "status": "IN_PROGRESS",
                    "applyID": "300000006a",
                    "startedAt": "2023-10-02T00:00:00Z",
                    "result": [{"test": "test"}, {"test": "test"}],
                    "resumedAt": "2023-10-03T12:23:59Z",
                    "procedures": {"procedures": "pre_test"},
                    "resumeProcedures": {"procedures": "pre_test"},
                },
            ),
            (
                sql.insert_resumed_get_target_sql_2,
                {
                    "status": "CANCELING",
                    "applyID": "300000007b",
                    "startedAt": "2023-10-02T00:00:00Z",
                    "canceledAt": "2023-10-02T00:00:01Z",
                    "executeRollback": True,
                    "resumedAt": "2023-10-03T12:23:59Z",
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "resumeProcedures": {"procedures": "pre_test"},
                },
            ),
            (
                sql.insert_resumed_get_target_sql_5,
                {
                    "status": "IN_PROGRESS",
                    "applyID": "300000004d",
                    "startedAt": "2023-10-02T00:00:00Z",
                    "result": [{"test": "test"}, {"test": "test"}],
                    "resumedAt": "2023-10-03T12:23:59Z",
                    "procedures": {"procedures": "pre_test"},
                    "resumeProcedures": {"procedures": "pre_test"},
                },
            ),
        ],
        ids=_case_id_from_assert_target,
    )
    def test_get_applystatus_success_when_state_in_progress_or_canceling_data(
        self, mocker, init_db_instance, assert_target, insert_sql, caplog, docker_services
    ):  # pylint: disable=W0613
        """Test get apply status success when state in progress or canceling data."""
        mocker.patch("logging.config.dictConfig")

        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
        init_db_instance.commit()
        assert_target["applyID"] = applyid

        # act
        response = client.get(f"/cdim/api/v1/layout-apply/{applyid}")

        # assert

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == assert_target
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        ("insert_sql", "assert_target"),
        [
            (
                sql.get_valid_insert_sql,
                {
                    "status": "COMPLETED",
                    "applyID": "999999999a",
                    "procedures": [],
                    "result": [],
                    "startedAt": "2023-10-02T00:00:00Z",
                    "endedAt": "2023-10-02T12:23:59Z",
                },
            )
        ],
        ids=_case_id_from_assert_target,
    )
    def test_get_applystatus_success_when_invalid_option_specified(
        self, mocker, init_db_instance, assert_target, insert_sql, caplog, docker_services
    ):  # pylint: disable=W0613
        """Test get apply status success when invalid option specified."""
        # arrange
        mocker.patch("logging.config.dictConfig")
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
        init_db_instance.commit()
        assert_target["applyID"] = applyid

        # act
        response = client.get(f"/cdim/api/v1/layout-apply/{applyid}", params={"fields": ["procedures"]})

        # assert

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == assert_target
        assert "Completed successfully." in caplog.text

    def test_get_applystatus_success_when_rollback_completed_after_cancel(
        self, mocker, init_db_instance, caplog, docker_services
    ):  # pylint: disable=W0613
        """Test get apply status success when rollback completed after cancel."""
        mocker.patch("logging.config.dictConfig")

        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_applystatus_insert_sql_cancel_with_rollback_completed, vars=[applyid])
            cursor.execute(query=sql.get_applystatus_insert_sql_rollback_completed_for_cancel, vars=[applyid])
        init_db_instance.commit()

        assert_target = {
            "status": "CANCELED",
            "applyID": applyid,
            "procedures": {"procedures": "pre_test"},
            "result": [{"test": "test"}, {"test": "test"}],
            "rollbackProcedures": {"procedures": "rollback_test"},
            "startedAt": "2023-10-03T00:00:00Z",
            "endedAt": "2023-10-04T12:23:59Z",
            "canceledAt": "2023-10-03T12:00:00Z",
            "executeRollback": True,
            "rollback": {
                "applyID": applyid,
                "status": "COMPLETED",
                "procedures": {"procedures": "rollback_test"},
                "result": [{"test": "rollback_result"}],
                "rollbackProcedures": None,
                "startedAt": "2023-10-03T12:20:00Z",
                "endedAt": "2023-10-04T12:23:59Z",
                "canceledAt": None,
                "resumeProcedures": None,
                "suspendedAt": None,
                "resumedAt": None,
            },
        }

        # act
        response = client.get(f"/cdim/api/v1/layout-apply/{applyid}")

        # assert
        assert response.status_code == 200
        get_response = json.loads(response.content.decode())

        assert get_response["status"] == assert_target["status"]
        assert get_response["applyID"] == assert_target["applyID"]
        assert get_response["procedures"] == assert_target["procedures"]
        assert get_response["result"] == assert_target["result"]
        assert get_response["rollbackProcedures"] == assert_target["rollbackProcedures"]
        assert get_response["startedAt"] == assert_target["startedAt"]
        assert get_response["endedAt"] == assert_target["endedAt"]
        assert get_response["canceledAt"] == assert_target["canceledAt"]
        assert get_response["executeRollback"] == assert_target["executeRollback"]
        assert get_response["rollback"]["status"] == "COMPLETED"
        assert get_response["rollback"]["result"] == [{"test": "rollback_result"}]
        assert get_response["rollback"]["startedAt"] == "2023-10-03T12:20:00Z"
        assert get_response["rollback"]["endedAt"] == "2023-10-04T12:23:59Z"

        assert "Completed successfully." in caplog.text

    def test_get_applystatus_success_when_multiple_resume_with_rollback(
        self, mocker, init_db_instance, caplog, docker_services
    ):  # pylint: disable=W0613
        """Test get apply status success when multiple resume with rollback."""
        mocker.patch("logging.config.dictConfig")

        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_applystatus_insert_sql_multiple_resume_with_rollback, vars=[applyid])
            cursor.execute(query=sql.get_applystatus_insert_sql_rollback_for_multiple_resume, vars=[applyid])
        init_db_instance.commit()

        # act
        response = client.get(f"/cdim/api/v1/layout-apply/{applyid}")

        # assert
        assert response.status_code == 200
        get_response = json.loads(response.content.decode())

        assert get_response["status"] == "CANCELED"
        assert get_response["applyID"] == applyid
        assert get_response["procedures"] == {"procedures": "apply_test"}
        assert len(get_response["result"]) == 3

        assert get_response["result"][0]["operationID"] == 1
        assert get_response["result"][0]["status"] == "FAILED"
        assert get_response["result"][1]["operationID"] == 1
        assert get_response["result"][1]["status"] == "COMPLETED"
        assert get_response["result"][2]["operationID"] == 2
        assert get_response["result"][2]["status"] == "FAILED"

        assert get_response["executeRollback"] is True
        assert get_response["resumeProcedures"] == [{"resume": 1, "procedure": "retry_after_suspend"}]
        assert get_response["resumedAt"] == "2023-10-11T10:00:00Z"
        assert get_response["suspendedAt"] == "2023-10-11T09:00:00Z"

        assert "rollback" in get_response
        assert get_response["rollback"]["status"] == "COMPLETED"
        assert len(get_response["rollback"]["result"]) == 3

        assert get_response["rollback"]["result"][0]["operationID"] == 2
        assert get_response["rollback"]["result"][0]["status"] == "FAILED"
        assert get_response["rollback"]["result"][1]["operationID"] == 2
        assert get_response["rollback"]["result"][1]["status"] == "COMPLETED"
        assert get_response["rollback"]["result"][2]["operationID"] == 1
        assert get_response["rollback"]["result"][2]["status"] == "COMPLETED"

        assert get_response["rollback"]["resumeProcedures"] == [{"resume": 1, "procedure": "retry_rollback"}]
        assert get_response["rollback"]["resumedAt"] == "2023-10-11T15:40:00Z"
        assert get_response["rollback"]["suspendedAt"] == "2023-10-11T15:30:00Z"

        assert "Completed successfully." in caplog.text

    def test_get_applystatus_success_when_rollback_suspended_and_resumed(
        self, mocker, init_db_instance, caplog, docker_services
    ):  # pylint: disable=W0613
        """Test get apply status success when rollback is suspended and resumed."""
        mocker.patch("logging.config.dictConfig")

        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_applystatus_insert_sql_rollback_suspended_and_resumed, vars=[applyid])
            cursor.execute(query=sql.get_applystatus_insert_sql_rollback_for_suspended_and_resumed, vars=[applyid])
        init_db_instance.commit()

        # act
        response = client.get(f"/cdim/api/v1/layout-apply/{applyid}")

        # assert
        assert response.status_code == 200
        get_response = json.loads(response.content.decode())

        assert get_response["status"] == "CANCELED"
        assert get_response["applyID"] == applyid
        assert get_response["procedures"] == {"procedures": "apply_test"}
        assert len(get_response["result"]) == 2
        assert get_response["result"][0]["operationID"] == 1
        assert get_response["result"][0]["status"] == "COMPLETED"
        assert get_response["result"][1]["operationID"] == 2
        assert get_response["result"][1]["status"] == "COMPLETED"
        assert get_response["executeRollback"] is True
        assert get_response["canceledAt"] == "2023-10-15T12:30:00Z"

        assert "rollback" in get_response
        assert get_response["rollback"]["status"] == "COMPLETED"
        assert len(get_response["rollback"]["result"]) == 3

        assert get_response["rollback"]["result"][0]["operationID"] == 2
        assert get_response["rollback"]["result"][0]["status"] == "FAILED"
        assert get_response["rollback"]["result"][0]["startedAt"] == "2023-10-15T13:00:00Z"
        assert get_response["rollback"]["result"][0]["endedAt"] == "2023-10-15T14:00:00Z"

        assert get_response["rollback"]["result"][1]["operationID"] == 2
        assert get_response["rollback"]["result"][1]["status"] == "COMPLETED"
        assert get_response["rollback"]["result"][1]["startedAt"] == "2023-10-15T15:00:00Z"
        assert get_response["rollback"]["result"][1]["endedAt"] == "2023-10-15T15:30:00Z"

        assert get_response["rollback"]["result"][2]["operationID"] == 1
        assert get_response["rollback"]["result"][2]["status"] == "COMPLETED"
        assert get_response["rollback"]["result"][2]["startedAt"] == "2023-10-15T15:30:00Z"
        assert get_response["rollback"]["result"][2]["endedAt"] == "2023-10-15T16:00:00Z"

        assert get_response["rollback"]["suspendedAt"] == "2023-10-15T14:00:00Z"
        assert get_response["rollback"]["resumedAt"] == "2023-10-15T15:00:00Z"
        assert get_response["rollback"]["resumeProcedures"] == {"procedures": "retry_rollback_after_suspend"}
        assert get_response["rollback"]["startedAt"] == "2023-10-15T13:00:00Z"
        assert get_response["rollback"]["endedAt"] == "2023-10-15T16:00:00Z"

        assert "Completed successfully." in caplog.text

    def test_get_applystatus_success_when_resumed_then_canceled_with_rollback(
        self, mocker, init_db_instance, caplog, docker_services
    ):  # pylint: disable=W0613
        """Test getting apply status successfully when it is resumed and then canceled with a rollback."""
        mocker.patch("logging.config.dictConfig")

        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_applystatus_insert_sql_resumed_then_canceled_with_rollback, vars=[applyid])
            cursor.execute(query=sql.get_applystatus_insert_sql_rollback_for_resumed_then_canceled, vars=[applyid])
        init_db_instance.commit()

        # act
        response = client.get(f"/cdim/api/v1/layout-apply/{applyid}")

        # assert
        assert response.status_code == 200
        get_response = json.loads(response.content.decode())

        assert get_response["status"] == "CANCELED"
        assert get_response["applyID"] == applyid
        assert get_response["procedures"] == {"procedures": "apply_test"}
        assert len(get_response["result"]) == 3

        assert get_response["result"][0]["operationID"] == 1
        assert get_response["result"][0]["status"] == "FAILED"
        assert get_response["result"][0]["startedAt"] == "2023-10-20T10:00:00Z"
        assert get_response["result"][0]["endedAt"] == "2023-10-20T11:00:00Z"

        assert get_response["result"][1]["operationID"] == 1
        assert get_response["result"][1]["status"] == "COMPLETED"
        assert get_response["result"][1]["startedAt"] == "2023-10-20T14:00:00Z"
        assert get_response["result"][1]["endedAt"] == "2023-10-20T15:00:00Z"

        assert get_response["result"][2]["operationID"] == 2
        assert get_response["result"][2]["status"] == "CANCELED"
        assert get_response["result"][2]["startedAt"] == "2023-10-20T15:00:00Z"
        assert get_response["result"][2]["endedAt"] == "2023-10-20T15:30:00Z"

        assert get_response["executeRollback"] is True
        assert get_response["suspendedAt"] == "2023-10-20T11:00:00Z"
        assert get_response["resumedAt"] == "2023-10-20T14:00:00Z"
        assert get_response["resumeProcedures"] == {"procedures": "resume_after_suspend"}
        assert get_response["canceledAt"] == "2023-10-20T15:30:00Z"

        assert "rollback" in get_response
        assert get_response["rollback"]["status"] == "COMPLETED"
        assert len(get_response["rollback"]["result"]) == 2

        assert get_response["rollback"]["result"][0]["operationID"] == 2
        assert get_response["rollback"]["result"][0]["status"] == "COMPLETED"
        assert get_response["rollback"]["result"][0]["startedAt"] == "2023-10-20T15:40:00Z"
        assert get_response["rollback"]["result"][0]["endedAt"] == "2023-10-20T16:00:00Z"

        assert get_response["rollback"]["result"][1]["operationID"] == 1
        assert get_response["rollback"]["result"][1]["status"] == "COMPLETED"
        assert get_response["rollback"]["result"][1]["startedAt"] == "2023-10-20T16:00:00Z"
        assert get_response["rollback"]["result"][1]["endedAt"] == "2023-10-20T17:00:00Z"

        assert get_response["rollback"]["startedAt"] == "2023-10-20T15:40:00Z"
        assert get_response["rollback"]["endedAt"] == "2023-10-20T17:00:00Z"

        assert "Completed successfully." in caplog.text

    def test_get_applystatus_success_when_canceling_without_execute_rollback(
        self, mocker, init_db_instance, caplog, docker_services
    ):  # pylint: disable=W0613
        """Test get apply status success when status is CANCELING and executeRollback is False."""
        mocker.patch("logging.config.dictConfig")

        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_8, vars=[applyid])
        init_db_instance.commit()

        response = client.get(f"/cdim/api/v1/layout-apply/{applyid}")
        get_response = json.loads(response.content.decode())

        assert response.status_code == 200
        assert get_response["status"] == "CANCELING"
        assert get_response["applyID"] == applyid
        assert get_response["executeRollback"] is False
        assert get_response["startedAt"] == "2023-10-01T23:59:59Z"
        assert get_response["canceledAt"] == "2023-10-02T12:00:00Z"
        assert get_response["procedures"] == {"procedures": "pre_test"}
        assert get_response["result"] == [{"test": "test"}, {"test": "test"}]
        assert "rollbackProcedures" not in get_response
        assert "rollback" not in get_response
        assert "Completed successfully." in caplog.text


class TestGetAPIServerFailure:
    """Failure scenarios for get API."""

    def test_get_applystatus_failure_when_canceling_rollback_has_no_startedat(
        self, mocker, init_db_instance, docker_services
    ):  # pylint: disable=W0613
        """Test failure when CANCELING rollback has procedures but no startedAt."""
        mocker.patch("logging.config.dictConfig")

        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid])
            cursor.execute(query=sql.get_list_insert_sql_r_2_without_startedat, vars=[applyid])
        init_db_instance.commit()

        with pytest.raises(KeyError):
            client.get(f"/cdim/api/v1/layout-apply/{applyid}")

    def test_get_applystatus_failure_when_query_failure_occurred(
        self, mocker, caplog, docker_services
    ):  # pylint: disable=W0613
        """Test failure when a query failure occurs."""
        mocker.patch("logging.config.dictConfig")

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

        # act
        response = client.get("/cdim/api/v1/layout-apply/123456789a")

        # assert
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40019"
        assert "Query failed." in error_response["message"]
        assert "[E40019]Query failed." in caplog.text

    def test_get_applystatus_failure_when_failed_db_connection(self, mocker, docker_services):  # pylint: disable=W0613
        """Test failure when failed to connect to the database."""
        # arrange
        mocker.patch.object(DbAccess, "get_apply_status", side_effect=psycopg2.OperationalError)

        # act
        response = client.get("/cdim/api/v1/layout-apply/123456789a")
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40018"
        assert "Could not connect to ApplyStatusDB." in error_response["message"]

    def test_get_applystatus_failure_when_nonexistent_id(
        self, mocker, init_db_instance, docker_services, caplog
    ):  # pylint: disable=W0613
        """Test failure when a non-existent ID is provided."""
        mocker.patch("logging.config.dictConfig")

        # act
        response = client.get("/cdim/api/v1/layout-apply/9999999999")

        # assert

        assert response.status_code == 404

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40020"
        assert error_response["message"] == "Specified 9999999999 is not found."
        assert "[E40020]Specified 9999999999 is not found." in caplog.text

    @pytest.mark.parametrize(
        "args",
        [
            ("g21bc21587"),  # character type violation
            ("ABCDEF0123"),  # character type violation
            ("あBCDEF0123"),  # character type violation
            ("a21bc2158"),  # character length violation
            ("a21bc215871"),  # character length violation
            ("a"),  # character length violation
        ],
    )
    def test_get_applystatus_failure_when_invalid_id(self, args):
        """Test failure when an invalid ID is provided."""
        # arrange

        response = client.get(f"/cdim/api/v1/layout-apply/{args}")
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"


@pytest.mark.usefixtures("httpserver_listen_address")
class TestGetAPIServerConfigFailure:
    """Configuration and initialization failures for get API."""

    def test_get_applystatus_failure_when_failed_to_load_config_file(
        self, mocker, docker_services
    ):  # pylint: disable=W0613
        """Test failure when failed to load configuration file."""
        mocker.patch(
            "yaml.safe_load", side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")]
        )

        response = client.get("/cdim/api/v1/layout-apply/123456789a")
        # assert
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_config.yaml.\n('Dummy message',)"

    def test_get_applystatus_failure_when_failed_to_load_log_config_file(
        self, mocker, docker_services
    ):  # pylint: disable=W0613
        """Test failure when failed to load log configuration file."""
        mocker.patch.object(LayoutApplyLogConfig, "_validate_log_dir", side_effect=[Exception("Dummy message")])

        # arrange
        response = client.get("/cdim/api/v1/layout-apply/123456789a")
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_log_config.yaml.\n('Dummy message',)"
