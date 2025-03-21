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
"""Main routine"""

import copy
from concurrent.futures import ALL_COMPLETED, FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import asdict
from typing import Generator

from layoutapply.apiclient import ConnectAPI, DisconnectAPI, PowerOffAPI, PowerOnAPI
from layoutapply.cdimlogger import Logger
from layoutapply.const import Action, ApiExecuteResultIdx, Operation, Result
from layoutapply.custom_exceptions import FailedExecuteLayoutApplyError
from layoutapply.data import Details, Procedure, details_dict_factory, get_procedure_list, procedure_dict_factory
from layoutapply.db import DbAccess, UpdateOption
from layoutapply.setting import LayoutApplyConfig


def run(  # pylint: disable=C0103
    procedure: dict,
    config: LayoutApplyConfig,
    applyID: str,
    action: str = Action.REQUEST,
):
    """Main routine execute

    Args:
        procedure (dict): Migration procedure
        config (LayoutApplyConfig): Configuration object.
        applyID (str): layoutapply ID
        action (str): action type. apply or resume. If not specified, apply action.
    """
    try:
        logger = Logger(**config.logger_args)
        _run(procedure, config, applyID, logger, action)
    except Exception as err:  # pylint: disable=W0718
        logger.error(f"[E40005]{FailedExecuteLayoutApplyError().message} {err}", stack_info=True)


def _run(  # pylint: disable=C0103, R0914
    procedure: dict,
    config: LayoutApplyConfig,
    applyID: str,
    logger: Logger,
    action: str,
):
    """Main routine for parallel execution (multiprocessing)

    Args:
        procedure (dict): Migration procedure
        config (LayoutApplyConfig): Configuration object.
        applyID (str): layoutapply ID
        logger (Logger): logger
        action (str): action type. apply or resume. If not specified, apply action.
    """
    database = DbAccess(logger)
    executed_list = []
    task_list = []
    executor = _set_executor(config)
    cancel_flg = False
    rollback_flg = False
    is_suspended = False

    logger.info("Start running")
    # List the migration procedure and obtain the size for completion judgment
    proc_list: list[Procedure] = get_procedure_list(procedure)
    proc_count = len(proc_list)
    origin_proc_list = copy.deepcopy(proc_list)
    on_loop = True

    current_status = _get_current_status(database, applyID)

    if current_status.get("status") != Result.CANCELING:
        _set_first_task(task_list, proc_list, executor, config)
    else:
        # Extract all remaining steps for cancellation and add them to the operation completion list
        cancel_flg = True
        logger.debug("Cancel requested detected. All tasks canceled.")
        _add_canceld_proc(executed_list, proc_list)
        on_loop = False

    last_done = set()
    while on_loop:
        # Wait until either of the tasks is completed
        # Tasks within "tasks" each have an execution status, and during wait, unexecuted tasks are executed
        done, _ = wait(task_list, return_when=FIRST_COMPLETED)
        # Get the difference set between the last completed task and
        # most recent completed task to obtain the most recently completed task
        latest_done = done - last_done
        last_done = done
        # Obtain the interruption flag information from the most recently completed task
        if is_suspended is False:  # pragma: no cover
            is_suspended = _is_task_suspended(latest_done)

        if is_suspended is False:
            current_status = _get_current_status(database, applyID)
            if current_status.get("status") == Result.CANCELING:
                cancel_flg = True
                rollback_flg = current_status.get("executeRollback")
                logger.debug("Cancel requested detected. Last procedures canceled.")
                # If the cancel flag is set to True,
                # wait until all the APIs of the currently executing hardware control functions are completed
                done, _ = wait(task_list, return_when=ALL_COMPLETED)
                latest_done = list(latest_done)
                for last_task in done - last_done:
                    latest_done.append(last_task)

        for task in latest_done:
            detail: Details = task.result()[ApiExecuteResultIdx.DETAIL]
            _add_result(detail, executed_list, proc_list, cancel_flg)

            _set_next_task(task_list, proc_list, executed_list, executor, config)

        # Exit the loop when all migration procedures have been executed
        if len(executed_list) == proc_count:
            executor.shutdown(wait=False, cancel_futures=True)
            break

    _update_layoutapply(
        executed_list,
        origin_proc_list,
        applyID,
        procedure,
        logger,
        config,
        rollback_flg,
        database,
        is_suspended,
        action,
    )
    logger.info("Completed successfully.")


