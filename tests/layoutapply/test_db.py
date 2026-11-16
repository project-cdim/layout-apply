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
"""Test for the db"""

import datetime
import io
import logging.config
from logging import INFO

import psycopg2
import psycopg2.extras
import pytest
from psycopg2.extras import DictCursor

from layoutapply.const import IdParameter, Result
from layoutapply.custom_exceptions import IdNotFoundException, MultipleInstanceError, SuspendedDataExistException
from layoutapply.db import DbAccess, GetAllOption, UpdateOption
from layoutapply.util import create_randomname
from tests.layoutapply.test_data import sql


class TestDbAccess:
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
            sql.get_list_insert_sql_9,
        ]
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        for insert_sql in get_applystatus_list:
            applyid = create_randomname(IdParameter.LENGTH)
            id_list.append(applyid)
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()
        return id_list

    def test_register_registered_in_db(self, mocker, get_db_instance, init_db_instance):
        mocker.patch.object(DbAccess, "close", return_value=None)
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        id_ = get_db_instance.register({})

        assert len(id_) == 10

    def test_register_query_failure_occurred(
        self,
        mocker,
        get_db_instance,
    ):
        mock_cursor = mocker.MagicMock()

        mock_cursor.execute.side_effect = [None, psycopg2.ProgrammingError]

        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)

        # psycopg2.extras.DictCursor is mocked
        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        with pytest.raises(psycopg2.ProgrammingError):
            _ = get_db_instance.register({})

    def test_register_integrityerror_occurred(self, mocker, get_db_instance, docker_services):
        result = {
            "applyid": "000000001a",
            "status": "COMPLETED",
            "rollbackstatus": None,
        }
        mock_connect = mocker.Mock()
        mocker.patch("psycopg2.connect", mock_connect)

        mock_cursor = mocker.Mock()
        mock_connect.return_value.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 0
        mock_cursor.fetchone.side_effect = [result, result]
        mock_cursor.execute.side_effect = [None, None, psycopg2.IntegrityError, None, None]

        # psycopg2.extras.DictCursor is mocked
        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        assert len(get_db_instance.register({})) == 10
        assert mock_cursor.execute.call_count == 5

    def test_register_multipleinstancerrror_occurred(self, mocker, get_db_instance, docker_services):
        result = {
            "applyid": "000000001a",
            "status": "IN_PROGRESS",
            "rollbackstatus": None,
        }
        mock_connect = mocker.Mock()
        mocker.patch("psycopg2.connect", mock_connect)

        mock_cursor = mocker.Mock()
        mock_connect.return_value.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 0
        mock_cursor.fetchone.side_effect = [result]
        mock_cursor.execute.side_effect = [None, [1], None]

        with pytest.raises(MultipleInstanceError):
            get_db_instance.register({})
            assert mock_cursor.execute.call_count == 4

    def test_register_suspendeddataexistexception_occurred(self, mocker, get_db_instance, docker_services):
        result = {
            "applyid": "000000009c",
            "status": "SUSPENDED",
            "procedures": '{"procedures": "pre_test"}',
            "applyresult": [{"test": "test"}, {"test": "test"}],
            "rollbackprocedures": None,
            "startedat": datetime.datetime(2023, 10, 2, 0, 0),
            "endedat": datetime.datetime(2023, 10, 2, 0, 0),
            "canceledat": datetime.datetime(2023, 10, 2, 0, 0),
            "executerollback": None,
            "rollbackstatus": None,
            "rollbackresult": None,
            "rollbackstartedat": datetime.datetime(2023, 10, 2, 0, 0),
            "rollbackendedat": datetime.datetime(2023, 10, 2, 0, 0),
            "resumeprocedures": None,
            "resumeresult": None,
            "suspendedat": datetime.datetime(2023, 10, 2, 0, 0),
            "resumedat": datetime.datetime(2023, 10, 2, 0, 0),
        }
        mock_connect = mocker.Mock()
        mocker.patch("psycopg2.connect", mock_connect)

        mock_cursor = mocker.Mock()
        mock_connect.return_value.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 0
        mock_cursor.fetchone.side_effect = [result]
        mock_cursor.execute.side_effect = [None, [1], None]

        with pytest.raises(SuspendedDataExistException):
            get_db_instance.register({})
            assert mock_cursor.execute.call_count == 4

    @pytest.mark.parametrize(
        "args",
        [
            # no optional items.
            (
                {
                    "applyID": "123456789a",
                    "status": "COMPLETED",
                    "procedures": None,
                    "applyresult": [],
                    "rollbackprocedures": [],
                    "rollback_status": "",
                    "rollback_result": {},
                    "resumeprocedures": [],
                    "resume_result": [],
                }
            ),
            (
                {
                    "applyID": "123456789a",
                    "status": "",
                    "procedures": None,
                    "applyresult": [],
                    "rollbackprocedures": [],
                    "rollback_status": "COMPLETED",
                    "rollback_result": {},
                    "resumeprocedures": [],
                    "resume_result": [],
                }
            ),
        ],
    )
    def test_update_success_when_no_optional_configuration_item(self, mocker, args, get_db_instance, init_db_instance):
        # arrange
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
        init_db_instance.commit()
        args["applyID"] = applyid

        mock_con = mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)

        get_db_instance.update(UpdateOption(**args))
        assert mock_con.call_count == 1

    @pytest.mark.parametrize(
        "args",
        [
            # all options(CANCELED)
            (
                {
                    "applyID": "123456789d",
                    "status": "CANCELED",
                    "procedures": {"procedures": "test"},
                    "applyresult": [
                        {"test": "test"},
                        {"test": "test"},
                        {"test": "test"},
                    ],
                    "rollbackprocedures": [
                        {"test": "test"},
                        {"test": "test"},
                        {"test": "test"},
                    ],
                    "rollback_status": "",
                    "rollback_result": {},
                    "resumeprocedures": [],
                    "resume_result": [],
                }
            ),
        ],
    )
    def test_update_success_when_status_canceled(self, mocker, args, get_db_instance, init_db_instance):
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
        init_db_instance.commit()
        args["applyID"] = applyid
        mock_con = mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)

        get_db_instance.update(UpdateOption(**args))
        assert mock_con.call_count == 1

    @pytest.mark.parametrize(
        "args",
        [
            # FAILED
            (
                {
                    "applyID": "123456789d",
                    "status": "FAILED",
                    "procedures": {"procedures": "test"},
                    "applyresult": [
                        {"test": "test"},
                        {"test": "test"},
                        {"test": "test"},
                    ],
                    "rollbackprocedures": [],
                    "rollback_status": "",
                    "rollback_result": {},
                    "resumeprocedures": [],
                    "resume_result": [],
                }
            ),
        ],
    )
    def test_update_success_when_status_failed(self, mocker, args, get_db_instance, init_db_instance):
        # arrange
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
        init_db_instance.commit()
        args["applyID"] = applyid
        mock_con = mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)

        get_db_instance.update(UpdateOption(**args))
        assert mock_con.call_count == 1

    @pytest.mark.parametrize(
        "args",
        [
            # no rollbackprocedures
            (
                {
                    "applyID": "123456789a",
                    "status": "COMPLETED",
                    "procedures": {"procedures": "test"},
                    "applyresult": [
                        {"test": "test"},
                        {"test": "test"},
                        {"test": "test"},
                    ],
                    "rollbackprocedures": [],
                    "rollback_status": "",
                    "rollback_result": {},
                    "resumeprocedures": [],
                    "resume_result": [],
                }
            ),
        ],
    )
    def test_update_success_when_status_completed(self, mocker, args, get_db_instance, init_db_instance):
        # arrange
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
        init_db_instance.commit()
        args["applyID"] = applyid
        mock_con = mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)

        get_db_instance.update(UpdateOption(**args))
        assert mock_con.call_count == 1

    @pytest.mark.parametrize(
        "args",
        [
            (
                {
                    "applyID": "300000001a",
                    "status": "COMPLETED",
                    "procedures": None,
                    "applyresult": [],
                    "rollbackprocedures": [],
                    "rollback_status": "",
                    "rollback_result": {},
                    "resumeprocedures": [],
                    "resume_result": [
                        {"test": "test"},
                        {"test": "test"},
                        {"test": "test"},
                    ],
                }
            ),
        ],
    )
    def test_update_success_when_on_resume(self, mocker, args, get_db_instance, init_db_instance):
        # arrange
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.insert_resumed_get_target_sql_1, vars=[applyid])
        init_db_instance.commit()
        args["applyID"] = applyid
        mock_con = mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)

        get_db_instance.update(UpdateOption(**args))
        assert mock_con.call_count == 1

    def test_update_failure_when_query_failure_occurred(self, mocker, get_db_instance):
        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = [None, psycopg2.ProgrammingError]
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)

        # psycopg2.extras.DictCursor is mocked
        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        with pytest.raises(psycopg2.ProgrammingError):
            get_db_instance.update(UpdateOption(None, None, None, None, None, None, None, None, None))
            assert mock_cursor.fetchone.call_count == 2

    def test_update_failure_when_nonexistent_id(self, mocker, get_db_instance, init_db_instance):
        mock_cursor = mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)

        with pytest.raises(IdNotFoundException):
            get_db_instance.update(UpdateOption("NoExitsId", None, None, None, None, None, None, None, None))

            applystatus = get_db_instance.get_apply_status(None)
            assert applystatus == {}
            assert mock_cursor.execute.call_count == 1

    def test_get_applystatus_success_when_status_canceled_rollback_false(
        self, mocker, get_db_instance, init_db_instance
    ):
        # arrange
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid])
        init_db_instance.commit()
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)

        # act
        applystatus = get_db_instance.get_apply_status(applyid)

        # assert
        assert applystatus["applyID"] == applyid
        assert applystatus["status"] == "CANCELED"
        assert applystatus["procedures"] == {"procedures": "pre_test"}
        assert applystatus["applyResult"] == [{"test": "test"}, {"test": "test"}]
        assert applystatus["rollbackProcedures"] == {"test": "test"}
        assert applystatus["startedAt"] == "2023-10-02T00:00:02Z"
        assert applystatus["endedAt"] == "2023-10-02T12:24:01Z"
        assert applystatus["canceledAt"] == "2023-10-02T12:00:00Z"
        assert applystatus["executeRollback"] is False
        assert "rollbackResult" not in applystatus
        assert "rollbackStatus" not in applystatus
        assert "resumeResult" not in applystatus

    def test_get_applystatus_success_when_status_canceled_rollback_true(
        self, mocker, get_db_instance, init_db_instance
    ):
        # arrange
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid])
        init_db_instance.commit()
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        applystatus = get_db_instance.get_apply_status(applyid)

        assert applystatus["applyID"] == applyid
        assert applystatus["status"] == "CANCELED"
        assert applystatus["procedures"] == {"procedures": "pre_test"}
        assert applystatus["applyResult"] == [{"test": "test"}, {"test": "test"}]
        assert applystatus["rollbackProcedures"] == {"test": "test"}
        assert applystatus["startedAt"] == "2023-10-03T00:00:00Z"
        assert applystatus["endedAt"] == "2023-10-04T12:23:59Z"
        assert applystatus["canceledAt"] == "2023-10-03T12:00:00Z"
        assert applystatus["executeRollback"] is True
        assert applystatus["rollbackResult"] == [{"test": "test"}, {"test": "test"}]
        assert applystatus["rollbackStatus"] == "COMPLETED"
        assert applystatus["rollbackStartedAt"] == "2023-10-03T12:20:00Z"
        assert applystatus["rollbackEndedAt"] == "2023-10-04T12:23:59Z"
        assert "resumeResult" not in applystatus

    def test_get_applystatus_success_when_status_completed(self, mocker, get_db_instance, init_db_instance):
        # arrange
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.get_list_insert_sql_3, vars=[applyid])
        init_db_instance.commit()
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        applystatus = get_db_instance.get_apply_status(applyid)

        assert applystatus["applyID"] == applyid
        assert applystatus["status"] == "COMPLETED"
        assert applystatus["procedures"] == {"procedures": "pre_test"}
        assert applystatus["applyResult"] == [{"test": "test"}, {"test": "test"}]
        assert applystatus["startedAt"] == "2023-10-02T00:00:00Z"
        assert applystatus["endedAt"] == "2023-10-02T12:23:59Z"
        assert "rollbackProcedures" not in applystatus
        assert "canceledAt" not in applystatus
        assert "executeRollback" not in applystatus
        assert "rollbackResult" not in applystatus
        assert "rollbackStatus" not in applystatus
        assert "resumeResult" not in applystatus

    def test_get_applystatus_success_when_status_in_progress(self, mocker, get_db_instance, init_db_instance):
        # Data adjustment before testing.
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
        init_db_instance.commit()
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        applystatus = get_db_instance.get_apply_status(applyid)

        assert applystatus["applyID"] == applyid
        assert applystatus["status"] == "IN_PROGRESS"
        assert applystatus["procedures"] == {"procedures": "pre_test"}
        assert "applyResult" not in applystatus
        assert "rollbackProcedures" not in applystatus
        assert applystatus["startedAt"] == "2023-10-02T00:00:00Z"
        assert "endedAt" not in applystatus
        assert "canceledAt" not in applystatus
        assert "executeRollback" not in applystatus
        assert "rollbackResult" not in applystatus
        assert "rollbackStatus" not in applystatus
        assert "resumeResult" not in applystatus

    def test_get_applystatus_success_when_status_canceling(self, mocker, get_db_instance, init_db_instance):
        # arrange
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid])
        init_db_instance.commit()
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)

        # act
        applystatus = get_db_instance.get_apply_status(applyid)

        # assert
        assert applystatus["applyID"] == applyid
        assert applystatus["status"] == "CANCELING"
        assert applystatus["procedures"] == {"procedures": "pre_test"}
        assert applystatus["applyResult"] == [{"test": "test"}, {"test": "test"}]
        assert applystatus["rollbackProcedures"] == {"test": "test"}
        assert applystatus["startedAt"] == "2023-10-01T23:59:59Z"
        assert applystatus["endedAt"] == "2023-10-02T12:23:58Z"
        assert applystatus["canceledAt"] == "2023-10-02T12:00:00Z"
        assert applystatus["executeRollback"] is True
        assert "rollbackResult" not in applystatus
        assert "rollbackStatus" not in applystatus
        assert "resumeResult" not in applystatus

    def test_get_applystatus_success_when_on_resume(self, mocker, get_db_instance, init_db_instance):
        # arrange
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.insert_resumed_get_target_sql_3, vars=[applyid])
        init_db_instance.commit()
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)

        applystatus = get_db_instance.get_apply_status(applyid)

        # assert
        assert applystatus["applyID"] == applyid
        assert applystatus["status"] == "COMPLETED"
        assert applystatus["procedures"] == {"procedures": "pre_test"}
        assert applystatus["applyResult"] == [{"test": "test"}, {"test": "test"}]
        assert "rollbackProcedures" not in applystatus
        assert applystatus["startedAt"] == "2023-10-02T00:00:00Z"
        assert applystatus["endedAt"] == "2023-10-02T12:23:59Z"
        assert "canceledAt" not in applystatus
        assert "executeRollback" not in applystatus
        assert "rollbackResult" not in applystatus
        assert "rollbackStatus" not in applystatus
        assert applystatus["resumeProcedures"] == {"test": "pre_test"}
        assert applystatus["resumeResult"] == [{"test": "test"}, {"test": "test"}]
        assert applystatus["suspendedAt"] == "2023-10-02T12:23:59Z"
        assert applystatus["resumedAt"] == "2023-10-03T12:23:59Z"

    def test_get_applystatus_failure_when_nonexistent_id(self, mocker, get_db_instance, docker_services):
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.side_effect = [None]
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)

        # psycopg2.extras.DictCursor is mocked
        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        with pytest.raises(IdNotFoundException):
            get_db_instance.get_apply_status("no_exsits_key")

    def test_get_applystatus_failure_when_query_failure_occurred(self, mocker, get_db_instance):
        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = [None, psycopg2.ProgrammingError]
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)

        # psycopg2.extras.DictCursor is mocked
        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        with pytest.raises(psycopg2.ProgrammingError):
            get_db_instance.update(UpdateOption(None, None, None, None, None, None, None, None, None))
            assert mock_cursor.execute.call_count == 2

    def test_requst_cancel_failure_when_no_update_target_on_cancel(self, mocker, get_db_instance, init_db_instance):
        mock_cursor = mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        get_db_instance._open_db_connection()
        with pytest.raises(IdNotFoundException):
            get_db_instance._requst_cancel("NoExitsId", True, "IN_PROGRESS")
            applystatus = get_db_instance.get_apply_status(None)
            assert applystatus == {}
            assert mock_cursor.execute.call_count == 1

    def test_execute_query_rollback_executed_when_query_failed_and_rollback_true(self, mocker, get_db_instance):
        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = [None, psycopg2.ProgrammingError]
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)

        # psycopg2.extras.DictCursor is mocked
        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)
        dummy_db_access = get_db_instance

        with pytest.raises(psycopg2.ProgrammingError):
            dummy_db_access = get_db_instance
            dummy_db_access._open_db_connection()
            dummy_db_access._execute_query("Select * from Dummy", None, True)

    def test_get_running_data_success(self, mocker, get_db_instance, init_db_instance):
        # arrange
        get_applystatus_list = [
            sql.get_list_insert_sql_1,
            sql.get_list_insert_sql_2,
            sql.get_list_insert_sql_9,
        ]
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        for insert_sql in get_applystatus_list:
            applyid = create_randomname(IdParameter.LENGTH)
            cursor.execute(query=insert_sql, vars=[applyid])
        init_db_instance.commit()
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        get_db_instance._open_db_connection()
        result = get_db_instance._get_running_data()

        # asseert
        assert "applyID" in result
        assert result["status"] in [
            Result.IN_PROGRESS,
            Result.CANCELING,
            Result.SUSPENDED,
        ]

    @pytest.mark.parametrize(
        "args",
        [
            (
                {
                    "applyID": "123456789a",
                    "rollback_status": "IN_PROGRESS",
                    "rollback_procedures_list": [{"test": "test"}],
                }
            ),
        ],
    )
    def test_update_rollback_status_success(self, mocker, args, get_db_instance, init_db_instance):
        # Data adjustment before testing.
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid])
        init_db_instance.commit()
        mock_con = mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        args["applyID"] = applyid

        get_db_instance.update_rollback_status(**args)
        assert mock_con.call_count == 1

    def test_update_rollback_status_failure_when_query_failure_occurred(self, mocker, get_db_instance):
        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = [None, psycopg2.ProgrammingError]
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)

        # psycopg2.extras.DictCursor is mocked
        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        with pytest.raises(psycopg2.ProgrammingError):
            get_db_instance.update_rollback_status(None, None, None)
            assert mock_cursor.fetchone.call_count == 2

    def test_update_rollback_status_failure_when_nonexistent_id(self, mocker, get_db_instance, init_db_instance):
        mock_cursor = mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)

        with pytest.raises(IdNotFoundException):
            get_db_instance.update_rollback_status("NoExitsId", None, None)
            applystatus = get_db_instance.get_apply_status(None)
            assert applystatus == {}
            assert mock_cursor.execute.call_count == 1

    def test_get_applystatus_status_list_success_when_no_target_to_retrieve(
        self, mocker, get_db_instance, init_db_instance
    ):

        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        date_dict = {
            "startedat_since": None,
            "startedat_until": None,
            "endedat_since": None,
            "endedat_until": None,
        }
        applystatus = get_db_instance.get_apply_status_list(
            GetAllOption(
                limit=20,
                fields=None,
                offset=0,
                orderBy="desc",
                sortBy="startedAt",
                status=None,
                date_dict=date_dict,
            )
        )

        assert_target = {
            "totalCount": 0,
            "count": 0,
            "applyResults": [],
        }

        assert applystatus == assert_target

    def test_get_applystatus_status_list_success_when_all_search_conditions_specified(
        self, mocker, get_db_instance, init_db_instance
    ):
        # arrange
        id_list = self.insert_list_data(init_db_instance)
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        date_dict = {
            "startedat_since": "2023-10-02T00:00:02Z",
            "startedat_until": "2023-10-02T00:00:03Z",
            "endedat_since": "2023-10-02T12:24:01Z",
            "endedat_until": "2023-10-02T12:24:02Z",
        }
        # act
        applystatus = get_db_instance.get_apply_status_list(
            GetAllOption(
                limit=20,
                fields=None,
                offset=0,
                orderBy="desc",
                sortBy="startedAt",
                status="CANCELED",
                date_dict=date_dict,
            )
        )

        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": id_list[4],
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }
        # assert
        assert applystatus == get_list_assert_target_all

    def test_get_applystatus_status_list_success_when_status_specified(self, mocker, get_db_instance, init_db_instance):
        # arrange
        id_list = self.insert_list_data(init_db_instance)
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        date_dict = {}

        # act
        applystatus = get_db_instance.get_apply_status_list(
            GetAllOption(
                limit=20,
                fields=None,
                offset=0,
                orderBy="desc",
                sortBy="startedAt",
                status="IN_PROGRESS",
                date_dict=date_dict,
            )
        )

        get_list_assert_target_status = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "applyID": id_list[0],
                    "status": "IN_PROGRESS",
                    "startedAt": "2023-10-02T00:00:00Z",
                },
            ],
        }
        # asseert
        assert applystatus == get_list_assert_target_status

    def test_get_applystatus_status_list_success_when_only_start_time_start_specified(
        self, mocker, get_db_instance, init_db_instance
    ):
        # Data adjustment before testing.
        id_list = self.insert_list_data(init_db_instance)
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        date_dict = {"startedat_since": "2023-10-03T00:00:00Z"}

        applystatus = get_db_instance.get_apply_status_list(
            GetAllOption(
                limit=20,
                fields=None,
                offset=0,
                orderBy="desc",
                sortBy="startedAt",
                status=None,
                date_dict=date_dict,
            )
        )

        get_list_assert_target_started_at_since = {
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
                    "rollbackStatus": "COMPLETED",
                    "rollbackStartedAt": "2023-10-03T12:20:00Z",
                    "rollbackEndedAt": "2023-10-04T12:23:59Z",
                },
            ],
        }

        assert applystatus == get_list_assert_target_started_at_since

    def test_get_applystatus_status_list_success_when_only_start_time_end_specified(
        self, mocker, get_db_instance, init_db_instance
    ):
        # arrange
        id_list = self.insert_list_data(init_db_instance)
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        date_dict = {"startedat_until": "2023-10-01T23:59:59Z"}

        # act
        applystatus = get_db_instance.get_apply_status_list(
            GetAllOption(
                limit=20,
                fields=None,
                offset=0,
                orderBy="desc",
                sortBy="startedAt",
                status=None,
                date_dict=date_dict,
            )
        )

        get_list_assert_target_started_at_until = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELING",
                    "applyID": id_list[1],
                    "startedAt": "2023-10-01T23:59:59Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": True,
                },
            ],
        }

        # assert
        assert applystatus == get_list_assert_target_started_at_until

    def test_get_applystatus_status_list_success_when_only_end_time_start_specified(
        self, mocker, get_db_instance, init_db_instance
    ):
        # arrange
        id_list = self.insert_list_data(init_db_instance)
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        date_dict = {"endedat_since": "2023-10-03T00:00:00Z"}

        # act
        applystatus = get_db_instance.get_apply_status_list(
            GetAllOption(
                limit=20,
                fields=None,
                offset=0,
                orderBy="desc",
                sortBy="startedAt",
                status=None,
                date_dict=date_dict,
            )
        )

        get_list_assert_target_ended_at_since = {
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
                    "rollbackStatus": "COMPLETED",
                    "rollbackStartedAt": "2023-10-03T12:20:00Z",
                    "rollbackEndedAt": "2023-10-04T12:23:59Z",
                },
            ],
        }
        # assert
        assert applystatus == get_list_assert_target_ended_at_since

    def test_get_applystatus_status_list_success_when_only_end_time_end_specified(
        self, mocker, get_db_instance, init_db_instance
    ):
        # arrange
        id_list = self.insert_list_data(init_db_instance)
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        date_dict = {"endedat_until": "2023-10-02T12:23:59Z"}

        # act
        applystatus = get_db_instance.get_apply_status_list(
            GetAllOption(
                limit=20,
                fields=None,
                offset=0,
                orderBy="desc",
                sortBy="startedAt",
                status=None,
                date_dict=date_dict,
            )
        )

        get_list_assert_target_ended_at_until = {
            "totalCount": 2,
            "count": 2,
            "applyResults": [
                {
                    "status": "COMPLETED",
                    "applyID": id_list[2],
                    "startedAt": "2023-10-02T00:00:00Z",
                    "endedAt": "2023-10-02T12:23:59Z",
                },
                {
                    "status": "CANCELING",
                    "applyID": id_list[1],
                    "startedAt": "2023-10-01T23:59:59Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": True,
                },
            ],
        }
        # assert
        assert applystatus == get_list_assert_target_ended_at_until

    def test_delete_success(self, mocker, get_db_instance, init_db_instance):
        # arrange
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.get_list_insert_sql_3, vars=[applyid])
        init_db_instance.commit()

        mock_cursor = mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)

        with pytest.raises(IdNotFoundException):
            get_db_instance.delete("900000006f")
            applystatus = get_db_instance.get_apply_status("900000006f")
            assert applystatus == {}
            assert mock_cursor.execute.call_count == 1

    def test_delete_failure_when_nonexistent_id(self, mocker, get_db_instance, init_db_instance):
        mock_cursor = mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)

        with pytest.raises(IdNotFoundException):
            get_db_instance.delete("NoExitsId")
            assert mock_cursor.execute.call_count == 1

    def test_request_resume_failure_when_nonexistent_id(self, mocker, get_db_instance, init_db_instance):
        mock_cursor = mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        get_db_instance._open_db_connection()
        with pytest.raises(IdNotFoundException):
            get_db_instance._request_resume("NoExitsId", {"status": "SUSPENDED"})
            assert mock_cursor.execute.call_count == 1

    def test_proc_result_status_and_resumedate_updated(self, mocker, get_db_instance, init_db_instance):
        # arrange
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.insert_resumed_target_sql_1, vars=[applyid])
        init_db_instance.commit()
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)

        # act
        get_db_instance.proc_resume(applyid)
        applystatus = get_db_instance.get_apply_status(applyid)

        # assert
        assert applystatus["applyID"] == applyid
        assert applystatus["status"] == "IN_PROGRESS"
        assert "resumedAt" in applystatus

    def test_open_db_connection_failure_when_failed_db_connection(
        self, mocker, get_db_instance, caplog, docker_services
    ):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        mocker.patch("psycopg2.connect").side_effect = psycopg2.OperationalError
        mocker.patch("time.sleep", return_value=None)
        with pytest.raises(psycopg2.OperationalError):
            get_db_instance._open_db_connection()

        assert "Could not connect to ApplyStatusDB. Reconnecting count: 1" in caplog.text
        assert "Could not connect to ApplyStatusDB. Reconnecting count: 2" in caplog.text
        assert "Could not connect to ApplyStatusDB. Reconnecting count: 3" in caplog.text
        assert "Could not connect to ApplyStatusDB. Reconnecting count: 4" in caplog.text
        assert "Could not connect to ApplyStatusDB. Reconnecting count: 5" in caplog.text
        assert "[E40018]Could not connect to ApplyStatusDB." in caplog.text

    def test_register_check_if_a_SerializationFailure_occurs(self, mocker, get_db_instance, docker_services):
        err_func = psycopg2.errors.SerializationFailure
        err_func.pgcode = "40001"
        mock_cursor = mocker.MagicMock()
        err = [None, err_func, None, None]
        mock_cursor.execute.side_effect = err

        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mocker.patch("psycopg2.connect", return_value=mock_connection)

        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        id_ = get_db_instance.register({})

        assert len(id_) == 10

    @pytest.mark.parametrize(
        "args",
        [
            # no optional items.
            (
                {
                    "applyID": "123456789a",
                    "status": "COMPLETED",
                    "procedures": None,
                    "applyresult": [],
                    "rollbackprocedures": [],
                    "rollback_status": "",
                    "rollback_result": {},
                    "resumeprocedures": [],
                    "resume_result": [],
                }
            ),
            (
                {
                    "applyID": "123456789a",
                    "status": "",
                    "procedures": None,
                    "applyresult": [],
                    "rollbackprocedures": [],
                    "rollback_status": "COMPLETED",
                    "rollback_result": {},
                    "resumeprocedures": [],
                    "resume_result": [],
                }
            ),
        ],
    )
    def test_update_check_if_a_SerializationFailure_occurs(self, mocker, get_db_instance, docker_services, args):
        err_func = psycopg2.errors.SerializationFailure
        err_func.pgcode = "40001"
        mock_cursor = mocker.MagicMock()
        mock_cursor.rowcount = 1
        err = [None, err_func, None, None]
        mock_cursor.execute.side_effect = err

        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_conn = mocker.patch("psycopg2.connect", return_value=mock_connection)

        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        get_db_instance.update(UpdateOption(**args))
        assert mock_conn.call_count == 1

    @pytest.mark.parametrize(
        "args",
        [
            (
                {
                    "applyID": "123456789a",
                    "rollback_status": "IN_PROGRESS",
                    "rollback_procedures_list": {"test": "test"},
                }
            ),
        ],
    )
    def test_update_rollback_status_check_if_a_SerializationFailure_occurs(
        self, mocker, args, docker_services, get_db_instance
    ):
        err_func = psycopg2.errors.SerializationFailure
        err_func.pgcode = "40001"
        mock_cursor = mocker.MagicMock()
        mock_cursor.rowcount = 1
        err = [None, err_func, None, None]
        mock_cursor.execute.side_effect = err

        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_conn = mocker.patch("psycopg2.connect", return_value=mock_connection)

        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        get_db_instance.update_rollback_status(**args)
        assert mock_conn.call_count == 1

    @pytest.mark.parametrize(
        "args",
        [
            (
                {
                    "applyID": "123456789a",
                    "rollback_status": "IN_PROGRESS",
                    "rollback_procedures_list": [{"test": "test"}],
                }
            ),
        ],
    )
    def test_get_apply_status_check_if_a_SerializationFailure_occurs(
        self, mocker, get_db_instance, docker_services, args
    ):
        err_func = psycopg2.errors.SerializationFailure
        err_func.pgcode = "40001"
        mock_cursor = mocker.MagicMock()
        mock_cursor.rowcount = 1
        err = [None, err_func, None, None]
        mock_cursor.execute.side_effect = err

        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_conn = mocker.patch("psycopg2.connect", return_value=mock_connection)

        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)
        get_db_instance.update_rollback_status(**args)
        assert mock_conn.call_count == 1

    def test_get_apply_status_list_check_if_a_SerializationFailure_occurs(
        self, mocker, get_db_instance, docker_services
    ):
        err_func = psycopg2.errors.SerializationFailure
        err_func.pgcode = "40001"
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.side_effect = [[0]]
        err = [None, err_func, 0, 0, []]
        mock_cursor.execute.side_effect = err

        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mocker.patch("psycopg2.connect", return_value=mock_connection)

        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        date_dict = {
            "startedat_since": None,
            "startedat_until": None,
            "endedat_since": None,
            "endedat_until": None,
        }
        applystatus = get_db_instance.get_apply_status_list(
            GetAllOption(
                limit=20,
                fields=None,
                offset=0,
                orderBy="desc",
                sortBy="startedAt",
                status=None,
                date_dict=date_dict,
            )
        )

        assert_target = {
            "totalCount": 0,
            "count": 0,
            "applyResults": [],
        }

        assert applystatus == assert_target

    def test_delete_check_if_a_SerializationFailure_occurs(self, mocker, get_db_instance, docker_services):
        err_func = psycopg2.errors.SerializationFailure
        err_func.pgcode = "40001"
        mock_cursor = mocker.MagicMock()
        mock_cursor.rowcount = 1
        err = [None, err_func, None]
        mock_cursor.execute.side_effect = err

        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_conn = mocker.patch("psycopg2.connect", return_value=mock_connection)

        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        get_db_instance.delete("900000006f")
        assert mock_conn.call_count == 1

    def test_proc_cancel_check_if_a_SerializationFailure_occurs(self, mocker, get_db_instance, docker_services):
        result = {
            "applyid": "000000001a",
            "status": "IN_PROGRESS",
            "procedures": {"procedures": "test"},
            "applyresult": None,
            "rollbackprocedures": None,
            "startedat": datetime.datetime(2023, 10, 2, 0, 0),
            "endedat": datetime.datetime(2023, 10, 2, 0, 0),
            "canceledat": datetime.datetime(2023, 10, 2, 0, 0),
            "executerollback": None,
            "rollbackstatus": None,
            "rollbackresult": None,
            "rollbackstartedat": datetime.datetime(2023, 10, 2, 0, 0),
            "rollbackendedat": datetime.datetime(2023, 10, 2, 0, 0),
            "resumeprocedures": None,
            "resumeresult": None,
            "suspendedat": datetime.datetime(2023, 10, 2, 0, 0),
            "resumedat": datetime.datetime(2023, 10, 2, 0, 0),
        }
        err_func = psycopg2.errors.SerializationFailure
        err_func.pgcode = "40001"
        mock_cursor = mocker.MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.fetchone.side_effect = [result]
        err = [None, err_func, None, None]
        mock_cursor.execute.side_effect = err

        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_conn = mocker.patch("psycopg2.connect", return_value=mock_connection)

        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        result_status = get_db_instance.proc_cancel("000000001a", False)
        assert result_status["status"] in Result.FAILED
        assert result_status["pre_status"] in "IN_PROGRESS"
        assert mock_conn.call_count == 1

    def test_proc_resume_check_if_a_SerializationFailure_occurs(self, mocker, get_db_instance, docker_services):
        err_func = psycopg2.errors.SerializationFailure
        err_func.pgcode = "40001"
        mock_cursor = mocker.MagicMock()
        mock_cursor.rowcount = 1
        err = [None, err_func, None, None]
        mock_cursor.execute.side_effect = err

        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_conn = mocker.patch("psycopg2.connect", return_value=mock_connection)

        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        get_db_instance.proc_resume("900000006f")
        assert mock_conn.call_count == 1

    @pytest.mark.parametrize(
        "args",
        [
            (
                {
                    "result": [{"test": "test"}],
                    "resume_flg": False,
                    "rollback_flg": False,
                    "request_flg": True,
                }
            ),
            (
                {
                    "result": [{"test": "test"}],
                    "resume_flg": False,
                    "rollback_flg": True,
                    "request_flg": False,
                }
            ),
            (
                {
                    "result": [{"test": "test"}],
                    "resume_flg": True,
                    "rollback_flg": False,
                    "request_flg": True,
                }
            ),
            (
                {
                    "result": [{"test": "test"}],
                    "resume_flg": True,
                    "rollback_flg": True,
                    "request_flg": False,
                }
            ),
            (
                {
                    "result": [{"test": "test"}],
                    "resume_flg": False,
                    "rollback_flg": False,
                    "request_flg": False,
                }
            ),
            (
                {
                    "result": [{"test": "test"}],
                    "resume_flg": True,
                    "rollback_flg": False,
                    "request_flg": False,
                }
            ),
        ],
    )
    def test_update_result_success(self, mocker, get_db_instance, init_db_instance, docker_services, args):
        # Data adjustment before testing.
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        applyid = create_randomname(IdParameter.LENGTH)
        cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
        init_db_instance.commit()
        mock_con = mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)
        args["applyID"] = applyid

        get_db_instance.update_result(**args)
        cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
        init_db_instance.commit()
        row = cursor.fetchone()
        assert mock_con.call_count == 1
        if args["resume_flg"] and args["request_flg"]:
            assert row.get("resumeresult") == args["result"]
        elif args["rollback_flg"]:
            assert row.get("rollbackresult") == args["result"]
        elif args["request_flg"]:
            assert row.get("applyresult") == args["result"]
        else:
            assert row.get("resumeresult") is None
            assert row.get("rollbackresult") is None
            assert row.get("applyresult") is None

    @pytest.mark.parametrize(
        "args",
        [
            (
                {
                    "applyID": "0123456789abcdef",
                    "result": [{"test": "test"}],
                    "resume_flg": False,
                    "rollback_flg": False,
                    "request_flg": True,
                }
            ),
            (
                {
                    "applyID": "0123456789abcdef",
                    "result": [{"test": "test"}],
                    "resume_flg": False,
                    "rollback_flg": True,
                    "request_flg": False,
                }
            ),
            (
                {
                    "applyID": "0123456789abcdef",
                    "result": [{"test": "test"}],
                    "resume_flg": True,
                    "rollback_flg": False,
                    "request_flg": True,
                }
            ),
            (
                {
                    "applyID": "0123456789abcdef",
                    "result": [{"test": "test"}],
                    "resume_flg": True,
                    "rollback_flg": True,
                    "request_flg": False,
                }
            ),
        ],
    )
    def test_update_result_failure_when_nonexistent_id(
        self, mocker, get_db_instance, init_db_instance, docker_services, args
    ):
        mocker.patch("psycopg2.connect", return_value=init_db_instance)
        mocker.patch.object(DbAccess, "close", return_value=None)

        with pytest.raises(IdNotFoundException):
            get_db_instance.update_result(**args)

    @pytest.mark.parametrize(
        "args",
        [
            (
                {
                    "applyID": "0123456789abcdef",
                    "result": [{"test": "test"}],
                    "resume_flg": False,
                    "rollback_flg": False,
                    "request_flg": True,
                }
            ),
            (
                {
                    "applyID": "0123456789abcdef",
                    "result": [{"test": "test"}],
                    "resume_flg": False,
                    "rollback_flg": True,
                    "request_flg": False,
                }
            ),
            (
                {
                    "applyID": "0123456789abcdef",
                    "result": [{"test": "test"}],
                    "resume_flg": True,
                    "rollback_flg": False,
                    "request_flg": True,
                }
            ),
            (
                {
                    "applyID": "0123456789abcdef",
                    "result": [{"test": "test"}],
                    "resume_flg": True,
                    "rollback_flg": True,
                    "request_flg": False,
                }
            ),
        ],
    )
    def test_update_result_check_if_a_SerializationFailure_occurs(
        self, mocker, get_db_instance, init_db_instance, docker_services, args
    ):
        err_func = psycopg2.errors.SerializationFailure
        err_func.pgcode = "40001"
        mock_cursor = mocker.MagicMock()
        mock_cursor.rowcount = 1
        err = [None, err_func, None, None]
        mock_cursor.execute.side_effect = err

        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_conn = mocker.patch("psycopg2.connect", return_value=mock_connection)

        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        get_db_instance.update_result(**args)
        assert mock_conn.call_count == 1
