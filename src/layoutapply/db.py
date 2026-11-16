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
"""Packages related to database operations"""

import copy
import json
import time
from dataclasses import dataclass

import psutil
import psycopg2
from psycopg2.errors import SerializationFailure  # pylint:disable=E0611
from psycopg2.extras import DictCursor

from layoutapply.common.dateutil import DATETIME_STR_FORMAT, get_str_now
from layoutapply.common.logger import Logger
from layoutapply.const import Action, IdParameter, Result
from layoutapply.custom_exceptions import (
    IdNotFoundException,
    MultipleInstanceError,
    OperationalError,
    ProgrammingError,
    SuspendedDataExistException,
)
from layoutapply.setting import LayoutApplyConfig
from layoutapply.util import create_applystatus_response, create_randomname

TABLE_NAME = "applystatus"
ROLLBACK_TABLE_NAME = "rollbackstatus"
# DB connection retry limit
LIMIT_RETRY_CONNECT = 5
# DB connection retry interval
INTERVAL_RETRY_CONNECT = 5


@dataclass
class UpdateOption:
    """UpdateOption options class"""

    # pylint: disable=C0103
    applyID: str
    status: str
    procedures: dict
    applyresult: list
    rollbackprocedures: list
    rollback_status: str
    rollback_result: list
    resumeprocedures: list


@dataclass
class GetAllOption:
    """Get all options class"""

    # pylint: disable=C0103
    status: str
    date_dict: dict
    fields: list
    sortBy: str
    orderBy: str
    limit: int
    offset: int