def _cancel_run(procedure: dict, config: LayoutApplyConfig, logger: Logger):  # pylint: disable=C0103
    """Cancel routine for parallel execution (multiprocessing)

    Args:
        procedure (dict): Migration procedure
        config (LayoutApplyConfig): Configuration object.
        logger (Logger): logger
    Returns:
        list: Results of migration procedure
    """
    executed_list = []
    task_list = []
    executor = _set_executor(config)
    is_suspended = False

    logger.info("Start rollback")
    proc_list: list[Procedure] = get_procedure_list(procedure)
    proc_count = len(proc_list)

    _set_first_task(task_list, proc_list, executor, config)

    last_done = set()
    while True:
        done, _ = wait(task_list, return_when=FIRST_COMPLETED)
        latest_done = done - last_done
        last_done = done
        if is_suspended is False:  # pragma: no cover
            is_suspended = _is_task_suspended(latest_done)

        for task in latest_done:
            execute_result = task.result()
            detail: Details = execute_result[ApiExecuteResultIdx.DETAIL]
            _add_result(detail, executed_list, proc_list, False)

            _set_next_task(task_list, proc_list, executed_list, executor, config)

        if len(executed_list) == proc_count:
            executor.shutdown(wait=False, cancel_futures=True)
            break

    return executed_list, is_suspended


def _set_executor(config) -> ProcessPoolExecutor:
    """Set ProcessPoolExecutor worker

    Args:
        config (LayoutApplyConfig): Configuration object.
    Returns:
        executor(ProcessPoolExecutor): ProcessPoolExecutor worker
    """
    executor = None
    if "request" in config.layout_apply and config.layout_apply["request"].get("max_workers") is not None:
        executor = ProcessPoolExecutor(max_workers=config.layout_apply["request"].get("max_workers"))
    else:
        # max_workers uses os.process_cpu_count() by default
        executor = ProcessPoolExecutor()

    return executor


def _get_current_status(database, applyID):  # pylint: disable=C0103
    """Get current applystatus

    Args:
        database (DbAccess): database object
        applyID (str): layoutapply ID
    Returns:
        applystatus(str): current applystatus
    """
    applystatus = {}
    applystatus = database.get_apply_status(applyID)  # pylint: disable=C0103

    return applystatus


def _update_layoutapply(  # pylint: disable=C0103
    executed_list: list[Details],
    origin_proc_list: list[Procedure],
    applyID: str,
    procedure: dict,
    logger: Logger,
    config: LayoutApplyConfig,
    rollback_flg: bool,
    database: DbAccess,
    is_suspended: bool,
    action: str,
) -> None:
    """Update layoutapply

    Args:
        executed_list (list[Details]): completed operations
        origin_proc_list (list[Procedure]): Migration plan list
        applyID (str): layoutapply ID
        procedure (dict): Migration procedure
        logger (Logger): logger
        config (LayoutApplyConfig): config
        rollback_flg (bool): rollback_flg
        database (DbAccess): database object
        is_suspended (bool): is_suspended
        action (str): action type. apply or resume. If not specified, apply action.
    """

    rollback_procedures_list = []
    resume_procedures_list = []
    rollback_status = ""
    rollback_result = {}
    resume_result = []
    resume_origin_proc_list = copy.deepcopy(origin_proc_list)
    resume_executed_list = copy.deepcopy(executed_list)

    result, apply_result = _create_result(executed_list, logger, is_suspended)

    if result == Result.CANCELED:
        rollback_procedure = _create_rollback_proc(origin_proc_list, executed_list)
        rollback_procedures_list = [asdict(i, dict_factory=procedure_dict_factory) for i in rollback_procedure]
        if rollback_flg:
            input_procedure = {}
            input_procedure["procedures"] = rollback_procedures_list

            database.update_rollback_status(  # pylint: disable=C0103
                applyID,
                Result.IN_PROGRESS,
            )
            rollback_executed_list, is_rollback_suspended = _cancel_run(input_procedure, config, logger)

            rollback_status, rollback_result = _create_result(rollback_executed_list, logger, is_rollback_suspended)

            resume_origin_proc_list = get_procedure_list(input_procedure)
            resume_executed_list = rollback_executed_list
    if action == Action.RESUME:
        # Set the restart results, migration procedure to exclude from the update targets,
        # and initialize the reflected results.
        resume_result = copy.deepcopy(apply_result)
        procedure, apply_result = None, []
    if action == Action.ROLLBACK_RESUME:
        # Resetting the restart results and rollback state, excluding the migration steps and
        # results from the update targets, and initializing the reflection results and state.
        resume_result = copy.deepcopy(apply_result)
        rollback_status = copy.deepcopy(result)
        procedure, apply_result, result = None, [], ""
    if Result.SUSPENDED in (result, rollback_status):
        resume_procedure = _create_resume_proc(resume_origin_proc_list, resume_executed_list)
        resume_procedures_list = [asdict(i, dict_factory=procedure_dict_factory) for i in resume_procedure]

    database.update(  # pylint: disable=C0103
        UpdateOption(
            applyID=applyID,
            status=result,
            procedures=procedure,
            applyresult=apply_result,
            rollbackprocedures=rollback_procedures_list,
            rollback_status=rollback_status,
            rollback_result=rollback_result,
            resumeprocedures=resume_procedures_list,
            resume_result=resume_result,
        )
    )


