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
"""Test for api"""  # pylint: disable=C0302

import json
import logging
import re
import urllib
from logging.config import dictConfig  # pylint: disable=W0611 # noqa: F401

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2.extras import DictCursor

from layoutapply.const import IdParameter, Result
from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.db import DbAccess
from layoutapply.server import app
from layoutapply.setting import LayoutApplyLogConfig
from layoutapply.util import create_randomname
from tests.layoutapply.test_data import sql

client = TestClient(app)

get_list_assert_target = {
    "totalCount": 9,
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
        },
        {
            "status": "CANCELING",
            "applyID": "000000007a",
            "startedAt": "2023-10-01T23:59:59Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": True,
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


@pytest.mark.usefixtures("httpserver_listen_address")
class TestGetListAPIServerSuccess:
    """Test cases for successful responses of the Get List API."""

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

    @pytest.mark.parametrize(
        "query_parameter",
        [
            {"startedAtSince": "2023-10-02T23:59:00Z"},
            {"startedAtSince": "2023-10-03T00:00:00Z"},
            {"startedAtSince": "2023-10-02T23:59:00-00:01"},
            {"startedAtSince": "2023-10-03T00:00:01+00:01"},
        ],
    )
    def test_get_applystatus_list_success_when_start_time_specified(
        self, mocker, query_parameter, init_db_instance, caplog, docker_services
    ):  # pylint: disable=W0613
        """Test successful retrieval of apply status list when start time is specified."""
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.INFO)
        # Data adjustment before testing.
        id_list = self.insert_list_data(init_db_instance)

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        encoded_params = urllib.parse.urlencode(query_parameter)
        full_url = f"{request_uri}?{encoded_params}"

        response = client.get(full_url)
        # response = client.get(request_uri, params=query_parameter)

        get_list_assert_target_1 = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": id_list[5],
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                },
            ],
        }

        # assert

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_1
        assert "Completed successfully." in caplog.text

    def test_get_applystatus_list_success(self, mocker, init_db_instance, caplog):
        """Test successful retrieval of apply status list."""
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()
        # act
        response = client.get("/cdim/api/v1/layout-apply")

        # assert

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())

        assert get_response["count"] == get_list_assert_target["count"]
        assert get_response["totalCount"] == get_list_assert_target["totalCount"]
        for a in get_response["applyResults"]:
            assert a in get_list_assert_target["applyResults"]
            assert a not in ("procedures", "result", "rollbackProcedures", "resumeProcedures")
        assert "Completed successfully." in caplog.text

    def test_get_applystatus_list_success_when_no_results_fetched(
        self, mocker, init_db_instance, caplog
    ):  # pylint: disable=W0613
        """Test successful retrieval of apply status list when no results are fetched."""
        mocker.patch("logging.config.dictConfig")

        assert_target = {
            "totalCount": 0,
            "count": 0,
            "applyResults": [],
        }

        # act
        response = client.get("/cdim/api/v1/layout-apply")

        # assert

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == assert_target
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "params, fields",
        [
            (
                {"fields": ["procedures"]},
                ["procedures"],
            ),  # fields:procedures
            (
                {"fields": ["result"]},
                ["result"],
            ),  # fields:result
            (
                {"fields": ["rollbackProcedures"]},
                ["rollbackProcedures"],
            ),  # fields:rollbackProcedures
            (
                {"fields": ["resumeProcedures"]},
                ["resumeProcedures"],
            ),  # fields:resumeProcedures
            (
                {"fields": ["procedures", "result"]},
                ["procedures", "result"],
            ),  # fields:procedures/result
            (
                {"fields": ["procedures", "rollbackProcedures"]},
                ["procedures", "rollbackProcedures"],
            ),  # fields:procedures/rollbackProcedures
            (
                {"fields": ["procedures", "resumeProcedures"]},
                ["procedures", "resumeProcedures"],
            ),  # fields:procedures/resumeProcedures
            (
                {"fields": ["result", "rollbackProcedures"]},
                ["result", "rollbackProcedures"],
            ),  # fields:result/rollbackProcedures
            (
                {"fields": ["result", "resumeProcedures"]},
                ["result", "resumeProcedures"],
            ),  # fields:result/resumeProcedures
            (
                {"fields": ["rollbackProcedures", "resumeProcedures"]},
                ["rollbackProcedures", "resumeProcedures"],
            ),  # fields:rollbackProcedures/resumeProcedures
            (
                {"fields": ["procedures", "result", "rollbackProcedures"]},
                ["procedures", "result", "rollbackProcedures"],
            ),  # fields:procedures/result/rollbackProcedures
            (
                {"fields": ["procedures", "result", "resumeProcedures"]},
                ["procedures", "result", "resumeProcedures"],
            ),  # fields:procedures/result/resumeProcedures
            (
                {"fields": ["procedures", "rollbackProcedures", "resumeProcedures"]},
                ["procedures", "rollbackProcedures", "resumeProcedures"],
            ),  # fields:procedures/rollbackProcedures/resumeProcedures
            (
                {"fields": ["result", "rollbackProcedures", "resumeProcedures"]},
                ["result", "rollbackProcedures", "resumeProcedures"],
            ),  # fields:result/rollbackProcedures/resumeProcedures
            (
                {
                    "fields": [
                        "procedures",
                        "result",
                        "rollbackProcedures",
                        "resumeProcedures",
                    ]
                },
                ["procedures", "result", "rollbackProcedures", "resumeProcedures"],
            ),  # fields:procedures/result/rollbackProcedures/resumeProcedures
        ],
    )
    def test_get_applystatus_list_success_when_field_specified(
        self, mocker, docker_services, init_db_instance, params, fields, caplog
    ):  # pylint: disable=W0613
        """Test successful retrieval of apply status list when specific fields are specified."""
        mocker.patch("logging.config.dictConfig", lambda config: None)

        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.INFO)

        def _fields_check(check_targets: list, fields: list, result: dict):
            for target in check_targets:
                if target in fields:
                    assert target in result
                else:
                    assert target not in result
                if "rollback" in result:
                    if target != "rollbackProcedures":
                        if target in fields:
                            assert target in result["rollback"]
                        else:
                            assert target not in result["rollback"]

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
            cursor.execute(query=sql.get_list_insert_sql_06f_rb)
        init_db_instance.commit()
        response = client.get("/cdim/api/v1/layout-apply", params=params)

        # assert
        assert response.status_code == 200
        get_response = json.loads(response.content.decode())
        # Only items specified in the fields are output, and unspecified items are not output.
        applyResults = get_response.get("applyResults")  # pylint: disable=invalid-name
        # standard output displays only the items specified by fields, and items not specified are not displayed.
        for result in applyResults:
            if result.get("suspendedAt") is not None:
                # no items that can be specified in fields
                _fields_check(
                    ["resumeProcedures"],
                    fields,
                    result,
                )
            match result.get("status"):
                case "COMPLETED" | "FAILED":
                    # no rollback related items with fields specified.
                    assert "rollbackProcedures" not in result
                    assert "resumeProcedures" not in result
                    _fields_check(["procedures", "result"], fields, result)
                case "IN_PROGRESS":
                    # no items that can be specified in fields
                    assert "result" not in result
                    assert "rollbackProcedures" not in result
                    assert "resumeProcedures" not in result
                case "CANCELING":
                    # no items that can be specified in fields
                    assert "resumeProcedures" not in result
                case "CANCELED":
                    _fields_check(
                        [
                            "procedures",
                            "result",
                            "rollbackProcedures",
                        ],
                        fields,
                        result,
                    )
                case "SUSPENDED":
                    # no rollback related items with fields specified.
                    assert "rollbackProcedures" not in result
                    _fields_check(["procedures", "result", "resumeProcedures"], fields, result)
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?status=CANCELED&startedAtSince=2023-10-02T00:00:03Z&startedAtUntil=2023-10-03T00:00:01Z&\
                endedAtSince=2023-10-02T12:24:01Z&endedAtUntil=2023-10-04T12:24:00Z",
        ],
    )
    def test_get_applystatus_list_success_when_only_start_date_start_out_of_range(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        """Test successful retrieval of apply status list when only the start date is out of range."""
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        # "applyID": "000000006f"（target）"applyID": "000000005e"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": "000000006f",
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                },
            ],
        }

        # assert

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_all
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?status=CANCELED&startedAtSince=2023-10-02T00:00:02Z&startedAtUntil=2023-10-02T23:59:59Z&endedAtSince=2023-10-02T12:24:01Z&endedAtUntil=2023-10-04T12:24:00Z",  # pylint: disable=C0301 # noqa: E501
        ],
    )
    def test_get_applystatus_list_success_when_only_end_date_end_out_of_range(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        """Test successful retrieval of apply status list when only the end date is out of range."""
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        # "applyID": "000000005e"（target）"applyID": "000000006f"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": "000000005e",
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_all
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?status=CANCELED&startedAtSince=2023-10-02T00:00:02Z&startedAtUntil=2023-10-03T00:00:00Z&endedAtSince=2023-10-02T12:24:02Z&endedAtUntil=2023-10-04T12:24:00Z",  # pylint: disable=C0301 # noqa: E501
        ],
    )
    def test_get_applystatus_list_success_when_only_end_date_start_out_of_range(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        """Test successful retrieval of apply status list when only the end date's start is out of range."""
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        # "applyID": "000000006f"（target）"applyID": "000000005e"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": "000000006f",
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                },
            ],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_all
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?status=CANCELED&startedAtSince=2023-10-02T00:00:02Z&startedAtUntil=2023-10-03T00:00:00Z&endedAtSince=2023-10-02T12:24:01Z&endedAtUntil=2023-10-04T12:23:58Z",  # pylint: disable=C0301 # noqa: E501
        ],
    )
    def test_get_applystatus_list_success_when_end_date_end_out_of_range(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        """Test successful retrieval of apply status list when the end date's end is out of range."""
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        # "applyID": "000000005e"（target）"applyID": "000000006f"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": "000000005e",
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_all
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?status=CANCELED&startedAtSince=2023-10-05T00:00:00Z&startedAtUntil=2023-10-06T00:00:00Z&endedAtSince=2023-10-05T00:00:00Z&endedAtUntil=2023-10-06T23:59:59Z",  # pylint: disable=C0301 # noqa: E501
        ],
    )
    def test_get_applystatus_list_success_when_boundary_value_of_end_date_end(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        """Test successful retrieval of apply status list when the end date's end is at the boundary value."""
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        # "applyID": "000000005e"、"applyID": "000000006f"（no target）
        get_list_assert_target_all = {
            "totalCount": 0,
            "count": 0,
            "applyResults": [],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_all
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?status=IN_PROGRESS",
        ],
    )
    def test_get_applystatus_list_success_when_status_specified(self, mocker, parameter_uri, init_db_instance, caplog):
        """Test successful retrieval of apply status list when the status is specified."""
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        get_list_assert_target_status = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "applyID": "000000001a",
                    "status": "IN_PROGRESS",
                    "startedAt": "2023-10-02T00:00:00Z",
                },
            ],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_status
        assert "Completed successfully." in caplog.text

    def test_get_applystatus_list_success_when_status_keys_contract_verified(
        self, mocker, init_db_instance, caplog
    ):
        """Verify required keys exist and unnecessary keys do not exist for all statuses."""
        mocker.patch("logging.config.dictConfig")

        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        response = client.get("/cdim/api/v1/layout-apply")

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        apply_results = get_response["applyResults"]

        expected_statuses = {
            "IN_PROGRESS",
            "CANCELING",
            "COMPLETED",
            "FAILED",
            "CANCELED",
            "SUSPENDED",
        }
        status_rules = {
            "IN_PROGRESS": {
                "required": {"applyID", "status", "startedAt"},
                "forbidden": {"endedAt", "canceledAt", "executeRollback", "suspendedAt", "rollback"},
            },
            "CANCELING": {
                "required": {"applyID", "status", "startedAt", "canceledAt", "executeRollback"},
                "forbidden": {"endedAt", "suspendedAt"},
            },
            "COMPLETED": {
                "required": {"applyID", "status", "startedAt", "endedAt"},
                "forbidden": {"canceledAt", "executeRollback", "suspendedAt", "rollback"},
            },
            "FAILED": {
                "required": {"applyID", "status", "startedAt", "endedAt"},
                "forbidden": {"suspendedAt", "rollback"},
            },
            "CANCELED": {
                "required": {"applyID", "status", "startedAt", "endedAt", "canceledAt", "executeRollback"},
                "forbidden": {"suspendedAt"},
            },
            "SUSPENDED": {
                "required": {"applyID", "status", "startedAt", "suspendedAt"},
                "forbidden": {"endedAt", "canceledAt", "executeRollback", "rollback"},
            },
        }
        common_forbidden = {"procedures", "result", "rollbackProcedures", "resumeProcedures"}

        seen_statuses = {result["status"] for result in apply_results}
        assert seen_statuses == expected_statuses

        for result in apply_results:
            status = result["status"]
            rule = status_rules[status]
            keys = set(result.keys())

            assert rule["required"].issubset(keys)
            assert not (keys & common_forbidden)
            assert not (keys & rule["forbidden"])

            if status == "CANCELING":
                assert "rollback" not in result

        assert "Completed successfully." in caplog.text

    def test_get_applystatus_list_success_when_canceling_with_rollback_startedat(
        self, mocker, init_db_instance, caplog
    ):
        """Test successful retrieval when status is CANCELING and rollback has startedAt."""
        mocker.patch("logging.config.dictConfig")

        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid])
            cursor.execute(
                query=sql.get_list_insert_sql_r_2,
                vars=[Result.IN_PROGRESS, "[]", "2023-10-02 12:20:00", applyid],
            )
        init_db_instance.commit()

        response = client.get("/cdim/api/v1/layout-apply/?status=CANCELING")

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response["totalCount"] == 1
        assert get_response["count"] == 1
        assert len(get_response["applyResults"]) == 1

        apply_result = get_response["applyResults"][0]
        assert apply_result["applyID"] == applyid
        assert apply_result["status"] == "CANCELING"
        assert apply_result["startedAt"] == "2023-10-01T23:59:59Z"
        assert apply_result["canceledAt"] == "2023-10-02T12:00:00Z"
        assert apply_result["executeRollback"] is True
        assert "Completed successfully." in caplog.text

    def test_get_applystatus_list_success_when_canceling_with_rollback_without_startedat(
        self, mocker, init_db_instance, caplog
    ):
        """Test successful retrieval when status is CANCELING and rollback has no startedAt."""
        mocker.patch("logging.config.dictConfig")

        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid])
            cursor.execute(query=sql.get_list_insert_sql_r_2_without_startedat, vars=[applyid])
        init_db_instance.commit()

        response = client.get("/cdim/api/v1/layout-apply/?status=CANCELING")

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response["totalCount"] == 1
        assert get_response["count"] == 1
        assert len(get_response["applyResults"]) == 1

        apply_result = get_response["applyResults"][0]
        assert apply_result["applyID"] == applyid
        assert apply_result["status"] == "CANCELING"
        assert apply_result["startedAt"] == "2023-10-01T23:59:59Z"
        assert apply_result["canceledAt"] == "2023-10-02T12:00:00Z"
        assert apply_result["executeRollback"] is True
        assert "rollback" not in apply_result
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?startedAtSince=2023-10-02T00:00:01Z&startedAtUntil=2023-10-02T00:00:02Z&endedAtSince=2023-10-02T12:24:00Z&endedAtUntil=2023-10-02T12:24:01Z",  # pylint: disable=C0301 # noqa: E501
        ],
    )
    def test_get_applystatus_list_success_when_time_equals_for_time_specification(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        """Test successful retrieval of apply status list when the time equals the specified time range."""
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        get_list_assert_target_equal = {
            "totalCount": 2,
            "count": 2,
            "applyResults": [
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
            ],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response["count"] == get_list_assert_target_equal["count"]
        assert get_response["totalCount"] == get_list_assert_target_equal["totalCount"]
        for apply_result in get_response["applyResults"]:
            assert apply_result in get_list_assert_target_equal["applyResults"]
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?startedAtSince=2023-10-02T00:00:02Z&startedAtUntil=2023-10-02T00:00:03Z&endedAtSince=2023-10-02T12:24:01Z&endedAtUntil=2023-10-02T12:24:02Z",  # pylint: disable=C0301 # noqa: E501
        ],
    )
    def test_get_applystatus_list_success_when_add_second_to_upper_time_limit(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        """Test successful retrieval of apply status list when the upper time limit is increased by one second."""
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        get_list_assert_target_plus1 = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": "000000005e",
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_plus1
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?startedAtSince=2023-10-02T00:00:00Z&startedAtUntil=2023-10-02T00:00:01Z&endedAtSince=2023-10-02T12:23:59Z&endedAtUntil=2023-10-02T12:24:00Z",  # pylint: disable=C0301 # noqa: E501
        ],
    )
    def test_get_applystatus_list_success_when_subtract_second_from_lower_time_limit(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        """Test successful retrieval of apply status list when the lower time limit is decreased by one second."""
        mocker.patch("logging.config.dictConfig")
        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        get_list_assert_target_minus1 = {
            "totalCount": 2,
            "count": 2,
            "applyResults": [
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
            ],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response["count"] == get_list_assert_target_minus1["count"]
        assert get_response["totalCount"] == get_list_assert_target_minus1["totalCount"]
        for apply_result in get_response["applyResults"]:
            assert apply_result in get_list_assert_target_minus1["applyResults"]
        assert "Completed successfully." in caplog.text

    def test_get_applystatus_list_success_when_no_specified_sortby_and_orderby_and_count_offset(
        self, mocker, init_db_instance, caplog, docker_services
    ):  # pylint: disable=W0613
        """Test successful retrieval of apply status list when no sortBy, orderBy, count, and offset are specified."""
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger()
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/?status=IN_PROGRESS"
        response = client.get(request_uri)

        assert_target = {"totalCount": 1, "count": 1}
        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response["count"] == assert_target["count"]
        assert get_response["totalCount"] == assert_target["totalCount"]

        assert "Completed successfully." in caplog.text
        log_msg = json.loads(caplog.messages[11]).get("message")
        assert "ORDER BY startedAt desc " in log_msg
        assert "LIMIT 20 " in log_msg
        assert "OFFSET 0" in log_msg

    def test_get_applystatus_list_success_when_specified_offset_exceed_data_count_registered_database(
        self, mocker, init_db_instance, caplog
    ):
        """Test successful retrieval of apply status list when the specified offset exceeds
        the data count in the registered database."""
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/?offset=10"
        response = client.get(request_uri)

        assert_target = {"totalCount": 9, "count": 0, "applyResults": []}

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == assert_target
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?sortBy=endedAt",
            "?sortBy=startedAt",
            "?orderBy=asc",
            "?orderBy=desc",
            "?limit=10",
            "?limit=2",
            "?offset=0",
            "?offset=1",
        ],
    )
    def test_get_applystatus_listsuccess_when_specified_sortby_and_orderby_and_count_offset(
        self, mocker, parameter_uri: str, init_db_instance, caplog
    ):
        """Test successful retrieval of apply status list when specified sortBy, orderBy,
        count, and offset are provided."""
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)
        count = 9
        if parameter_uri[1:].startswith("offset"):
            count = count - int(parameter_uri[-1])
        if parameter_uri[1:].startswith("limit") and int(re.findall(r"\d+", parameter_uri)[0]) < 9:
            count = int(parameter_uri[-1])

        assert_target = {"totalCount": 9, "count": count}

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response["count"] == assert_target["count"]
        assert get_response["totalCount"] == assert_target["totalCount"]

        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri, expected_ids",
        [
            ("?status=CANCELED&sortBy=startedAt&orderBy=asc", ["000000005e", "000000006f"]),
            ("?status=CANCELED&sortBy=startedAt&orderBy=desc", ["000000006f", "000000005e"]),
            ("?status=CANCELED&sortBy=endedAt&orderBy=asc", ["000000005e", "000000006f"]),
            ("?status=CANCELED&sortBy=endedAt&orderBy=desc", ["000000006f", "000000005e"]),
        ],
    )
    def test_get_applystatus_list_success_when_specified_sortby_and_orderby(
        self, mocker, parameter_uri: str, expected_ids: list[str], init_db_instance, caplog
    ):
        """Test successful retrieval with correct ordering when sortBy and orderBy are specified."""
        mocker.patch("logging.config.dictConfig")

        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        response = client.get(f"/cdim/api/v1/layout-apply/{parameter_uri}")

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response["totalCount"] == 2
        assert get_response["count"] == 2
        assert [result["applyID"] for result in get_response["applyResults"]] == expected_ids
        assert "Completed successfully." in caplog.text

    def test_get_applystatus_list_success_with_cancel_and_rollback_patterns(self, mocker, init_db_instance, caplog):
        """Test successful retrieval of apply status list with cancel and rollback patterns."""
        mocker.patch("logging.config.dictConfig")

        applyid_list = []

        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            # pattern 1: Cancelled and rollback
            applyid1 = create_randomname(IdParameter.LENGTH)
            applyid_list.append(applyid1)
            cursor.execute(
                query="""INSERT INTO applystatus
                    (applyid, status, procedures, result, rollbackprocedures,
                    startedat, endedat, canceledat, executerollback)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid1,
                    Result.CANCELED,
                    '{"procedures": "pre_test"}',
                    '[{"test": "test"}, {"test": "test"}]',
                    '{"procedures": "rollback_test"}',
                    "2023-10-03 00:00:00",
                    "2023-10-04 12:23:59",
                    "2023-10-03 12:00:00",
                    True,
                ),
            )
            cursor.execute(
                query="""INSERT INTO rollbackstatus
                    (applyid, status, procedures, result, startedat, endedat)
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid1,
                    Result.COMPLETED,
                    '{"procedures": "rollback_test"}',
                    '[{"test": "rollback_result"}]',
                    "2023-10-03 12:20:00",
                    "2023-10-04 12:23:59",
                ),
            )

            # pattern 2: Cancelled and multiple rollbacks
            applyid2 = create_randomname(IdParameter.LENGTH)
            applyid_list.append(applyid2)
            cursor.execute(
                query="""INSERT INTO applystatus
                    (applyid, status, procedures, result, rollbackprocedures,
                    startedat, endedat, canceledat, executerollback, resumeprocedures, resumedat, suspendedat)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid2,
                    Result.CANCELED,
                    '{"procedures": "apply_test"}',
                    '[{"operationID": 1, "status": "FAILED", "startedAt": "2023-10-11T00:00:00Z", \
                    "endedAt": "2023-10-11T09:00:00Z"}, {"operationID": 1, "status": "COMPLETED", \
                    "startedAt": "2023-10-11T10:00:00Z", "endedAt": "2023-10-11T14:50:00Z"}, \
                    {"operationID": 2, "status": "FAILED", "startedAt": "2023-10-11T14:50:00Z", \
                    "endedAt": "2023-10-11T15:00:00Z"}]',
                    '{"procedures": "rollback_test"}',
                    "2023-10-11 00:00:00",
                    "2023-10-11 16:00:00",
                    "2023-10-11 15:00:00",
                    True,
                    '[{"resume": 1, "procedure": "retry_after_suspend"}]',
                    "2023-10-11 10:00:00",
                    "2023-10-11 09:00:00",
                ),
            )
            cursor.execute(
                query="""INSERT INTO rollbackstatus
                    (applyid, status, procedures, result, startedat, endedat, resumeprocedures, resumedat, suspendedat)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid2,
                    Result.COMPLETED,
                    '{"procedures": "rollback_test"}',
                    '[{"operationID": 2, "status": "FAILED", "startedAt": "2023-10-11T15:10:00Z", \
                    "endedAt": "2023-10-11T15:30:00Z"}, {"operationID": 2, "status": "COMPLETED", \
                    "startedAt": "2023-10-11T15:40:00Z", "endedAt": "2023-10-11T15:50:00Z"}, \
                    {"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-11T15:50:00Z", \
                    "endedAt": "2023-10-11T16:00:00Z"}]',
                    "2023-10-11 15:10:00",
                    "2023-10-11 16:00:00",
                    '[{"resume": 1, "procedure": "retry_rollback"}]',
                    "2023-10-11 15:40:00",
                    "2023-10-11 15:30:00",
                ),
            )

            # pattern 3: interrupt and resume during rollback
            applyid3 = create_randomname(IdParameter.LENGTH)
            applyid_list.append(applyid3)
            cursor.execute(
                query="""INSERT INTO applystatus
                    (applyid, status, procedures, result, rollbackprocedures,
                    startedat, endedat, canceledat, executerollback)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid3,
                    Result.CANCELED,
                    '{"procedures": "apply_test"}',
                    '[{"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-15T10:00:00Z", \
                    "endedAt": "2023-10-15T11:00:00Z"}, {"operationID": 2, "status": "COMPLETED", \
                    "startedAt": "2023-10-15T11:00:00Z", "endedAt": "2023-10-15T12:00:00Z"}]',
                    '{"procedures": "rollback_test"}',
                    "2023-10-15 10:00:00",
                    "2023-10-15 16:00:00",
                    "2023-10-15 12:30:00",
                    True,
                ),
            )
            cursor.execute(
                query="""INSERT INTO rollbackstatus
                    (applyid, status, procedures, result, startedat, endedat, resumeprocedures, resumedat, suspendedat)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid3,
                    Result.COMPLETED,
                    '{"procedures": "rollback_test"}',
                    '[{"operationID": 2, "status": "FAILED", "startedAt": "2023-10-15T13:00:00Z", \
                    "endedAt": "2023-10-15T14:00:00Z"}, {"operationID": 2, "status": "COMPLETED", \
                    "startedAt": "2023-10-15T15:00:00Z", "endedAt": "2023-10-15T15:30:00Z"},\
                    {"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-15T15:30:00Z", \
                    "endedAt": "2023-10-15T16:00:00Z"}]',
                    "2023-10-15 13:00:00",
                    "2023-10-15 16:00:00",
                    '{"procedures": "retry_rollback_after_suspend"}',
                    "2023-10-15 15:00:00",
                    "2023-10-15 14:00:00",
                ),
            )

            # pattern 4: Cancell after resume and rollback completed
            applyid4 = create_randomname(IdParameter.LENGTH)
            applyid_list.append(applyid4)
            cursor.execute(
                query="""INSERT INTO applystatus
                    (applyid, status, procedures, result, rollbackprocedures,
                    startedat, endedat, canceledat, executerollback, resumeprocedures, resumedat, suspendedat)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid4,
                    Result.CANCELED,
                    '{"procedures": "apply_test"}',
                    '[{"operationID": 1, "status": "FAILED", "startedAt": "2023-10-20T10:00:00Z", \
                    "endedAt": "2023-10-20T11:00:00Z"}, {"operationID": 1, "status": "COMPLETED", \
                    "startedAt": "2023-10-20T14:00:00Z", "endedAt": "2023-10-20T15:00:00Z"}, \
                    {"operationID": 2, "status": "CANCELED", "startedAt": "2023-10-20T15:00:00Z", \
                    "endedAt": "2023-10-20T15:30:00Z"}]',
                    '{"procedures": "rollback_test"}',
                    "2023-10-20 10:00:00",
                    "2023-10-20 17:00:00",
                    "2023-10-20 15:30:00",
                    True,
                    '{"procedures": "resume_after_suspend"}',
                    "2023-10-20 14:00:00",
                    "2023-10-20 11:00:00",
                ),
            )
            cursor.execute(
                query="""INSERT INTO rollbackstatus
                    (applyid, status, procedures, result, startedat, endedat)
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid4,
                    Result.COMPLETED,
                    '{"procedures": "rollback_test"}',
                    '[{"operationID": 2, "status": "COMPLETED", "startedAt": "2023-10-20T15:40:00Z", \
                    "endedAt": "2023-10-20T16:00:00Z"}, {"operationID": 1, "status": "COMPLETED", \
                    "startedAt": "2023-10-20T16:00:00Z", "endedAt": "2023-10-20T17:00:00Z"}]',
                    "2023-10-20 15:40:00",
                    "2023-10-20 17:00:00",
                ),
            )
        init_db_instance.commit()

        # act
        response = client.get("/cdim/api/v1/layout-apply")

        # assert
        assert response.status_code == 200
        get_response = json.loads(response.content.decode())

        assert get_response["totalCount"] == 4
        assert get_response["count"] == 4
        assert len(get_response["applyResults"]) == 4

        apply_results = get_response["applyResults"]
        results_by_id = {result["applyID"]: result for result in apply_results}

        # pattern 1: Cancelled and rollback
        result1 = results_by_id[applyid1]
        assert result1["status"] == "CANCELED"
        assert result1["executeRollback"] is True
        assert result1["startedAt"] == "2023-10-03T00:00:00Z"
        assert result1["endedAt"] == "2023-10-04T12:23:59Z"
        assert result1["canceledAt"] == "2023-10-03T12:00:00Z"
        assert "rollback" in result1
        assert result1["rollback"]["status"] == "COMPLETED"
        assert result1["rollback"]["startedAt"] == "2023-10-03T12:20:00Z"
        assert result1["rollback"]["endedAt"] == "2023-10-04T12:23:59Z"

        # pattern 2: Cancelled and multiple rollbacks
        result2 = results_by_id[applyid2]
        assert result2["status"] == "CANCELED"
        assert result2["executeRollback"] is True
        assert result2["startedAt"] == "2023-10-11T00:00:00Z"
        assert result2["endedAt"] == "2023-10-11T16:00:00Z"
        assert result2["canceledAt"] == "2023-10-11T15:00:00Z"
        assert result2["suspendedAt"] == "2023-10-11T09:00:00Z"
        assert result2["resumedAt"] == "2023-10-11T10:00:00Z"
        assert "rollback" in result2
        assert result2["rollback"]["status"] == "COMPLETED"
        assert result2["rollback"]["startedAt"] == "2023-10-11T15:10:00Z"
        assert result2["rollback"]["endedAt"] == "2023-10-11T16:00:00Z"

        # pattern 3: interrupt and resume during rollback
        result3 = results_by_id[applyid3]
        assert result3["status"] == "CANCELED"
        assert result3["executeRollback"] is True
        assert result3["startedAt"] == "2023-10-15T10:00:00Z"
        assert result3["endedAt"] == "2023-10-15T16:00:00Z"
        assert result3["canceledAt"] == "2023-10-15T12:30:00Z"
        assert "rollback" in result3
        assert result3["rollback"]["status"] == "COMPLETED"
        assert result3["rollback"]["startedAt"] == "2023-10-15T13:00:00Z"
        assert result3["rollback"]["endedAt"] == "2023-10-15T16:00:00Z"

        # pattern 4: Cancell after resume and rollback completed
        result4 = results_by_id[applyid4]
        assert result4["status"] == "CANCELED"
        assert result4["executeRollback"] is True
        assert result4["startedAt"] == "2023-10-20T10:00:00Z"
        assert result4["endedAt"] == "2023-10-20T17:00:00Z"
        assert result4["canceledAt"] == "2023-10-20T15:30:00Z"
        assert result4["suspendedAt"] == "2023-10-20T11:00:00Z"
        assert result4["resumedAt"] == "2023-10-20T14:00:00Z"
        assert "rollback" in result4
        assert result4["rollback"]["status"] == "COMPLETED"
        assert result4["rollback"]["startedAt"] == "2023-10-20T15:40:00Z"
        assert result4["rollback"]["endedAt"] == "2023-10-20T17:00:00Z"

        assert "Completed successfully." in caplog.text