class DbAccess:
    """Connection LayoutApply status management database"""

    def __init__(self, logger: Logger):
        """Constructor"""
        self.conn = None
        self.cur = None
        self.logger = logger

    def register(self, procedures: dict, is_empty=False) -> str:
        """Register
            Register the status to LayoutApply status management database
        Args:
            procedures (dict): Procedures
            is_empty (bool, optional): Flag to check if the migration procedure list is empty. default False

        Returns:
            str : Registered LayoutApply ID
        """

        self._open_db_connection()

        while True:
            date = get_str_now()
            insert_query = ""
            applyID = create_randomname(IdParameter.LENGTH)  # pylint: disable=C0103
            params = [applyID]
            if not is_empty:
                insert_query = (
                    f"INSERT INTO {TABLE_NAME} (applyID, status, procedures, startedAt) " "VALUES(%s,%s,%s,%s)"
                )
                params.extend([Result.IN_PROGRESS, json.dumps(procedures.get("procedures", [])), date])
            else:
                insert_query = (
                    f"INSERT INTO {TABLE_NAME} (applyID, status, procedures, result, startedAt, endedAt) "
                    "VALUES(%s,%s,%s,%s,%s,%s)"
                )
                params.extend([Result.COMPLETED, "[]", "[]", date, date])
            try:
                applystatus = self._get_running_data()
                self._is_running_data(applystatus)
                self._execute_query(query=insert_query, params=params)
                self.conn.commit()
                self.logger.info(f"Added a new apply (ID) : {applyID}")
                break
            except psycopg2.IntegrityError:
                self.logger.debug(f"Reissued  apply (ID) : {applyID}")
                continue
            except SerializationFailure:
                self.conn.rollback()
                continue

        self.close()
        return applyID

    def update(self, options: UpdateOption):  # pylint: disable=C0103
        """Update
            Update the status to LayoutApply status management database

        Args:
            oprions (UpdateOption): Update option

        Raises:
            IdNotFoundException: Occurs when a non-existent ID is specified
        """
        self._open_db_connection()
        params = []
        r_params = []

        update_query, r_update_query, params, r_params = self._create_query_of_update(params, r_params, options)

        try:
            if len(params) > 1:
                self.execute_query_auto_retry_on_serializationfailure(update_query, params)
                if self.cur.rowcount == 0:
                    self.logger.error(
                        f"[E40020]{IdNotFoundException(options.applyID).message}",
                        stack_info=False,
                    )
                    raise IdNotFoundException(options.applyID)
            if len(r_params) > 1:
                self.execute_query_auto_retry_on_serializationfailure(r_update_query, r_params)

        finally:
            self.close()

    def register_rollback_status(
        self, applyID: str, rollback_status: str, rollback_procedures_list: list
    ):  # pylint: disable=C0103
        """register rollback status

        Args:
            applyID (str): layoutapply ID
            rollback_status (str): registered rollback status
            rollback_procedures_list (list): rollback procedures

        Raises:
            IdNotFoundException: Specified applyID is not found
        """
        self._open_db_connection()

        update_query = (
            f"INSERT INTO {ROLLBACK_TABLE_NAME} (status, procedures, startedAt, applyid) VALUES(%s,%s,%s,%s) "
        )

        try:
            self.execute_query_auto_retry_on_serializationfailure(
                update_query, params=[rollback_status, json.dumps(rollback_procedures_list), get_str_now(), applyID]
            )

        finally:
            self.close()

    def update_subprocess(self, pid: str, applyID: str, action: str):  # pylint: disable=C0103
        """update subprocess information

        Args:
            pid (str): subprocess ID
            applyID (str): apply ID
        Raises:
            IdNotFoundException: Specified applyID is not found
        """
        self._open_db_connection()
        proc = psutil.Process(pid)
        if action == Action.ROLLBACK_RESUME:
            update_query = f"UPDATE {ROLLBACK_TABLE_NAME} SET "
        else:
            update_query = f"UPDATE {TABLE_NAME} SET "
        update_query += "processID = %s, executionCommand = %s, processStartedAt = %s WHERE applyID = %s"

        try:
            self.execute_query_auto_retry_on_serializationfailure(
                update_query,
                params=[pid, "".join(proc.cmdline()), str(proc.create_time()), applyID],
            )

        finally:
            self.close()

    def update_result(self, applyID: str, result: list, rollback_flg: bool, request_flg: bool):  # pylint: disable=C0103
        """update result

        Args:
            applyID (str): apply ID
            result (list): apply/rollback/resume result
            rollback_flg (bool): rollback_flg
            request_flg (bool): request_flg

        Raises:
            IdNotFoundException: Specified applyID is not found
        """
        self._open_db_connection()

        update_query = None

        if request_flg:
            update_query = f"UPDATE {TABLE_NAME} SET result = %s WHERE applyID = %s"
        elif rollback_flg:
            update_query = f"UPDATE {ROLLBACK_TABLE_NAME} SET result = %s WHERE applyID = %s"

        try:
            if update_query:
                self.execute_query_auto_retry_on_serializationfailure(
                    update_query, params=[json.dumps(result), applyID]
                )
                if self.cur.rowcount == 0:
                    self.logger.error(f"[E40020]{IdNotFoundException(applyID).message}", stack_info=False)
                    raise IdNotFoundException(applyID)

        finally:
            self.close()

    def get_apply_status(self, applyID: str, no_connection=True) -> dict:  # pylint: disable=C0103
        """Get apply status

        Args:
            applyID (str): LayoutApply ID
            no_connection (bool, optional): Flag to open DB connection. Defaults to True.

        Raises:
            IdNotFoundException: The target ID does not exist.

        Returns:
            applystatus (dict): result applystatus
        """
        if no_connection:
            self._open_db_connection()
        select_query = (
            "SELECT "
            "applyID, status, procedures, result, rollbackProcedures, startedAt, endedAt"
            ", canceledAt, executeRollback, resumeProcedures, suspendedAt, resumedAt "
            f"FROM {TABLE_NAME} "
            "WHERE applyID = %s"
        )
        r_select_query = (
            "SELECT "
            "applyID, status, procedures, result, startedAt, endedAt"
            ", canceledAt, resumeProcedures, suspendedAt, resumedAt "
            f"FROM {ROLLBACK_TABLE_NAME} "
            "WHERE applyID = %s"
        )
        if no_connection:
            self.execute_query_auto_retry_on_serializationfailure(select_query, params=[applyID])
        else:
            self._execute_query(select_query, params=[applyID])
        row = self.cur.fetchone()
        if row is None:
            self.logger.error(f"[E40020]{IdNotFoundException(applyID).message}", stack_info=False)
            raise IdNotFoundException(applyID)

        if no_connection:
            self.execute_query_auto_retry_on_serializationfailure(r_select_query, params=[applyID])
        else:
            self._execute_query(r_select_query, params=[applyID])
        r_row = self.cur.fetchone()
        if no_connection:
            self.close()

        # results obtained in the array are stored in applystatus
        applystatus = self._dict_order_norm(row)
        if r_row is not None:
            applystatus["rollback"] = self._dict_order_norm(r_row)
            applystatus["rollback"].pop("applyID", None)
        self.logger.debug(f"Get Data : {applystatus}")

        return applystatus

    def get_apply_status_list(self, options: GetAllOption) -> dict:
        """get_apply_status_list

        Args:
            options (GetAllOption): get all options

        Returns:
            dict: number of data and list of applystatus
        """

        self._open_db_connection()

        params = []
        where_query = self._create_where_query_of_get(
            options,
            params,
        )
        return_dict = {"totalCount": self.get_total_count(where_query, params)}

        select_query, r_select_query = self._create_select_queries_of_get_apply_status_list(options)
        select_query = self._append_get_apply_status_list_query_option(select_query, where_query, options)
        r_select_query = self._append_get_apply_status_list_query_option(r_select_query, where_query, options)

        self.execute_query_auto_retry_on_serializationfailure(select_query, params)
        results = self.cur.fetchall()
        self.execute_query_auto_retry_on_serializationfailure(r_select_query, params)
        r_results = self.cur.fetchall()
        self.close()

        applystatus_list = self._create_applystatus_list(results, r_results)
        self.logger.info(f"Get Data : {applystatus_list}")
        return_dict.update({"count": len(applystatus_list), "applyResults": applystatus_list})

        return return_dict

    def _create_select_queries_of_get_apply_status_list(self, options: GetAllOption) -> tuple[str, str]:
        """Create select queries used by get_apply_status_list."""
        if not options.fields:
            return self._create_default_select_queries_of_get_apply_status_list()

        select_query = (
            "SELECT "
            f"{', '.join(options.fields)}"
            ", applyID, status, startedAt, endedAt, canceledAt, executeRollback"
            ", suspendedAt, resumedAt "
            f"FROM {TABLE_NAME}"
        )
        fields_without_rp = [field for field in options.fields if field != "rollbackProcedures"]
        if fields_without_rp:
            r_select_query = (
                "SELECT "
                f"{', '.join(fields_without_rp)}"
                ", applyID, status, startedAt, endedAt, canceledAt, suspendedAt, resumedAt "
                f"FROM {ROLLBACK_TABLE_NAME}"
            )
        else:
            _, r_select_query = self._create_default_select_queries_of_get_apply_status_list()

        return select_query, r_select_query

    def _create_default_select_queries_of_get_apply_status_list(self) -> tuple[str, str]:
        """Create default select queries used by get_apply_status_list."""
        select_query = (
            "SELECT "
            "applyID, status, startedAt, endedAt, canceledAt, executeRollback"
            ", suspendedAt, resumedAt "
            f"FROM {TABLE_NAME}"
        )
        r_select_query = (
            "SELECT "
            "applyID, status, startedAt, endedAt, canceledAt, suspendedAt, resumedAt "
            f"FROM {ROLLBACK_TABLE_NAME}"
        )
        return select_query, r_select_query

    def _append_get_apply_status_list_query_option(self, query: str, where_query: str, options: GetAllOption) -> str:
        """Append where/order/limit options to query for get_apply_status_list."""
        query += where_query
        query += f" ORDER BY {options.sortBy} {options.orderBy}"
        # If the limit is unspecified, it is necessary to add ALL to retrieve everything in Postgres.
        query += f" LIMIT {options.limit or 'ALL'} OFFSET {options.offset}"
        return query

    def _create_applystatus_list(self, results: list, r_results: list) -> list:
        """Merge apply and rollback rows and return API response list."""
        rollback_map = {
            r_applystatus.get("applyID"): r_applystatus
            for r_applystatus in (self._dict_order_norm(r_row) for r_row in r_results)
        }

        applystatus_list = []
        for row in results:
            applystatus = self._dict_order_norm(row)
            rollback_data = rollback_map.get(applystatus.get("applyID"))
            if rollback_data is not None:
                applystatus["rollback"] = rollback_data
                applystatus["rollback"].pop("applyID", None)
            applystatus_list.append(create_applystatus_response(applystatus))
        return applystatus_list

    def get_total_count(self, where_query: str, params: list) -> int:
        """Get total count of apply

        Args:
            where_query (str): 'where' sql condition
            params (list): sql params

        Returns:
            int: Count of applys
        """
        select_query = f"SELECT COUNT(*) AS totalCount FROM {TABLE_NAME}"
        self.execute_query_auto_retry_on_serializationfailure(select_query + where_query, params)
        return self.cur.fetchone()[0]

    def proc_cancel(self, applyID: str, rollbackflag: bool):  # pylint: disable=C0103
        """proc_cancel
            cancel process

        Args:
            applyID (str): layoutapply id
            rollbackflag (bool): rollbackflag

        Raises:
            IdNotFoundException:

        Returns:
            result_status(dict): change status, rollbackStatus result for cancel
              before key: before change status, rollbackStatus
              after key:  after change status, rollbackStatus
        """
        self._open_db_connection()
        while True:
            try:
                applystatus = self._get_applystatus_data(applyID)
                result_status = self._exec_cancel(applyID, rollbackflag, applystatus)
                self.conn.commit()
                self.close()
                break
            except SerializationFailure:
                self.conn.rollback()
                continue

        return result_status

    def _get_applystatus_data(self, applyID: str) -> dict:  # pylint: disable=C0103
        """Get applystatus data from database

        Args:
            applyID (str): layoutapply id

        Returns:
            dict: applystatus data

        Raises:
            IdNotFoundException: when applyID is not found
        """
        select_query = (
            "SELECT status, processID, executionCommand" f", processStartedAt FROM {TABLE_NAME} WHERE applyID = %s"
        )
        r_select_query = (
            "SELECT status, processID, executionCommand"
            f", processStartedAt FROM {ROLLBACK_TABLE_NAME} WHERE applyID = %s"
        )

        self._execute_query(select_query, params=[applyID])
        row = self.cur.fetchone()
        row_count = self.cur.rowcount

        self._execute_query(r_select_query, params=[applyID])
        r_row = self.cur.fetchone()
        r_row_count = self.cur.rowcount

        if row_count == 0 and r_row_count == 0:
            self.close()
            self.logger.error(f"[E40020]{IdNotFoundException(applyID).message}", stack_info=False)
            raise IdNotFoundException(applyID)

        applystatus = {k: v for k, v in dict(row).items() if v is not None}
        if r_row_count != 0 and r_row is not None:
            applystatus["rollback"] = {k: v for k, v in dict(r_row).items() if v is not None}

        return applystatus

    def _exec_cancel(self, id_: str, rollbackflag: bool, applystatus: dict) -> dict:  # pylint: disable=C0103
        """Exec cancel

        Args:
            id_ (str): layoutapply id
            rollbackflag (bool): rollbackflag
            applystatus (dict): current applystatus

        Returns:
            result_status (dict): cancel result
        """
        status = applystatus.get("status")
        r_status = applystatus.get("rollback", {}).get("status", None)
        # Store the return values with the pre-transition state (pre_xxx),
        # reflected state after the transition (status), and the rollback state (r_status)
        result_status = {
            "pre_status": status,
            "status": status,
            "pre_r_status": r_status,
            "r_status": r_status,
        }

        if status == Result.IN_PROGRESS:
            if self._is_subprocess_exist(applystatus) is True:
                result_status["status"] = Result.CANCELING
                self._requst_cancel(id_, rollbackflag, status)
            else:
                result_status["status"] = Result.FAILED
                self._requst_cancel(id_, False, Result.FAILED)
        elif status == Result.CANCELED and r_status == Result.IN_PROGRESS:
            if self._is_subprocess_exist(applystatus.get("rollback", {})) is False:
                result_status["r_status"] = Result.FAILED
                self._requst_cancel(id_, False, status, r_status)
        elif status == Result.SUSPENDED:
            result_status["status"] = Result.FAILED
            self._requst_cancel(id_, False, status)
        elif r_status == Result.SUSPENDED:
            result_status["r_status"] = Result.FAILED
            self._requst_cancel(id_, False, status, r_status)

        return result_status

    def _is_subprocess_exist(self, applystatus: dict):  # pylint: disable=C0103
        """Check the existence of the subprocess by
           comparing the registered subprocess execution command and start time in the DB

        Args:
            applystatus (dict): current applystatus

        Returns:
            return_value(bool): subprocess exist judgement
        """
        cmd = applystatus.get("executioncommand")
        stime = applystatus.get("processstartedat")
        try:
            proc = psutil.Process(applystatus.get("processid"))
            proc_cmd = "".join(proc.cmdline())
            proc_stime = str(proc.create_time())
        except Exception:  # pylint: disable=W0703
            # If the process does not exist or process information cannot be retrieved (zombified)
            return False

        return cmd == proc_cmd and stime == proc_stime

    def _requst_cancel(
        self, applyID: str, rollbackflag: bool, status: str, r_status: str = ""
    ):  # pylint: disable=C0103
        """Cancel request
            If running: Update to cancelling
            If suspended: Update to failed

        Args:
            applyID (str): Update ID
            rollbackflag (bool): Rollback flag
            status (str): Status before execution
            r_status (str): RollbackStatus before execution

        Raises:
            IdNotFoundException: Occurs when a non-existent ID is specified
        """

        update_query, params = self._create_query_of_request_cancel(status, r_status)
        if status in (Result.IN_PROGRESS, Result.SUSPENDED) or r_status == Result.SUSPENDED:
            params.append(get_str_now())
        if status == Result.IN_PROGRESS:
            params.append(rollbackflag)
        params.append(applyID)

        self._execute_query(update_query, params)
        if self.cur.rowcount == 0:
            self.logger.error(f"[E40020]{IdNotFoundException(applyID).message}", stack_info=False)
            self.close()
            raise IdNotFoundException(applyID)

    def proc_resume(self, applyID: str):  # pylint: disable=C0103
        """proc_resume
            resume process

        Args:
            applyID (str): layoutapply id

        Raises:
            IdNotFoundException:

        Returns:
            applystatus(str): get result apply status
        """
        self._open_db_connection()
        while True:
            try:
                applystatus = self.get_apply_status(applyID, no_connection=False)
                if (
                    applystatus.get("status") == Result.SUSPENDED
                    or applystatus.get("rollback", {}).get("status", None) == Result.SUSPENDED
                ):
                    self._request_resume(applyID, applystatus)  # pylint: disable=C0103
                    self.conn.commit()
                break
            except SerializationFailure:
                self.conn.rollback()
                continue
        self.close()
        return applystatus

    def _request_resume(self, applyID: str, applystatus: dict):  # pylint: disable=C0103
        """update status to IN_PROGRESS

        Args:
            applyID (str): layoutapply ID
            applystatus (dict): get applystatus result

        Raises:
            IdNotFoundException
        """
        update_query: str
        if applystatus.get("status") == Result.SUSPENDED:
            update_query = f"UPDATE {TABLE_NAME} SET status = %s, resumedAt = %s WHERE applyID = %s"
        if applystatus.get("rollback", {}).get("status") == Result.SUSPENDED:
            update_query = f"UPDATE {ROLLBACK_TABLE_NAME} SET status = %s, resumedAt = %s WHERE applyID = %s"
        self._execute_query(update_query, params=[Result.IN_PROGRESS, get_str_now(), applyID])
        if self.cur.rowcount == 0:
            self.close()
            self.logger.error(f"[E40020]{IdNotFoundException(applyID).message}", stack_info=False)
            raise IdNotFoundException(applyID)

    def _get_running_data(self) -> dict:  # pylint: disable=C0103
        """get running layoutapply data

        Returns:
             dict: running layoutapply data
        """
        select_query = f"SELECT applyID, status FROM {TABLE_NAME} " "WHERE status IN (%s, %s, %s)"
        r_select_query = f"SELECT applyID, status FROM {ROLLBACK_TABLE_NAME} " "WHERE status IN (%s, %s)"
        self._execute_query(
            select_query,
            [Result.IN_PROGRESS, Result.CANCELING, Result.SUSPENDED],
        )
        row = self.cur.fetchone()
        self._execute_query(
            r_select_query,
            [Result.IN_PROGRESS, Result.SUSPENDED],
        )
        r_row = self.cur.fetchone()
        # results obtained in the array are stored in applystatus
        applystatus = self._dict_order_norm(row) if row is not None else {}
        if r_row is not None:
            applystatus["rollback"] = self._dict_order_norm(r_row)
        self.logger.info(f"Get running data : {applystatus}")
        return applystatus

    def _is_running_data(self, applystatus):
        """check running layoutapply data

        Args:
            applystatus (dict): running layoutapply data

        Raises:
            MultipleInstanceError: Already running. Cannot start multiple instances
            SuspendedDataExistException: Suspended data exist
        """
        if (
            applystatus.get("status") in [Result.IN_PROGRESS, Result.CANCELING]
            or applystatus.get("rollback", {}).get("status") == Result.IN_PROGRESS
        ):
            self.conn.rollback()
            raise MultipleInstanceError()
        if (
            applystatus.get("status") == Result.SUSPENDED
            or applystatus.get("rollback", {}).get("status") == Result.SUSPENDED
        ):
            self.conn.rollback()
            if applystatus.get("status") == Result.SUSPENDED:
                applyid = applystatus.get("applyID")
            else:
                applyid = applystatus.get("rollback").get("applyID")
            raise SuspendedDataExistException(applyid)

    def delete(
        self,
        applyID: str,
    ):  # pylint: disable=C0103
        """delete layoutapply data

        Args:
            applyID (str): specified applyID for delete

        Raises:
            IdNotFoundException: Raise specified not exist ID
        """
        self._open_db_connection()

        delete_query = f"DELETE FROM {TABLE_NAME}"
        delete_query += " WHERE applyID = %s"
        r_delete_query = f"DELETE FROM {ROLLBACK_TABLE_NAME}"
        r_delete_query += " WHERE applyID = %s"

        try:
            # applyID is linked as a foreign key, so delete it from rollback table first.
            self.execute_query_auto_retry_on_serializationfailure(r_delete_query, params=[applyID])
            self.execute_query_auto_retry_on_serializationfailure(delete_query, params=[applyID])

            if self.cur.rowcount == 0:
                self.logger.error(f"[E40020]{IdNotFoundException(applyID).message}", stack_info=False)
                raise IdNotFoundException(applyID)

        finally:
            self.close()

    def _execute_query(self, query, params=None, need_rollback=False):
        """Executed query

        Args:
            query (str): string query
            params (Any, optional): parameter. Defaults to None.
            need_rollback (bool, optional): Whether to roll back in case of an error. Defaults to False.

        Raises:
            error: psycopg2.ProgrammingError

        Returns:
            Any: Execution result
        """
        self.logger.debug(f"query : {query}, vars: {params}")
        try:
            result = self.cur.execute(query=query, vars=params)
        except psycopg2.ProgrammingError as err:
            msg = f"[E40019]{ProgrammingError(err).message}"
            self.logger.error(msg, stack_info=True)
            if need_rollback:
                self.conn.rollback()
            self.close()
            raise err
        return result

    def execute_query_auto_retry_on_serializationfailure(self, query, params=None):
        """Execute query.

        Args:
            query (str): Query string.
            params (Any, optional): Parameters. Defaults to None.
        """
        while True:
            try:
                self._execute_query(query, params)
                self.conn.commit()
                break
            except SerializationFailure:
                self.conn.rollback()
                continue

    def _open_db_connection(self, retry_counter: int = 0):
        """Connect ApplyStatusDB

        Args:
            retry_counter (int): Connect DB retry count

        """

        config = LayoutApplyConfig()
        try:
            self.conn = psycopg2.connect(**config.db_config)
            self.cur = self.conn.cursor(cursor_factory=DictCursor)
            self._execute_query("set transaction isolation level SERIALIZABLE")
        except psycopg2.OperationalError as err:
            if retry_counter >= LIMIT_RETRY_CONNECT:
                self.logger.error(f"[E40018]{OperationalError(err).message}", stack_info=True)
                raise err
            retry_counter += 1
            msg = f"Could not connect to ApplyStatusDB. Reconnecting count: {retry_counter}"
            self.logger.info(msg)
            time.sleep(INTERVAL_RETRY_CONNECT)
            self._open_db_connection(retry_counter)

    def close(self):
        """Disconnect DB"""
        self.cur.close()
        self.conn.close()
        self.logger.debug("DB connection closed")

    def _create_update_query(  # pylint: disable=C0103
        self,
        options: UpdateOption,
        params: list,
        r_params: list,
        date: str,
    ) -> tuple[str, str]:
        """Create an update query

        Args:
            procedures (dict): Procedures
            applyresult (list): Applyresult
            rollbackprocedures (list): RollbackProcedures
            params (list): List of parameters for query

        Returns:
            str: Created query
        """
        status = options.status
        rollback_status = options.rollback_status
        update_query = ""
        r_update_query = ""
        if options.applyresult:
            update_query += ", result = %s"
            params.append(json.dumps(options.applyresult))
        if rollback_status == "" and options.rollbackprocedures:
            update_query += ", rollbackprocedures = %s"
            params.append(json.dumps(options.rollbackprocedures))
        if status == Result.SUSPENDED and options.resumeprocedures:
            update_query += ", resumeprocedures = %s"
            params.append(json.dumps(options.resumeprocedures))
        if rollback_status == Result.SUSPENDED:
            r_update_query += ", suspendedAt = %s, resumeprocedures = %s"
            r_params.extend([date, json.dumps(options.resumeprocedures)])
        elif rollback_status in (Result.COMPLETED, Result.FAILED):
            r_update_query += ", endedAt = %s"
            r_params.append(date)
        if options.rollback_result:
            r_update_query += ", result = %s"
            r_params.append(json.dumps(options.rollback_result))
        return update_query, r_update_query

    def _dict_order_norm(self, row) -> dict:
        """Normalize the order and key names of the retrieved apply status

        Args:
            row (dict): dict_row retrieved from the database
            fields (list): List of items included in return value

        Returns:
            dict: Normalized apply status
        """
        applystatus = dict(row)
        applystatus = {k: v for k, v in applystatus.items() if v is not None}
        # Modify the key names for response, reassign values
        applystatus = self._rename_keys_and_replace_values(applystatus)
        return applystatus

    def _rename_keys_and_replace_values(self, applystatus: dict) -> dict:
        """Rename keys of applystatus dict and replace values

        Args:
            applystatus (dict): applystatus of response body

        Returns:
            dict: dict of apply status
        """
        key_value_pairs_to_rename = [
            ("applyid", "applyID"),
            ("rollbackprocedures", "rollbackProcedures"),
            ("executerollback", "executeRollback"),
            ("resumeprocedures", "resumeProcedures"),
            ("processid", "processID"),
            ("executioncommand", "executionCommand"),
        ]
        date_keys_to_rename = [
            ("startedat", "startedAt"),
            ("endedat", "endedAt"),
            ("canceledat", "canceledAt"),
            ("processstartedat", "processStartedAt"),
            ("suspendedat", "suspendedAt"),
            ("resumedat", "resumedAt"),
        ]

        updated_status = copy.deepcopy(applystatus)
        for key, value in key_value_pairs_to_rename:
            current_value = applystatus.get(key)
            # Replace only the fields with values in the database to filter the output items.
            should_rename = (
                current_value is not None
                or (key == "executerollback" and current_value is False)
                or (key == "result" and current_value == [])
            )
            if should_rename:
                updated_status[value] = current_value
                updated_status.pop(key, None)

        for key, value in date_keys_to_rename:
            current_value = applystatus.get(key)
            if current_value:
                updated_status[value] = current_value.strftime(DATETIME_STR_FORMAT)
                updated_status.pop(key, None)

        return updated_status

    def _create_where_query_of_get(self, options: GetAllOption, params: list) -> str:
        """Create where query of get method

        Args:
            options(GetAllOption): get all option
            params (list): List of parameters for query

        Returns:
            str: Created query
        """
        where_query = ""
        if options.status is not None:
            where_query += " where status = %s"
            params.append(options.status)
        for key, value in options.date_dict.items():
            if where_query == "":
                where_query += " where "
            else:
                where_query += " and "
            if key.endswith("_since"):
                where_query += key[:-6] + " >= %s"
            else:
                where_query += key[:-6] + " <= %s"
            params.append(value)

        return where_query

    def _should_set_ended_at(self, status: str, rollback_status: str) -> bool:
        return bool(status or rollback_status) and rollback_status != Result.SUSPENDED

    def _append_where_apply_id(self, query: str, query_params: list, apply_id: str) -> str:
        if query_params:
            query += " WHERE applyID = %s"
            query_params.append(apply_id)
        return query

    def _create_query_of_update(self, params: list, r_params: list, options: UpdateOption):
        """Create query of update method

        Args:
            params (list): List of parameters for query
            options (UpdateOption): Update all option

        Returns:
            any(str,list): Created query and query parameter
        """
        date = get_str_now()
        n_status = options.status
        r_status = options.rollback_status
        update_query = f"UPDATE {TABLE_NAME} SET "
        r_update_query = f"UPDATE {ROLLBACK_TABLE_NAME} SET "

        if n_status != "":
            params.append(n_status)
            update_query += "status = %s"
        if r_status != "":
            r_update_query += "status = %s"
            r_params.append(r_status)
        update_fragment, r_update_fragment = self._create_update_query(options, params, r_params, date)
        update_query += update_fragment
        r_update_query += r_update_fragment
        if n_status == Result.SUSPENDED:
            update_query += ", suspendedAt = %s"
            params.append(date)
        elif self._should_set_ended_at(n_status, r_status):
            update_query += f"{', ' if params else ''}endedAt = %s"
            params.append(date)
        update_query = self._append_where_apply_id(update_query, params, options.applyID)
        r_update_query = self._append_where_apply_id(r_update_query, r_params, options.applyID)
        return update_query, r_update_query, params, r_params

    def _create_query_of_request_cancel(self, status: str, r_status: str):
        """Create query of request cancel method

        Args:
            status (str): Status before execution
            r_status (str): Rollback Status before execution

        Returns:
            any(str,list): Created query and query parameter
        """
        query = f"UPDATE {TABLE_NAME} SET status = %s WHERE applyID = %s"
        if status == Result.IN_PROGRESS:
            # Status:IN_PROGRESS⇒CANCELING
            return (
                f"UPDATE {TABLE_NAME} SET status = %s, canceledAt = %s, executeRollback = %s WHERE applyID = %s",
                [Result.CANCELING],
            )
        if status == Result.SUSPENDED:
            # Status:SUSPENDED⇒FAILED
            return f"UPDATE {TABLE_NAME} SET status = %s, canceledAt = %s WHERE applyID = %s", [Result.FAILED]
        if r_status == Result.IN_PROGRESS:
            # RollbackStatus:IN_PROGRESS⇒FAILED
            return f"UPDATE {ROLLBACK_TABLE_NAME} SET status = %s WHERE applyID = %s", [Result.FAILED]
        if r_status == Result.SUSPENDED:
            # RollbackStatus:SUSPENDED⇒FAILED
            return f"UPDATE {ROLLBACK_TABLE_NAME} SET status = %s, canceledAt = %s WHERE applyID = %s", [Result.FAILED]
        # Status:IN_PROGRESS⇒FAILED
        return query, [Result.FAILED]