def _create_result(executed_list: list[Details], logger: Logger, is_suspended: bool = False):
    """Create layoutapply result or rollback result

    Args:
        executed_list (list): executed list
        logger (Logger): logger
    Returns:
        status (str): executed result status
        applyresult (list): applyresult

    """
    status = Result.COMPLETED
    if is_suspended:
        status = Result.SUSPENDED
    elif len(_get_ids(executed_list, Result.FAILED)) > 0:
        status = Result.FAILED
        logger.error(f"[E40005]{FailedExecuteLayoutApplyError().message}", stack_info=False)
    elif len(_get_ids(executed_list, Result.CANCELED)) > 0:
        status = Result.CANCELED

    applyresult = [asdict(i, dict_factory=details_dict_factory) for i in executed_list]

    return status, applyresult


def _set_first_task(
    task_list: list,
    proc_list: list,
    executor: ProcessPoolExecutor,
    config: LayoutApplyConfig,
) -> None:
    """Set first task.

    Args:
        task_list (list): task list
        proc_list (list): Migration plan list
        executor (ProcessPoolExecutor): ProcessPoolExecutor
        config (LayoutApplyConfig): config
    """
    # Register migration steps with empty dependencies
    # from the migration steps list as the initial execution task.
    # Remove the tasks that have been migrated from the migration procedure list
    for proc in _find_first_proc(copy.deepcopy(proc_list)):
        task_list.append(_create_task(proc, executor, config))
        proc_list.remove(proc)


def _set_next_task(
    task_list: list,
    proc_list: list,
    executed_list: list,
    executor: ProcessPoolExecutor,
    config: LayoutApplyConfig,
) -> None:
    """Set next task.

    Args:
        task_list (list): task list
        proc_list (list): Migration plan list
        executed_list (list): completed operations
        executor (ProcessPoolExecutor): ProcessPoolExecutor
        config (LayoutApplyConfig): config
    """
    # Extract executable migration procedures from the list of migration procedure
    for proc in _find_next_proc(executed_list, proc_list):
        task_list.append(_create_task(proc, executor, config))
        proc_list.remove(proc)


def _add_result(detail: Details, executed_list: list, proc_list: list, cancel_flg: bool):
    """Add detail to executed_list

    Args:
        detail (Details): operations results
        executed_list (list): completed operations
        proc_list (list): Migration plan list
        cancel_flg (Value): Whether a cancellation request has been received or not.
    """
    executed_list.append(detail)

    # Add the steps after the abnormal termination as skip targets to the operation completion list.
    if detail.status == Result.FAILED:
        _add_skiped_proc(executed_list, proc_list)

    # If the cancel flag is set to True, extract all remaining steps in the migration procedure list
    # as cancel targets and add them to the operation completion list.
    if cancel_flg is True:
        _add_canceld_proc(executed_list, proc_list)


def _add_canceld_proc(executed_list: list, proc_list: list) -> None:
    """Add all remaining steps to the list of completed operations as canceled steps.

    Args:
        executed_list (list): completed operations
        proc_list (list): Migration plan list
    """
    for proc in proc_list:
        detail: Details = Details(operationID=proc.operationID, status=Result.CANCELED)
        executed_list.append(detail)
    proc_list.clear()


def _add_skiped_proc(executed_list: list, proc_list: list) -> None:
    """Add step that was skipped due to failed operation to the list of completed

    Args:
        executed_list (list): completed operations
        proc_list (list): Migration plan list
    """
    failed_ids = _get_ids(executed_list, Result.FAILED)
    skip_ids = _get_skip_ids(proc_list, failed_ids)
    for proc in copy.deepcopy(proc_list):
        if proc.operationID in skip_ids:
            executed_list.append(Details(operationID=proc.operationID, status=Result.SKIP))
            proc_list.remove(proc)


