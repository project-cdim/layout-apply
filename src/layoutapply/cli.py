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
"""Layoutapply Command"""

import json
import os
import pickle
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Tuple
from zoneinfo import ZoneInfo

import iso8601
import psycopg2
from jsonschema import ValidationError, validate

from layoutapply.common.cli import AbstractBaseCommandLine
from layoutapply.common.logger import Logger

sys.path.append(os.path.abspath("."))

# pylint: disable=wrong-import-position
from layoutapply.const import Action, ExitCode, Result  # noqa: E402
from layoutapply.custom_exceptions import (  # noqa: E402
    AlreadyExecuteException,
    BeingRunningException,
    FailedOutputError,
    FailedStartSubprocessException,
    IdNotFoundException,
    LoggerLoadException,
    MultipleInstanceError,
    NotAllowedWithError,
    OperationalError,
    OutPathPointError,
    ProgrammingError,
    SecretInfoGetException,
    SettingFileLoadException,
    SubprocessNotFoundException,
    SuspendedDataExistException,
)
from layoutapply.db import DbAccess, GetAllOption  # noqa: E402
from layoutapply.schema import apply_id as apply_id_scheme  # noqa: E402
from layoutapply.schema import fields as fields_schema  # noqa: E402
from layoutapply.schema import limit as limit_schema  # noqa: E402
from layoutapply.schema import offset as offset_schema  # noqa: E402
from layoutapply.schema import orderBy as orderBy_schema  # noqa: E402
from layoutapply.schema import procedure as procedure_scheme  # noqa: E402
from layoutapply.schema import sortBy as sortBy_schema  # noqa: E402
from layoutapply.schema import status as status_schema  # noqa: E402
from layoutapply.setting import LayoutApplyConfig  # noqa: E402
from layoutapply.util import create_applystatus_response, set_date_dict  # noqa: E402

DATABASE = None


@dataclass
class SubprocOpt:
    """Subprocess run options"""

    procedure: dict
    config: LayoutApplyConfig
    applyID: str  # pylint: disable=C0103,R0913
    action: str