class TestGetListAPIServerFailure:
    """Test cases for general server failures."""

    def test_get_applystatus_list_failure_when_query_failure_occurred(
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
        response = client.get("/cdim/api/v1/layout-apply")

        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40019"
        assert "Query failed." in error_response["message"]
        assert "[E40019]Query failed." in caplog.text

    def test_get_applystatus_list_failure_when_failed_db_connection(self, mocker):
        """Test failure when the database connection cannot be established."""
        # arrange
        mocker.patch.object(DbAccess, "get_apply_status_list", side_effect=psycopg2.OperationalError)

        # act
        response = client.get("/cdim/api/v1/layout-apply")
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40018"
        assert "Could not connect to ApplyStatusDB." in error_response["message"]

    @pytest.mark.parametrize(
        "query_parameter",
        [
            {"status": "IN_PROGRES"},
            {"status": ""},
            {"startedAtSince": "T11:11:11Z"},
            {"startedAtSince": "20231102T111111Z"},
            {"startedAtSince": "2023-11-02 11:11:11"},
            {"startedAtSince": "2023/11/02T11:11:11Z"},
            {"startedAtSince": "20231102T11:11:11Z"},
            {"startedAtSince": "2023-11-0211:11:11Z"},
            {"startedAtSince": ""},
            {"startedAtUntil": "2023-11-02"},
            {"startedAtUntil": "T11:11:11Z"},
            {"startedAtUntil": "20231102T111111Z"},
            {"startedAtUntil": "2023-11-02 11:11:11"},
            {"startedAtUntil": "2023/11/02T11:11:11Z"},
            {"startedAtUntil": "20231102T11:11:11Z"},
            {"startedAtUntil": "2023-11-0211:11:11Z"},
            {"startedAtUntil": ""},
            {"endedAtSince": "2023-11-02"},
            {"endedAtSince": "T11:11:11Z"},
            {"endedAtSince": "20231102T111111Z"},
            {"endedAtSince": "2023-11-02 11:11:11"},
            {"endedAtSince": "2023/11/02T11:11:11Z"},
            {"endedAtSince": "20231102T11:11:11Z"},
            {"endedAtSince": "2023-11-0211:11:11Z"},
            {"endedAtSince": ""},
            {"endedAtUntil": "2023-11-02"},
            {"endedAtUntil": "T11:11:11Z"},
            {"endedAtUntil": "20231102T111111Z"},
            {"endedAtUntil": "2023-11-02 11:11:11"},
            {"endedAtUntil": "2023/11/02T11:11:11Z"},
            {"endedAtUntil": "20231102T11:11:11Z"},
            {"endedAtUntil": "2023-11-0211:11:11Z"},
            {"endedAtUntil": ""},
            {"endedAtUntil": "2023-11-02T11:11:11+"},
            {"endedAtUntil": "2023-11-02T11:11:11-09"},
            {"endedAtUntil": "2023-11-02T11:11:11-24:00"},
            {"endedAtUntil": "2023-11-02T11:11:11Z+09:00"},
            {"sortBy": ""},
            {"sortBy": "status"},
            {"orderBy": ""},
            {"orderBy": "new"},
            {"limit": ""},
            {"limit": "-1"},
            {"offset": ""},
            {"offset": "-1"},
        ],
    )
    def test_get_applystatus_list_failure_when_invalid_parameter(self, query_parameter):
        """Test failure when an invalid query parameter is provided."""
        request_uri = "/cdim/api/v1/layout-apply/"
        encoded_params = urllib.parse.urlencode(query_parameter)
        full_url = f"{request_uri}?{encoded_params}"

        response = client.get(full_url)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    @pytest.mark.parametrize(
        "query_parameter",
        [
            {"startedAtSince": "0000-11-02T11:11:11+09:00"},
        ],
    )
    def test_get_applystatus_list_failure_when_invalid_time_specification(self, query_parameter):
        """Test failure when an invalid time specification is provided."""
        request_uri = "/cdim/api/v1/layout-apply/"
        encoded_params = urllib.parse.urlencode(query_parameter)
        full_url = f"{request_uri}?{encoded_params}"

        response = client.get(full_url)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    @pytest.mark.parametrize(
        "params",
        [
            ({"fields": [""]}),  # empty string
            ({"fields": ["procedure"]}),  # invalid name
            ({"fields": ["applyresult"]}),  # invalid name
            ({"fields": ["rollbackProcedure"]}),  # invalid name
            ({"fields": ["rollbackresult"]}),  # invalid name
        ],
    )
    def test_get_applystatus_list_failure_when_invalid_field(self, params):
        """Test failure when invalid fields are specified."""
        # arrange

        response = client.get("/cdim/api/v1/layout-apply", params=params)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    def test_get_applystatus_list_failure_when_duplicate_fields_specified(self):
        """Test failure when duplicate fields are specified."""
        response = client.get(
            "/cdim/api/v1/layout-apply",
            params=[("fields", "procedures"), ("fields", "procedures")],
        )

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"


class TestGetListAPIServerConfigFailure:
    """Test cases for failures in server configuration loading."""

    def test_get_applystatus_list_failure_when_failed_to_load_config_file(self, mocker):
        """Test failure when server config cannot be loaded."""

        mocker.patch(
            "yaml.safe_load", side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")]
        )

        response = client.get("/cdim/api/v1/layout-apply")
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_config.yaml.\n('Dummy message',)"

    def test_get_applystatus_list_failure_when_failed_to_load_log_config_file(
        self, mocker, docker_services
    ):  # pylint: disable=W0613
        """Test failure when log config cannot be loaded."""
        mocker.patch.object(LayoutApplyLogConfig, "_validate_log_dir", side_effect=[Exception("Dummy message")])

        # arrange
        response = client.get("/cdim/api/v1/layout-apply")
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_log_config.yaml.\n('Dummy message',)"