def _find_first_proc(proc_list: list) -> Generator[dict, None, None]:
    """Return the migration plan with no dependencies, which is the first one to be executed

    Args:
        proc_list (list): Migration plan list

    Returns:
        Procedure: Migration plan

    Yields:
        Iterator[Procedure]: Generator that returns the initial migration procedure to be executed
    """
    for proc in proc_list:
        if not proc.dependencies:
            yield proc


def _find_next_proc(executed_list: list, proc_list: list) -> Generator[dict, None, None]:
    """Search for the migration plan and select the next task to be executed,
    which has all the operation IDs specified in its dependencies completed.

    Args:
        executed_list (list): completed operations
        proc_list (list): Migration plan list

    Returns:
        Procedure: Next migration procedure

    Yields:
        Iterator[Procedure]: A generator that creates the next migration procedure to execute
    """
    completed_ids = _get_ids(executed_list, Result.COMPLETED)
    for proc in proc_list:
        count = 0
        for ope_id in proc.dependencies:
            if ope_id in completed_ids:
                count = count + 1
            if count == len(proc.dependencies):
                yield proc


def _get_ids(executed_list: list, coditions: Result) -> list:
    """Extract and return a list of operation_ids from the completed list that match the conditions.

    Args:
        executed_list (list): completed operations
        coditions (Result): Status of the target to be searched (COMPLETED: success, FAILED: failure)

    Returns:
        list: List of operation_ids that match the conditions
    """
    return [i.operationID for i in executed_list if i.status == coditions]


def _get_skip_ids(proc_list: list, failed_ids: list) -> list:
    """Obtain the list of IDs for subsequent steps of the failed ID.

    Args:
        proc_list (list): Migration plan list
        failed_ids (list): List of operation IDs that failed to process

    Returns:
        list: List of operation_Id that failed to execute
    """
    skipped_ids = []
    # Generate a list of operationIDs included in dependencies that are part of the failure list.
    skiped_proc_list = [p for p in proc_list for id in p.dependencies if id in failed_ids]
    for proc in skiped_proc_list:
        if proc.operationID not in skipped_ids:
            skipped_ids.append(proc.operationID)
            # A recursive call is made to continue skipping the subsequent steps that were skipped.
            skipped_ids.extend(_get_skip_ids(proc_list, [proc.operationID]))
    return skipped_ids


def _create_task(
    procedure: Procedure,
    executor: ProcessPoolExecutor,
    config: LayoutApplyConfig,
) -> Future:
    """Generate tasks according to the operation.

    Args:
        procedure (Procedure): Feasible migration procedure
        executor (ProcessPoolExecutor): Multiprocessing pool
        config (LayoutApplyConfig) : Configuration information
    """
    # Change the setting values and call class according to the operation
    match procedure.operation:
        case Operation.POWEROFF:
            api_config = config.poweroff
            api_obj = PowerOffAPI
        case Operation.DISCONNECT:
            api_config = config.disconnect
            api_config["poweroff"] = config.poweroff
            api_obj = DisconnectAPI
        case Operation.CONNECT:
            api_config = config.connect
            api_config["isosboot"] = config.isosboot
            api_obj = ConnectAPI
        case Operation.POWERON:
            api_config = config.poweron
            api_config["isosboot"] = config.isosboot
            api_obj = PowerOnAPI
    # Generate a task call instance
    args = {
        "hardware_control_conf": config.hardware_control,
        "get_info_conf": config.get_information,
        "api_config": api_config,
        "logger_args": config.logger_args,
        "server_connection_conf": config.server_connection,
    }
    instance = api_obj(**args)

    return executor.submit(instance.execute, procedure)


def _create_rollback_proc(procedure_list: list[Procedure], executed_list: list[Details]) -> list[Procedure]:
    """Create a procedure to roll back a modified layout

    Args:
        procedure_list (list[Procedure]): Migration procedure list
        executed_list (list[Details]): Execution result list

    Returns:
        list[Procedure]: Rollback procedure list
    """
    # Extract the migration procedures subject to rollback from the migration procedures list
    target_proc_list = _get_rollback_target_proc(procedure_list, executed_list)
    rollback_procedure_list = []

    # Execute the following steps for the extracted rollback migration steps
    for _ in range(len(target_proc_list)):
        target_proc = target_proc_list.pop()

        _convert_to_rollback(target_proc, target_proc_list)
        rollback_procedure_list.append(target_proc)

    _clear_dependencies(rollback_procedure_list)

    return rollback_procedure_list