class LayoutApplyCommandLine(AbstractBaseCommandLine):
    """Command line class for LayoutApply function"""

    def __init__(self) -> None:
        """Constructor"""
        super().__init__("Apply design data to node.")

    def _add_arguments(self) -> None:
        """Add command line argument"""

        self.subparsers = self.parser.add_subparsers(dest="command")
        parser_apply = self.subparsers.add_parser("request", help="Apply design data to node.")

        parser_apply.add_argument(
            "-p",
            "--procedure",
            type=str,
            metavar="PROCEDURE_FILE",
            help="procedure file path",
            required=True,
        )

        # LayoutApply cancellation request command
        cancel_command = self.subparsers.add_parser("cancel", help="Cancel apply design data to node.")
        cancel_command.add_argument(
            "--apply-id",
            type=str,
            metavar="APPLY_ID",
            required=True,
            help="cancel ID as a string",
        )
        cancel_command.add_argument(
            "-rc",
            "--rollback-on-cancel",
            action="store_true",
            help="rollback will be performed after cancellation.",
        )

        # LayoutApply state reference command, retrieve list command.
        get_command = self.subparsers.add_parser(
            "get",
            help="Gets the apply status of the specified ID or the apply status of list.",
        )
        get_command.add_argument(
            "--apply-id",
            type=str,
            metavar="APPLY_ID",
            help=(
                "get ID as a string. If not specified, get all apply status."
                + " not allowed with argument --fields, --status, --started-at-since, --started-at-until,"
                + " --ended-at-since, --ended-at-until, --sort-by, --order-by, --limit, --offset."
            ),
        )
        get_command.add_argument(
            "-f",
            "--fields",
            type=str,
            metavar="ITEM,ITEM....ITEM",
            help="""
                specify the items to be included in the return information.
                If not specified, that items are not included.
                set [procedures | applyResult | rollbackProcedures | rollbackResult | resumeProcedures | resumeResult]
            """,
        )
        get_command.add_argument(
            "-s",
            "--status",
            type=str,
            metavar="STATUS",
            help=(
                "specify the status for return information."
                + " set [IN_PROGRESS | COMPLETED | FAILED | CANCELING | CANCELED | SUSPENDED]"
            ),
        )
        get_command.add_argument(
            "-ss",
            "--started-at-since",
            type=str,
            metavar="STARTED_AT_SINCE",
            help="specify the startpoint of started time for return information.",
        )
        get_command.add_argument(
            "-su",
            "--started-at-until",
            type=str,
            metavar="STARTED_AT_UNTIL",
            help="specify the endpoint of started time for return information.",
        )
        get_command.add_argument(
            "-es",
            "--ended-at-since",
            type=str,
            metavar="ENDED_AT_SINCE",
            help="specify the startpoint of ended time for return information.",
        )
        get_command.add_argument(
            "-eu",
            "--ended-at-until",
            type=str,
            metavar="ENDED_AT_UNTIL",
            help="specify the endpoint of ended time for return information.",
        )
        get_command.add_argument(
            "--sort-by",
            # If an apply-id is specified, a validation error needs to be performed.
            # If a default value is set, it is commented out because it cannot be
            # determined whether arguments other than apply-id were specified.
            # Later processing will input startedAt if no apply-id is specified.
            # default="startedAt"
            type=str,
            metavar="SORT_BY",
            help=(
                "specify the items to be sorted. \
                If not specified, that data will be sorted by startedAt. \
                set [startedAt | endedAt]"
            ),
        )
        get_command.add_argument(
            "--order-by",
            type=str,
            metavar="ORDER_BY",
            help=("specify the order of the return information. set [asc | desc]"),
        )
        get_command.add_argument(
            "--limit",
            # If an apply-id is specified, a validation error needs to occur.
            # If a default value is set, it is commented out because it cannot be
            # determined if arguments other than apply-id were specified.
            # Later processing will input 100 if no apply-id is specified.
            # default=100
            type=int,
            metavar="NUMBER",
            help=(
                "specify the number of apply status to be retrieve for return information. \
                specify an integer value greater than or equal to 1"
            ),
        )
        get_command.add_argument(
            "--offset",
            # If apply-id is specified, a validation error needs to be executed.
            # If a default value is set, it is commented out because it cannot be
            # determined whether an argument was specified other than apply-id.
            # Later processing will input 0 if apply-id is not specified.
            # default=0
            type=int,
            metavar="NUMBER",
            help=(
                "specify the row of apply status to be retrieve for return information. \
                specify an integer value greater than or equal to 0"
            ),
        )
        get_command.add_argument(
            "-o",
            "--output",
            type=str,
            metavar="OUTPUT_FILE",
            help="apply result file path",
        )

        # LayoutApply state deletion command
        delete_command = self.subparsers.add_parser("delete", help="Delete the apply status of the specified ID.")
        delete_command.add_argument(
            "--apply-id",
            type=str,
            metavar="APPLY_ID",
            required=True,
            help="specified applyID for delete. applyID as a string.",
        )

        # LayoutApply request to resume command
        resume_command = self.subparsers.add_parser("resume", help="Resume the layoutapply of the specified ID.")
        resume_command.add_argument(
            "--apply-id",
            type=str,
            metavar="APPLY_ID",
            required=True,
            help="specified applyID for resume. applyID as a string.",
        )

    def run(self) -> None:
        """Main processing function for CLI.
        Branching based on the subcommand.
        """
        args = self.get_args()
        if args.command == Action.REQUEST:
            self.request()
        elif args.command == Action.CANCEL:
            self.cancel()
        elif args.command == Action.GET:
            self.get()
        elif args.command == Action.DELETE:
            self.delete()
        elif args.command == Action.RESUME:
            self.resume()
        else:
            # If no subcommand is specified, output the help.
            self.parser.print_help()

    def request(self) -> None:
        """Main processing function for layout request"""
        # Load the migration procedure list and perform validation checks.
        args = self.get_args()
        procedure = self._read_procedure(args.procedure)
        proc_len = len(procedure.get("procedures"))

        config, logger = self._initialize()
        logger.info(f"Start request cli. args:{vars(args)}. args.procedure:{json.dumps(procedure)}")
        logger.debug(f"config: {vars(config)}")

        try:
            # Control dual startup
            database = DbAccess(logger)
            applyID = database.register(procedure, is_empty=proc_len == 0)  # pylint: disable=C0103
            logger.debug(f"applyID: {applyID}")
        except MultipleInstanceError as err:
            print(
                f"[E40010]{err.message}",
                file=sys.stderr,
            )
            sys.exit(err.exit_code)
        except SuspendedDataExistException as err:
            print(f"[E40027]{err.message}", file=sys.stderr)
            sys.exit(err.exit_code)
        except psycopg2.OperationalError as err:
            exc = OperationalError(err)
            print(f"[E40018]{exc.message}", file=sys.stderr)
            sys.exit(exc.exit_code)
        except psycopg2.ProgrammingError as err:
            exc = ProgrammingError(err)
            print(f"[E40019]{exc.message}", file=sys.stderr)
            sys.exit(exc.exit_code)
        if proc_len != 0:
            # Run subprocess asynchronously
            proc_id = self._exec_subprocess(logger, procedure, config, applyID, Action.REQUEST)

            # Register subprocess information in the DB
            self._update_subporcess_info(database, proc_id, applyID)

        print("Request was successful. Start applying.", file=sys.stderr)

        result_json = {"applyID": applyID}
        print(json.dumps(result_json, indent=4))
        logger.info(f"End request cli. exit_code:{ExitCode.NORMAL}")
        sys.exit(ExitCode.NORMAL)

    def cancel(self) -> None:
        """Main processing function for layout cancel"""

        applyID = self.args.apply_id  # pylint: disable=C0103
        rollback_flg = False

        try:
            validate(applyID, schema=apply_id_scheme)
        except ValidationError as err:
            error_msg = err.message.split("\n")[-1]
            print(f"[E40001]{error_msg}", file=sys.stderr)
            sys.exit(ExitCode.VALIDATION_ERR)

        if self.args.rollback_on_cancel:
            rollback_flg = True

        _, logger = self._initialize()

        try:
            database = DbAccess(logger)
            logger.info(f"Start cancel cli. args:{vars(self.args)}")
            result_status = database.proc_cancel(applyID, rollback_flg)
        except psycopg2.OperationalError as err:
            exc = OperationalError(err)
            print(f"[E40018]{exc.message}", file=sys.stderr)
            sys.exit(exc.exit_code)
        except psycopg2.ProgrammingError as err:
            exc = ProgrammingError(err)
            print(f"[E40019]{exc.message}", file=sys.stderr)
            sys.exit(exc.exit_code)
        except IdNotFoundException as err:
            print(f"[E40020]{err.message}", file=sys.stderr)
            sys.exit(err.exit_code)

        exit_code = self._make_cancel_response(logger, result_status)
        logger.info(f"End cancel cli. exit_code:{exit_code}")
        sys.exit(exit_code)

    def _make_cancel_response(self, logger: Logger, result_status: dict) -> int:
        """Make layout cancel response.

        Args:
            logger (Logger): Logger
            result_status (dict): cancel request result dict
        Return:
            exit_code (int): cancel response code
        """
        pre_status, status = result_status["pre_status"], result_status["status"]
        pre_r_status, r_status = (
            result_status["pre_r_status"],
            result_status["r_status"],
        )
        if (
            status == Result.CANCELING
            or pre_status == Result.SUSPENDED
            or (pre_status == Result.CANCELED and pre_r_status is None)
        ):
            # Output the post-transition state and exit normally
            # if the post-transition state is CANCELING or the pre-transition state is SUSPENDED.
            # Alternatively, when the pre-transition apply state is CANCELED and
            # pre-transition rollback state is None, output the post-transition apply state and exit normally.
            exit_code = ExitCode.NORMAL
            msg = f"Success.\nstatus={status}"
            print(msg)
            logger.info(msg)
        else:
            exit_code = self._make_cancel_response_other_case(logger, pre_status, status, pre_r_status, r_status)

        return exit_code

    def _make_cancel_response_other_case(
        self,
        logger: Logger,
        pre_status: dict,
        status: dict,
        pre_r_status: str,
        r_status: str,
    ) -> int:
        """Make layout cancel response for other case.

        Args:
            logger (Logger): Logger
            pre_status (dict): pre status
            status (dict): status
            pre_r_status (dict): pre rollback status
            r_status (dict): rollback status
        Return:
            exit_code (int): cancel response code
        """
        if pre_r_status in (Result.COMPLETED, Result.FAILED, Result.SUSPENDED):
            # If the rollback state before the transition is either COMPLETED or FAILED,
            # terminate normally without any transition.
            # Alternatively, when the rollback state before the transition is SUSPENDED,
            # output the reflected state after the transition (no change), the rollback state, and terminate normally.
            exit_code = ExitCode.NORMAL
            msg = f"Success.\nstatus={status}\nrollbackStatus={r_status}"
            print(msg)
            logger.info(msg)
        elif pre_status == Result.IN_PROGRESS and status == Result.FAILED:
            exit_code = ExitCode.MULTIPLE_RUN_ERR
            # When the reflected state before transition is IN_PROGRESS and the state after transition is FAILED,
            # subprocess does not exist and terminates abnormally.
            error_msg = f"[E40028]{SubprocessNotFoundException("status").message}"
            print(f"{error_msg}\nstatus={status}", file=sys.stderr)
            logger.error(error_msg)
        elif pre_r_status == Result.IN_PROGRESS and r_status == Result.FAILED:
            # When the rollback state before the transition is IN_PROGRESS and the rollback state
            # after the transition is FAILED, the subprocess does not exist and terminates abnormally.
            exit_code = ExitCode.MULTIPLE_RUN_ERR
            error_msg = f"[E40028]{SubprocessNotFoundException("rollbackStatus").message}"
            print(
                f"{error_msg}\nstatus={status}\nrollbackStatus={r_status}",
                file=sys.stderr,
            )
            logger.error(error_msg)
        else:
            # If the reflect state before transition is COMPLETED or FAILED,
            # transition is not possible in the executed status, resulting in an abnormal termination.
            # Alternatively, if the reflection status is CANCELED, the rollback status is IN_PROGRESS,
            # and there is no irregularity in the process, it will result in abnormal termination
            # because it is in a non-transitional state due to a cancellation request.
            exit_code = AlreadyExecuteException().exit_code
            error_msg = f"[E40022]{AlreadyExecuteException().message}"
            print(error_msg, file=sys.stderr)
            logger.error(error_msg)

        return exit_code

    def get(self):
        """Execute main processing function for layout get or getall"""
        if self.args.apply_id is not None:
            self._get()
        else:
            self._add_default_value()
            self._getall()

    def _get(self):
        """Main processing function for layout get"""
        args = self.get_args()

        self._validate_allowed_args(args)

        self._validate_option_for_get_cli(args)

        _, logger = self._initialize()

        try:
            database = DbAccess(logger)
            logger.info(f"Start get cli. args:{vars(args)}")
            applystatus = database.get_apply_status(args.apply_id)
        except psycopg2.OperationalError as err:
            exc = OperationalError(err)
            print(f"[E40018]{exc.message}", file=sys.stderr)
            sys.exit(exc.exit_code)
        except psycopg2.ProgrammingError as err:
            exc = ProgrammingError(err)
            print(f"[E40019]{exc.message}", file=sys.stderr)
            sys.exit(exc.exit_code)
        except IdNotFoundException as err:
            print(f"[E40020]{err.message}", file=sys.stderr)
            sys.exit(err.exit_code)
        logger.info("Completed successfully")

        if args.output:
            self._wirte_result_file(args.output, create_applystatus_response(applystatus), logger)
            print("Success.")
        else:
            print(json.dumps(create_applystatus_response(applystatus), indent=4))
        logger.info(f"End get cli. exit_code:{ExitCode.NORMAL}")
        sys.exit(ExitCode.NORMAL)

    def _getall(self):
        """Main processing function for layout getall"""

        date_dict = set_date_dict(
            self.args.started_at_since,
            self.args.started_at_until,
            self.args.ended_at_since,
            self.args.ended_at_until,
        )

        fields_list = self._set_fields_list(self.args.fields)

        self._validate_option_for_get_cli(self.args, fields_list, date_dict)

        _, logger = self._initialize()

        try:
            database = DbAccess(logger)
            apply_option = GetAllOption(
                status=self.args.status,
                date_dict=date_dict,
                fields=fields_list,
                sortBy=self.args.sort_by,
                orderBy=self.args.order_by,
                limit=self.args.limit,
                offset=self.args.offset,
            )
            logger.info(f"Start getall cli. args:{vars(self.args)}")
            applyresults = database.get_apply_status_list(apply_option)

        except psycopg2.OperationalError as err:
            exc = OperationalError(err)
            print(f"[E40018]{exc.message}", file=sys.stderr)
            sys.exit(exc.exit_code)
        except psycopg2.ProgrammingError as err:
            exc = ProgrammingError(err)
            print(f"[E40019]{exc.message}", file=sys.stderr)
            sys.exit(exc.exit_code)
        logger.info("Completed successfully")

        if self.args.output:
            self._wirte_result_file(self.args.output, applyresults, logger)
            print("Success.")
        else:
            print(json.dumps(applyresults, indent=4))
        logger.info(f"End getall cli. exit_code:{ExitCode.NORMAL}")
        sys.exit(ExitCode.NORMAL)

    def _add_default_value(self):
        """Set default values for get function options"""
        # Cannot determine if any options other than the specified apply-id
        # exist when setting default values for options that need default values, such as sort_by and order_by.
        # Therefore, options requiring default values are not set.
        # If no apply-id is specified and no value is provided, process to enter the default value.
        if self.args.sort_by is None:
            self.args.sort_by = "startedAt"
        if self.args.order_by is None:
            self.args.order_by = "desc"
        if self.args.limit is None:
            self.args.limit = 20
        if self.args.offset is None:
            self.args.offset = 0

    def delete(self) -> None:
        """Main processing function for layout delete"""

        applyID = self.args.apply_id  # pylint: disable=C0103

        try:
            validate(applyID, schema=apply_id_scheme)
        except ValidationError as err:
            error_msg = err.message.split("\n")[-1]
            print(f"[E40001]{error_msg}", file=sys.stderr)
            sys.exit(ExitCode.VALIDATION_ERR)

        _, logger = self._initialize()

        try:
            database = DbAccess(logger)
            logger.info(f"Start delete cli. args:{vars(self.args)}")

            result_status = database.get_apply_status(applyID)
            if result_status.get("status") in [
                Result.IN_PROGRESS,
                Result.CANCELING,
                Result.SUSPENDED,
            ] or result_status.get("rollbackStatus") in [
                Result.IN_PROGRESS,
                Result.SUSPENDED,
            ]:
                print(
                    f"[E40024]{BeingRunningException().message}",
                    file=sys.stderr,
                )
                sys.exit(BeingRunningException().exit_code)

            database.delete(applyID)

        except psycopg2.OperationalError as err:
            exc = OperationalError(err)
            print(f"[E40018]{exc.message}", file=sys.stderr)
            sys.exit(exc.exit_code)
        except psycopg2.ProgrammingError as err:
            exc = ProgrammingError(err)
            print(f"[E40019]{exc.message}", file=sys.stderr)
            sys.exit(exc.exit_code)
        except IdNotFoundException as err:
            print(f"[E40020]{err.message}", file=sys.stderr)
            sys.exit(err.exit_code)

        print("Success.")

        logger.info(f"End delete cli. exit_code:{ExitCode.NORMAL}")
        sys.exit(ExitCode.NORMAL)

    def resume(self) -> None:
        """Main processing function for layout resume"""

        applyID = self.args.apply_id  # pylint: disable=C0103

        try:
            validate(applyID, schema=apply_id_scheme)
        except ValidationError as err:
            error_msg = err.message.split("\n")[-1]
            print(f"[E40001]{error_msg}", file=sys.stderr)
            sys.exit(ExitCode.VALIDATION_ERR)

        config, logger = self._initialize()

        try:
            database = DbAccess(logger)
            logger.info(f"Start resume cli. args:{vars(self.args)}")
            proc_result = database.proc_resume(applyID)
        except psycopg2.OperationalError as err:
            exc = OperationalError(err)
            print(f"[E40018]{exc.message}", file=sys.stderr)
            sys.exit(exc.exit_code)
        except psycopg2.ProgrammingError as err:
            exc = ProgrammingError(err)
            print(f"[E40019]{exc.message}", file=sys.stderr)
            sys.exit(exc.exit_code)
        except IdNotFoundException as err:
            print(f"[E40020]{err.message}", file=sys.stderr)
            sys.exit(err.exit_code)

        exit_code = self._make_resume_result(database, logger, config, proc_result, applyID)
        logger.info(f"End resume cli. exit_code:{exit_code}")
        sys.exit(exit_code)

    def _make_resume_result(
        self,
        database: DbAccess,
        logger: Logger,
        config: LayoutApplyConfig,
        proc_result: dict,
        applyID: str,
    ):  # pylint: disable=C0103,R0913
        """make resume result.

        Args:
            database (DbAccess): DbAccess object
            logger (Logger): logger
            config (LayoutApplyConfig): LayoutApplyConfig
            proc_result (dict): applystatus of exec resume before
            applyID (str): LayoutApplyID
        Returns:
            exit_code (int): exit code
        """
        status, rollback_status = proc_result.get("status"), proc_result.get("rollbackStatus")
        exit_code = ExitCode.NORMAL  # Default
        if status == Result.SUSPENDED:
            input_procedure = {"procedures": proc_result.get("resumeProcedures")}
            proc_id = self._exec_subprocess(logger, input_procedure, config, applyID, Action.RESUME)
            self._update_subporcess_info(database, proc_id, applyID)
            print("Success.")
            print(f"status={Result.IN_PROGRESS}")
        elif rollback_status == Result.SUSPENDED:
            input_procedure = {"procedures": proc_result.get("resumeProcedures")}
            proc_id = self._exec_subprocess(logger, input_procedure, config, applyID, Action.ROLLBACK_RESUME)
            self._update_subporcess_info(database, proc_id, applyID)
            print("Success.")
            print(f"status={status}")
            print(f"rollbackStatus={Result.IN_PROGRESS}")
        elif status == Result.CANCELED and rollback_status in [
            Result.COMPLETED,
            Result.FAILED,
        ]:
            print("Success.")
            print(f"status={status}")
            print(f"rollbackStatus={rollback_status}")
        elif status in [Result.COMPLETED, Result.FAILED] or (status == Result.CANCELED and rollback_status is None):
            print("Success.")
            print(f"status={status}")
        else:
            # An error occurs if the reflection status is IN_PROGRESS or CANCELING,
            # or if the reflection status is CANCELED and the rollback status is IN_PROGRESS.
            exit_code = AlreadyExecuteException().exit_code
            error_msg = f"[E40022]{AlreadyExecuteException().message}"
            print(error_msg, file=sys.stderr)
            logger.error(error_msg)

        return exit_code

    def _update_subporcess_info(self, database: DbAccess, pid: str, apply_id: str):
        """update subporcess info to db.

        Args:
            database (DbAccess): DbAccess object
            pid (str): subprocess id
            apply_id (str): apply id
        """
        try:
            database.update_subprocess(pid, apply_id)
        except psycopg2.OperationalError as err:
            exc = OperationalError(err)
            print(f"[E40018]{exc.message}", file=sys.stderr)
            sys.exit(exc.exit_code)
        except psycopg2.ProgrammingError as err:
            exc = ProgrammingError(err)
            print(f"[E40019]{exc.message}", file=sys.stderr)
            sys.exit(exc.exit_code)

    def _set_fields_list(
        self,
        fields: str,
    ) -> list:
        """Set list of fields

        Args:
            fields (str): specified fields of args

        Returns:
            list: Set list
        """
        if fields is not None:
            fields_list = fields.split(",")
        else:
            fields_list = None

        return fields_list

    def _validate_option_for_get_cli(self, args: dict, fields: list = None, date_dict: dict = None) -> None:
        """Validate option of get cli

        Args:
            args (dict): specified option
            fields (list): specified column
            date_dict (dict): specified date
        """
        self._validate_output_path(args.output)
        # Define the schemas and corresponding arguments for validation
        validation_pairs = [
            (args.apply_id, apply_id_scheme),
            (args.sort_by, sortBy_schema),
            (args.order_by, orderBy_schema),
            (args.limit, limit_schema),
            (args.offset, offset_schema),
            (args.status, status_schema),
            (fields, fields_schema),
        ]

        try:
            # Validate provided arguments if they are not None
            for arg, schema in validation_pairs:
                if arg is not None:
                    validate(arg, schema=schema)
            if date_dict is not None:
                for key, value in date_dict.items():
                    date_val = iso8601.parse_date(value)
                    date_dict[key] = str(date_val.astimezone(ZoneInfo("UTC")))
        except ValidationError as err:
            error_msg = err.message.split("\n")[-1]
            print(f"[E40001]{error_msg}", file=sys.stderr)
            sys.exit(ExitCode.VALIDATION_ERR)
        except iso8601.ParseError as err:
            print(f"[E40001]{err}", file=sys.stderr)
            sys.exit(ExitCode.VALIDATION_ERR)

    def _load_logger(self, config: LayoutApplyConfig) -> Logger:
        """Initialize the log object.
        Args:
            config (LayoutApplyConfig): LayoutApplyConfig object
        Returns:
            Logger: logger object
        """
        try:
            logger = Logger(config.log_config)
        except Exception as error:  # pylint: disable=W0703
            raise LoggerLoadException() from error
        return logger

    def _initialize(self) -> Tuple[LayoutApplyConfig, Logger]:
        """Initialize the configuration file object and log object.

        Returns:
            Tuple[LayoutApplyConfig, Logger]: Config object and logger object
        """
        try:
            config = LayoutApplyConfig()
            config.load_log_configs()
        except SettingFileLoadException as error:
            print(f"[E40002]{error.message}", file=sys.stderr)
            sys.exit(error.exit_code)
        except SecretInfoGetException as error:
            print(f"[E40030]{error.message}", file=sys.stderr)
            sys.exit(error.exit_code)

        try:
            logger = self._load_logger(config)
        except LoggerLoadException as error:
            print(f"[E40031]{error.message}", file=sys.stderr)
            sys.exit(error.exit_code)
        return config, logger

    def _wirte_result_file(self, file_path: str, result: dict, logger: Logger) -> None:
        """Output dictionary data to a file, and dump it to the error log if it fails.

        Args:
            file_path (str): File path
            result (dict):  Dictionary data
            logger (Logger): Logger
        """
        try:
            self._write_file(file_path, result)
        except Exception:  # pylint: disable=W0703
            msg = f"[E40006]{FailedOutputError().message}"
            print(msg, file=sys.stderr)
            logger.error(msg, stack_info=False)
            sys.exit(FailedOutputError().exit_code)

    def _write_file(self, file_path: str, json_data: dict) -> None:
        """Output a file".

        Args:
            file_path (str): File path
            json_data (dict): Dictionary data to dump
        """
        dirname = os.path.dirname(file_path)
        if len(dirname) != 0:
            os.makedirs(dirname, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(json_data, file, indent=4)

    def _read_procedure(self, file_path: str) -> dict:
        """Argument: Read the file specified in the procedure.

        Args:
            file_path (str): Migration procedure file path

        Returns:
            dict: Migration procedure
        """
        try:
            with open(file_path, encoding="utf-8") as file:
                procedure = json.load(file)

            validate(instance=procedure, schema=procedure_scheme)
        except ValidationError as exception:  # pylint: disable=W0703
            print(f"[E40001]{exception.message}", file=sys.stderr)
            sys.exit(ExitCode.VALIDATION_ERR)
        except Exception as exception:  # pylint: disable=W0703
            print(f"[E40001]{exception}", file=sys.stderr)
            sys.exit(ExitCode.VALIDATION_ERR)

        return procedure

    def _validate_output_path(self, filepath: str) -> None:
        """validate oupput path.

        Args:
            filepath (str): oupput path
        """
        if filepath and (filepath.endswith(os.sep) or os.path.isdir(filepath)):
            print(f"[E40001]{OutPathPointError().message}", file=sys.stderr)
            sys.exit(OutPathPointError().exit_code)

    def _validate_allowed_args(self, args: dict) -> None:
        """validate specified args. not allowed with argument.

        Args:
            args (dict): specified args
        """
        for option_key in args.__dict__.keys():
            # Since the args also contain command (subcommand) and apply-id,
            # judging with not None will get caught by command and apply-id.
            # Therefore, skip command, apply-id, and output.
            if option_key in ("command", "apply_id", "output"):
                continue
            if args.__dict__[option_key] is not None:
                print(f"[E40001]{NotAllowedWithError().message}", file=sys.stderr)
                sys.exit(NotAllowedWithError().exit_code)

    def _exec_subprocess(
        self,
        logger: Logger,
        procedure: dict,
        config: LayoutApplyConfig,
        applyID: str,
        action: str,
    ):  # pylint: disable=C0103,R0913
        """execute subprocess

        Args:
            logger (Logger): logger
            procedure (dict): Migration procedure
            config (LayoutApplyConfig): Configuration object.
            applyID (str): layoutapply ID
            action (str): action type. apply or resume. If not specified, apply action.
        Returns:
            proc.pid (str): process id
        """
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as fp:
                fp.write(pickle.dumps(SubprocOpt(procedure, config, applyID, action)).hex())

            proc = subprocess.Popen(
                [
                    sys.executable,
                    os.path.join("/", *__file__.split("/")[:-1], "main_executor.py"),
                    fp.name,
                ]
            )
        except Exception as err:  # pylint: disable=W0703
            exc = FailedStartSubprocessException(err)
            msg = f"[E40026]{exc.message}"
            logger.error(msg)
            print(msg, file=sys.stderr)
            sys.exit(exc.exit_code)
        return proc.pid


def main() -> None:
    """entry point"""
    cmd = LayoutApplyCommandLine()
    cmd.run()


if __name__ == "__main__":  # pragma: no cover
    main()