def _get_rollback_target_proc(procedure_list: list[Procedure], executed_list: list[Details]) -> list[Procedure]:
    """Extract migration procedures to rollback

    Args:
        procedure_list (list[Procedure]): Migration procedure list
        executed_list (list[Details]): Execution result list

    Returns:
        list[Procedure]: Rollback procedure list
    """
    # Extract operationIDs with EXECUTED status (COMPLETED) from the completed operations list
    completed_ids = _get_ids(executed_list, Result.COMPLETED)
    # Extract the migration procedures with operation IDs that match the operation IDs
    # extracted from the migration procedure list
    return [p for p in procedure_list if p.operationID in completed_ids]


def _convert_to_rollback(target_proc: Procedure, target_proc_list: list[Procedure]) -> None:
    """Convert a migration procedure to a rollback procedure

    Args:
        target_proc (Procedure): Rollback procedure for conversion
        target_proc_list (list[Procedure]): Migration procedure list
    """
    # Search for migration steps that have dependencies including the operationID
    # of the migration step to be rolled back
    for proc in target_proc_list:
        if target_proc.operationID in proc.dependencies:
            _swap_execution_order(target_proc=target_proc, proc=proc)
        elif proc.operationID in target_proc.dependencies:
            _swap_execution_order(target_proc=proc, proc=target_proc)

    _change_operation(target_proc)


def _clear_dependencies(target_proc_list: list[Procedure]) -> None:
    """If the relevant procedure does not exist in dependencies, make it an empty list

    Args:
        target_proc_list (list[Procedure]): Migration procedure list
    """
    # Get the list of operationIDs within the backup target list
    id_list = [i.operationID for i in target_proc_list]
    for proc in target_proc_list:
        # Delete dependencies that do not exist in the operationID list within the backup target list
        proc.dependencies = [i for i in proc.dependencies if i in id_list]


def _swap_execution_order(target_proc: Procedure, proc: Procedure) -> None:
    """Swap the order in which migration steps are performed

    Args:
        target_proc (Procedure): Rollback procedure for conversion
        proc (Procedure): Migration procedure with dependencies
    """
    # Delete the operationID of the migration steps to be rolled back from the detected migration steps' dependencies.
    proc.dependencies = [i for i in proc.dependencies if i != target_proc.operationID]
    # Add the operation ID of the detected migration procedure to
    # dependencies of the migration procedure to be rolled back.
    target_proc.dependencies.append(proc.operationID)


def _change_operation(target_proc: Procedure) -> None:
    """Change the operation of the migration procedure
    |origin    |   |result    |
    |----------|---|----------|
    |shutdown  | → |boot      |
    |boot      | → |shutdown  |
    |connect   | → |disconnect|
    |disconnect| → |connect   |

    Args:
        target_proc (Procedure): Rollback procedure for conversion
    """
    match target_proc.operation:
        case Operation.POWEROFF:
            target_proc.operation = str(Operation.POWERON)
        case Operation.POWERON:
            target_proc.operation = str(Operation.POWEROFF)
        case Operation.CONNECT:
            target_proc.operation = str(Operation.DISCONNECT)
        case Operation.DISCONNECT:
            target_proc.operation = str(Operation.CONNECT)


def _create_resume_proc(procedure_list: list[Procedure], executed_list: list[Details]) -> list[Procedure]:
    """Create a procedure to resume a suspended layout

    Args:
        procedure_list (list[Procedure]): Migration procedure list
        executed_list (list[Details]): Execution result list

    Returns:
        list[Procedure]: Resume procedure list
    """
    # Extract migration steps to be executed upon resumption from the migration procedure list.
    # 1.Extract the steps with status FAILED and SKIPPED from the completed operations list.
    failed_ids = _get_ids(executed_list, Result.FAILED)
    failed_ids.extend(_get_ids(executed_list, Result.SKIP))
    completed_ids = _get_ids(executed_list, Result.COMPLETED)

    # 2.Search for the extracted migration procedure's operation ID in the migration procedure list,
    # and add it to the restart procedure.
    resume_procedure_list = []
    for procedure in procedure_list:
        if procedure.operationID in failed_ids:
            resume_procedure_list.append(procedure)

    # 3.If the ID stored with the status "COMPLETED" in the operation completion list is
    # included in the dependencies of the extracted procedure, delete it from the dependencies.
    for resume_procedure in resume_procedure_list:
        resume_procedure.dependencies = [num for num in resume_procedure.dependencies if num not in completed_ids]

    return resume_procedure_list


def _is_task_suspended(latest_done) -> bool:
    """task result is susupeded or not.

    Args:
        latest_done (list): task results list

    Returns:
        bool: true means exists suspeded task. false means not exists suspended task.
    """
    ret = False
    for task in latest_done:
        if task.result()[ApiExecuteResultIdx.SUSPEND_FLG] is True:
            ret = True
            break
    return ret
