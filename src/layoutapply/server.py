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
"""LayoutApply API request-response function"""

import copy
import json
import sys
from http import HTTPStatus
from multiprocessing import Process
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

import iso8601
import psycopg2
import uvicorn
from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from jsonschema import ValidationError, validate
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.cors import CORSMiddleware

from layoutapply.cdimlogger import Logger
from layoutapply.const import Action, Result
from layoutapply.custom_exceptions import (
    AlreadyExecuteException,
    BeingRunningException,
    FailedStartSubprocessException,
    IdNotFoundException,
    JsonSchemaError,
    LoggerLoadException,
    MultipleInstanceError,
    OperationalError,
    ProgrammingError,
    RequestError,
    SecretInfoGetException,
    SettingFileLoadException,
    SubprocessNotFoundException,
    SuspendedDataExistException,
)
from layoutapply.db import DbAccess, GetAllOption
from layoutapply.main import run
from layoutapply.migration_apiclient import ConfigManagerAPI, GetAvailableResourcesAPI, MigrationAPI
from layoutapply.schema import action as action_scheme
from layoutapply.schema import apply_id as apply_id_scheme
from layoutapply.schema import desiredLayout as desiredLayout_schema
from layoutapply.schema import fields as fields_schema
from layoutapply.schema import limit as limit_schema
from layoutapply.schema import offset as offset_schema
from layoutapply.schema import orderBy as orderBy_schema
from layoutapply.schema import procedure as procedure_schema
from layoutapply.schema import sortBy as sortBy_schema
from layoutapply.schema import status as status_schema
from layoutapply.schema import targetNodeID as targetNodeID_schema
from layoutapply.schema import time_format as time_format_schema
from layoutapply.setting import LayoutApplyConfig
from layoutapply.util import create_applystatus_response, set_date_dict

app = FastAPI()
BASEURL = "/cdim/api/v1/"
DATABASE = None

# Add to bypass CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Setting to allow response
    allow_credentials=True,  # Settings to allow credentials on CORS requests
    allow_methods=["*"],  # Settings to allow request methods for CORS requests
    allow_headers=["*"],  # Settings to allow headers in CORS requests
)


class ProcedureList(BaseModel):
    """Model class for the migration procedure list"""

    procedures: list

    @field_validator("procedures")
    def validate_procedure(cls, procedures):  # pylint: disable=E0213
        """Validation check of migration procedure

        Args:
            procedure (dict): migration procedure

        Returns:
            dict: migration procedure
        """
        validate({"procedures": procedures}, procedure_schema)
        return procedures


class DesiredLayout(BaseModel):
    """Model class for the desiredLayout"""

    targetNodeIDs: Optional[list] = Field(None)
    desiredLayout: dict

    @field_validator("desiredLayout")
    def validate_desiredLayout(cls, desiredLayout):  # noqa: E501 pylint: disable=C0103,E0213
        """Validation check of desiredLayout

        Args:
            desiredLayout (dict): desiredLayout

        Returns:
            dict: desiredLayout
        """
        validate(desiredLayout, desiredLayout_schema)
        return desiredLayout

    @field_validator("targetNodeIDs")
    def validate_targetNodeID(cls, targetNodeIDs):  # noqa: E501 pylint: disable=C0103,E0213
        """Validation check of targetNodeIDs

        Args:
            targetNodeIDs (list): targetNodeIDs

        Returns:
            list: targetNodeIDs
        """
        validate(targetNodeIDs, targetNodeID_schema)
        return targetNodeIDs


class GetAllLayoutApplyOptions(BaseModel):
    """Data model to store options for the list retrieval function"""

    model_config = {"extra": "forbid"}

    status: Optional[str] = None
    startedAtSince: Optional[str] = None
    startedAtUntil: Optional[str] = None
    endedAtSince: Optional[str] = None
    endedAtUntil: Optional[str] = None
    sortBy: Optional[str] = "startedAt"
    orderBy: Optional[str] = "desc"
    limit: Optional[int] = 20
    offset: Optional[int] = 0


def _initialize() -> Tuple[LayoutApplyConfig, Logger]:
    """Initialize the configuration file object and log object.

    Returns:
        Tuple[LayoutApplyConfig, Logger]: Config object and logger object
    """
    config = LayoutApplyConfig()
    try:
        logger = Logger(**config.logger_args)
    except Exception as error:
        raise LoggerLoadException() from error
    return config, logger


def _get_db_connection(logger: Logger):
    """DB connect

    Args:
        logger (Logger): Logger object

    Returns:
        class: DBACCESS Class
    """
    return DbAccess(logger)


@app.post(BASEURL + "layout-apply", response_class=JSONResponse)
def execute_layoutapply(procedure: ProcedureList):
    """execute layoutapply(API)
    Args:
        procedure (Procedure): list of migration procedure

    Returns:
        JsonResponse: A Json object containing the status code and the object to be returned
    """
    proc = procedure.model_dump()
    proc_len = len(proc.get("procedures"))
    config, logger = _initialize()

    logger.info(f"Start request api. args.procedure: {json.dumps(proc)}")
    logger.debug(f"config: {vars(config)}")

    # Control dual boot
    database = _get_db_connection(logger)
    applyID = database.register(is_empty=proc_len == 0)  # pylint: disable=C0103
    logger.debug(f"applyID: {applyID}")

    # Do not run the subprocess if the migration procedure list is empty.
    if proc_len != 0:
        # Execute a subprocess asynchronously
        response_code, return_data, proc_id = _exec_subprocess(logger, proc, config, applyID, Action.REQUEST)
        database.update_subprocess(proc_id, applyID)
        if response_code is not None:
            return JSONResponse(status_code=response_code, content=return_data)

    result_json = {"applyID": applyID}
    return_value = JSONResponse(status_code=HTTPStatus.ACCEPTED.value, content=result_json)
    logger.info(f"End request api. status_code:{HTTPStatus.ACCEPTED.value}")
    return return_value


@app.put(BASEURL + "layout-apply/{ApplyID}", response_class=JSONResponse)
def action_layoutapply(ApplyID: str, action: str, rollbackOnCancel: bool = False):  # noqa: E501 pylint: disable=C0103
    """action cancel or resume layoutapply(API)
    Args:
        ApplyID (str): layout applyID
        action (str): request action. cancel or resume.
        rollbackOnCancel (bool):  Specified this option, exec rollback for cancel.
    Returns:
        JSONResponse: response
    """

    validate(ApplyID, schema=apply_id_scheme)
    validate(action, schema=action_scheme)

    config, logger = _initialize()

    if action == Action.CANCEL:
        response = _cancel_layoutapply(ApplyID, rollbackOnCancel, logger)
    else:
        response = _resume_layoutapply(ApplyID, config, logger)

    return response


def _cancel_layoutapply(applyID: str, rollback_flg: bool, logger: Logger):  # pylint: disable=C0103
    """exec cancel layoutapply
    Args:
        applyID: layout applyID
        rollback_flg: specified rollback option
        logger: logger

    Returns:
        JSONResponse: status_code, exec result
    """

    logger.info(f"Start cancel api. args.applyID:{applyID}. args.rollbackOnCancel:{json.dumps(rollback_flg)}.")
    database = _get_db_connection(logger)
    ret = database.proc_cancel(applyID, rollback_flg)

    # r_status is rollback_status
    pre_status, status = ret["pre_status"], ret["status"]
    pre_r_status, r_status = ret["pre_r_status"], ret["r_status"]

    # Adjusting response content in accordance with the results of the cancellation process
    if pre_status == Result.IN_PROGRESS and status == Result.FAILED:
        exc = SubprocessNotFoundException("status")
        return_data = {"code": "E40028", "message": exc.message, "status": status}
        logger.error(f"[E40028]{exc.message}")
        response_code = exc.status_code
    elif pre_r_status == Result.IN_PROGRESS and r_status == Result.FAILED:
        exc = SubprocessNotFoundException("rollbackStatus")
        logger.error(f"[E40028]{exc.message}")
        return_data = {
            "code": "E40028",
            "message": exc.message,
            "status": status,
            "rollbackStatus": r_status,
        }
        response_code = exc.status_code
    elif pre_status in [Result.IN_PROGRESS, Result.SUSPENDED]:
        response_code, return_data = HTTPStatus.ACCEPTED.value, {"status": status}
    elif pre_r_status == Result.SUSPENDED:
        response_code, return_data = HTTPStatus.ACCEPTED.value, {
            "status": status,
            "rollbackStatus": r_status,
        }
    elif pre_status in (Result.CANCELING, Result.CANCELED) and pre_r_status is None:
        response_code, return_data = HTTPStatus.OK.value, {"status": status}
    elif pre_r_status in (Result.COMPLETED, Result.FAILED):
        response_code, return_data = HTTPStatus.OK.value, {
            "status": status,
            "rollbackStatus": r_status,
        }
    else:
        # Abnormal termination because the previous status was COMPLETED or FAILED,
        # making it impossible to transition to the executed status.
        # Or, if the status is CANCELED and the rollback status is IN_PROGRESS with no abnormality in the process,
        # process will be abnormally terminated as it is already requested to be canceled and cannot be transitioned
        msg = AlreadyExecuteException().message
        return_data = {"code": "E40022", "message": msg}
        logger.error(f"[E40022]{msg}")
        response_code = AlreadyExecuteException().status_code

    logger.info(f"End cancel api. status_code:{response_code}")
    return JSONResponse(status_code=response_code, content=return_data)


@app.get(BASEURL + "layout-apply/{applyID}", response_class=JSONResponse)
def get_applystatus(applyID, fields: List[str] = Query(None)):  # pylint: disable=C0103
    """layoutapply get(API)
    Args:
        applyID: layoutapply id
        fields: specify the items for return information

    Returns:
        JsonResponse: include status_code, applystatus
    """

    return_data = _validate_option_for_get_api(fields, applyID)
    if return_data:
        return JSONResponse(status_code=HTTPStatus.BAD_REQUEST.value, content=return_data)

    config, logger = _initialize()

    logger.debug(f"config: {vars(config)}")

    logger.info(f"Start get api. args.applyID:{applyID}. args.fields:{json.dumps(fields)}.")
    database = _get_db_connection(logger)
    applystatus = database.get_apply_status(applyID, fields)

    logger.info("Completed successfully.")

    logger.info(f"End get api. status_code:{HTTPStatus.OK.value}")
    return JSONResponse(
        status_code=HTTPStatus.OK.value,
        content=create_applystatus_response(applystatus),
    )


@app.get(BASEURL + "layout-apply", response_class=JSONResponse)
def get_applystatus_list(
    options: GetAllLayoutApplyOptions = Depends(GetAllLayoutApplyOptions),
    fields: List[str] = Query(None),
):
    """layoutapply get list(API)
    Args:
        options: get all applystatus options
        fields: specify the items to be included in the return information.
    Returns:
        JsonResponse: include status_code, applystatus, count
    """
    # Set the specified date and time as a dict in the search conditions.
    date_dict = set_date_dict(
        options.startedAtSince,
        options.startedAtUntil,
        options.endedAtSince,
        options.endedAtUntil,
    )

    return_data = _validate_option_for_get_api(fields, None, date_dict, options)
    if return_data:
        return JSONResponse(status_code=HTTPStatus.BAD_REQUEST.value, content=return_data)

    config, logger = _initialize()

    logger.info(f"Start getall api. args:{vars(options)}. args.fields:{json.dumps(fields)}")
    logger.debug(f"config: {vars(config)}")

    database = _get_db_connection(logger)
    opts_dict = options.__dict__
    # Remove unused keys for unpacking
    del (
        opts_dict["endedAtUntil"],
        opts_dict["endedAtSince"],
        opts_dict["startedAtUntil"],
        opts_dict["startedAtSince"],
    )
    opts_dict["date_dict"] = date_dict
    opts_dict["fields"] = fields
    options_inst = GetAllOption(**opts_dict)
    applyresults = database.get_apply_status_list(options_inst)

    logger.info("Completed successfully.")
    logger.info(f"End getall api. status_code:{HTTPStatus.OK.value}")

    return JSONResponse(status_code=HTTPStatus.OK.value, content=applyresults)


def _validate_option_for_get_api(
    fields: str,
    applyID: str = None,  # pylint: disable=C0103
    date_dict: dict = None,
    options: GetAllLayoutApplyOptions = None,
) -> any:
    """Validate option of get api
    Args:
        applyID: applystatus ID
        fields: specify the items to be included in the return information.
        date_dict: specified date of args
        options: get all applystatus options

    Returns:
        return_data: if raised error, include error contents.
    """
    return_data = {}
    validation_pairs = [(applyID, apply_id_scheme), (fields, fields_schema)]
    if options is not None:
        validation_pairs.extend(
            [
                (options.sortBy, sortBy_schema),
                (options.orderBy, orderBy_schema),
                (options.limit, limit_schema),
                (options.offset, offset_schema),
                (options.status, status_schema),
            ]
        )
    try:
        # Validate provided options if they are not None
        for arg, schema in validation_pairs:
            if arg is not None:
                validate(arg, schema=schema)
        if date_dict is not None:
            for key, value in date_dict.items():
                validate(value, schema=time_format_schema)
                date_val = iso8601.parse_date(value)
                date_dict[key] = str(date_val.astimezone(ZoneInfo("UTC")))
    except ValidationError as err:
        error_message = err.message.split("\n")[-1]
        return_data = {"code": "E40001", "message": error_message}
    except iso8601.ParseError as err:
        return_data = {"code": "E40001", "message": str(err)}

    return return_data


@app.delete(BASEURL + "layout-apply/{ApplyID}", response_class=JSONResponse)
def delete_layoutapply(ApplyID: str):  # pylint: disable=C0103
    """delete layoutapply data(API)
    Args:
        ApplyID (str): specified applyID for delete
    Returns:
        JsonResponse: include status_code
    """

    validate(ApplyID, schema=apply_id_scheme)

    config, logger = _initialize()
    logger.debug(f"config: {vars(config)}")

    logger.info(f"Start delete api. args.applyID:{ApplyID}")
    database = _get_db_connection(logger)

    # Obtain the current reflection status and check if it is not an in-progress status.
    result_status = database.get_apply_status(ApplyID)
    if result_status.get("status") in [
        Result.IN_PROGRESS,
        Result.CANCELING,
        Result.SUSPENDED,
    ] or result_status.get("rollbackStatus") in [
        Result.IN_PROGRESS,
        Result.SUSPENDED,
    ]:
        exc = BeingRunningException()
        return_data = {"code": "E40024", "message": exc.message}
        return JSONResponse(status_code=exc.status_code, content=return_data)

    database.delete(ApplyID)

    logger.info(f"End delete api. status_code:{HTTPStatus.NO_CONTENT.value}")
    return Response(status_code=HTTPStatus.NO_CONTENT.value)


@app.post(BASEURL + "migration-procedures", response_class=JSONResponse)
def execute_migration(desiredLayout: DesiredLayout):  # pylint: disable=C0103
    """execute generate migration procedure(API)
    Args:
        desiredLayout (desiredLayout): desiredLayout

    Returns:
        JsonResponse: A Json object that stores the status code and the returned object
    """
    desired_layout = desiredLayout.model_dump()

    config, logger = _initialize()
    logger.info(f"Start migration_generate api. args.desiredLayout:{json.dumps(desired_layout)}")
    logger.debug(f"config: {vars(config)}")

    # Get a list of all nodes
    code, get_all_nodes_resp = ConfigManagerAPI(
        logger, config.configuration_manager, config.server_connection
    ).execute()

    if code != HTTPStatus.OK.value:
        return JSONResponse(content=get_all_nodes_resp, status_code=code)

    # Create current Layout
    current_layout = _create_current_layout(get_all_nodes_resp.get("nodes"), desired_layout.get("targetNodeIDs"))

    # Get a list of available resources
    code, get_available_resources_resp = GetAvailableResourcesAPI(
        logger, config.configuration_manager, config.server_connection
    ).execute()

    if code != HTTPStatus.OK.value:
        return JSONResponse(content=get_available_resources_resp, status_code=code)

    # Set boundDevices info
    desired_layout["desiredLayout"]["boundDevices"] = _create_bound_devices(
        get_available_resources_resp, get_all_nodes_resp.get("nodes"), desired_layout.get("targetNodeIDs")
    )

    code, resp = MigrationAPI(
        logger,
        config.migration_procedure,
        config.server_connection,
        {
            "currentLayout": current_layout["currentLayout"],
            "desiredLayout": desired_layout["desiredLayout"],
        },
    ).execute()
    if code != HTTPStatus.OK.value:
        return JSONResponse(content=resp, status_code=code)

    logger.info(f"End migration_generate api. status_code:{HTTPStatus.OK.value}")
    return JSONResponse(status_code=HTTPStatus.OK.value, content={"procedures": resp})


def _create_current_layout(nodes: List, node_ids: List) -> dict:
    """Create a layout for generating migration procedures

    Args:
        nodes (list): Current node list
        node_ids: (list): Get nodes by id

    Returns:
        dict: Created layout
    """
    current_layout = {"currentLayout": {"nodes": []}}
    filtered_nodes = []

    if node_ids is None:
        filtered_nodes = nodes
    elif node_ids == []:
        # return initilize current layout
        pass
    else:
        # Extract all valid IDs from the input nodes
        valid_ids = {node.get("id") for node in nodes}

        # Find invalid IDs in node_ids
        invalid_ids = [node_id for node_id in node_ids if node_id not in valid_ids]

        # Raise exception if invalid IDs are found
        if invalid_ids:
            raise IdNotFoundException(invalid_ids)
        # Filter nodes based on node_ids
        filtered_nodes = [node for node in nodes if node.get("id") in node_ids]

    for node in filtered_nodes:
        current_layout.get("currentLayout").get("nodes").append(_create_device_struct(node.get("resources")))
    return current_layout


def _create_device_struct(resources: List) -> dict:
    """Create device configuration.

    Args:
        resources (List): List of node devices

    Returns:
        dict: device configuration
    """
    device_struct = {"device": {}}
    for resource in resources:
        device = resource.get("device")
        device_type = device.get("type").lower()
        # If there are multiple identical devices on one node, add them to the deviceIDs array.
        if device_type in device_struct["device"].keys():  # pylint: disable=C0201
            device_struct["device"][device_type]["deviceIDs"].append(device.get("deviceID"))
        else:
            device_struct["device"][device_type] = {"deviceIDs": [device.get("deviceID")]}
    return device_struct


def _create_bound_devices(response: dict, nodes: List, target_node_ids: list) -> dict:
    """Create a layout for bound devices

    Args:
        response (dict): Available Resources Response
        node_ids (list): Get nodes by id
        target_node_ids (list): Specified target node id list of args

    Returns:
        dict: Created boundDevices dict
    """
    dict_id_to_type = _set_dict_id_to_type(response)

    # Get a list of devices that cannot be used in the design
    unavailable_resources = _set_unavailable_resources(nodes, target_node_ids)

    device_pairs = []  # A list used to eliminate duplicate data where only the src and dest are swapped
    bound_devices = {}  # Bound device information for migration procedures
    for resource_data in response["resources"]:
        # Skip if there are no constraints or if the node not subject to design changes uses the device
        if (
            resource_data.get("device", {}).get("constraints") is None
            or resource_data["device"]["deviceID"] in unavailable_resources
        ):
            continue
        device_pairs, bound_devices = _set_bound_devices_info(
            dict_id_to_type, resource_data, device_pairs, bound_devices
        )

    return bound_devices


def _set_dict_id_to_type(response: dict) -> dict:
    """Set dict_id_to_type for create bound devices info

    Args:
        response (dict): Available Resources Response

    Returns:
        dict: dict_id_to_type for created boundDevices info
    """
    dict_id_to_type = {}
    for resource_data in response["resources"]:
        device_id = resource_data["device"]["deviceID"]
        device_type = resource_data["device"]["type"]
        dict_id_to_type[device_id] = device_type
    return dict_id_to_type


def _set_unavailable_resources(nodes: List, target_node_ids: list) -> dict:
    """Set unavailable_resources for create bound devices info

    Args:
        node_ids (list): Get nodes by id
        target_node_ids (list): Specified target node id list of args

    Returns:
        dict: unavailable_resources for created boundDevices info
    """
    all_node_ids = []
    for node in nodes:
        all_node_ids.append(node["id"])

    # Identification of node IDs not subject to design changes
    unchanged_node_ids = []
    if target_node_ids is not None:
        unchanged_node_ids = list(set(all_node_ids) - set(target_node_ids))

    # Get a list of devices that cannot be used in the design
    unavailable_resources = _extract_unavailable_resources(nodes, unchanged_node_ids)

    return unavailable_resources


def _extract_unavailable_resources(node_data, unchanged_node_ids):
    """Obtain a list of devices used by nodes that are not subject to design changes

    Args:
        node_data (list[dict]): nodes info
        unchanged_node_ids (list[str]): List of node IDs not subject to design changes

    Returns:
        list[str]: List of device IDs for devices that cannot be used in design
    """
    unavailable_resources = []
    for node in node_data:
        if node["id"] in unchanged_node_ids:
            for resource in node["resources"]:
                unavailable_resources.append(resource["device"]["deviceID"])
    return unavailable_resources


def _set_bound_devices_info(
    dict_id_to_type: dict, resource_data: dict, device_pairs: list, bound_devices: dict
) -> Tuple[list, dict]:
    """Set bound devices info

    Args:
        dict_id_to_type (dict): Combination of deviceID and type
        resource_data (dict): Resource data
        device_pairs (list): A list used to eliminate duplicate data where only the src and dest are swapped
        bound_devices (dict): Bound device information for migration procedures

    Returns:
        device_pairs (list): A list used to eliminate duplicate data where only the src and dest are swapped
        bound_devices (dict): Bound device information for migration procedures
    """
    connection_constraints = resource_data["device"]["constraints"]
    src_device_id = resource_data["device"]["deviceID"]
    for constraint in connection_constraints.get("nonRemovableDevices", []):
        if (dest_device_id := constraint.get("deviceID")) and {src_device_id, dest_device_id} not in device_pairs:
            if dict_id_to_type.get(dest_device_id).lower() == "cpu":
                # Swap so that the CPU becomes the src
                src_device_id, dest_device_id = dest_device_id, src_device_id
            device_pairs.append({src_device_id, dest_device_id})
            if dict_id_to_type.get(src_device_id).lower() == "cpu":
                dest_device_type = dict_id_to_type.get(dest_device_id)
                bound_devices.setdefault(src_device_id, {}).setdefault(dest_device_type, [])
                bound_devices[src_device_id][dest_device_type].append(dest_device_id)

    return device_pairs, bound_devices


def _resume_layoutapply(
    applyID: str,
    config: LayoutApplyConfig,
    logger: Logger,
):  # pylint: disable=C0103
    """exec cancel layoutapply
    Args:
        applyID: layout applyID
        config: layoutapply config
        logger: logger

    Returns:
        JSONResponse: status_code, exec result
    """
    logger.info(f"Start resume api. args.applyID:{applyID}")
    database = _get_db_connection(logger)
    proc_result = database.proc_resume(applyID)
    status, rollback_status = proc_result.get("status"), proc_result.get("rollbackStatus")
    # Adjustment of response content according to the resumption execution results
    if status == Result.SUSPENDED:
        input_procedure = {"procedures": proc_result.get("resumeProcedures")}
        response_code, return_data, proc_id = _exec_subprocess(logger, input_procedure, config, applyID, Action.RESUME)
        if response_code is not None:
            return JSONResponse(status_code=response_code, content=return_data)
        database.update_subprocess(proc_id, applyID)
        return_data = {"status": Result.IN_PROGRESS}
        response_code = HTTPStatus.ACCEPTED.value
    elif rollback_status == Result.SUSPENDED:
        input_procedure = {"procedures": proc_result.get("resumeProcedures")}
        response_code, return_data, proc_id = _exec_subprocess(
            logger, input_procedure, config, applyID, Action.ROLLBACK_RESUME
        )
        if response_code is not None:
            return JSONResponse(status_code=response_code, content=return_data)
        database.update_subprocess(proc_id, applyID)
        return_data = {"status": status, "rollbackStatus": Result.IN_PROGRESS}
        response_code = HTTPStatus.ACCEPTED.value
    elif status == Result.CANCELED and rollback_status in [
        Result.COMPLETED,
        Result.FAILED,
    ]:
        return_data = {"status": status, "rollbackStatus": rollback_status}
        response_code = HTTPStatus.OK.value
    elif status in [Result.COMPLETED, Result.FAILED] or (status == Result.CANCELED and rollback_status is None):
        return_data = {"status": status}
        response_code = HTTPStatus.OK.value
    else:
        # An error occurs if the status is IN_PROGRESS or CANCELING,
        # or if the status is CANCELED and the rollback status is IN_PROGRESS.
        msg = AlreadyExecuteException().message
        return_data = {"code": "E40022", "message": msg}
        logger.error(f"[E40022]{msg}")
        response_code = AlreadyExecuteException().status_code

    logger.info(f"End resume api. status_code:{response_code}")
    return JSONResponse(status_code=response_code, content=return_data)


def _exec_subprocess(
    logger: Logger,
    procedure: dict,
    config: LayoutApplyConfig,
    applyID: str,
    action: str,
):  # pylint: disable=C0103
    """execute subprocess

    Args:
        logger (Logger): logger
        procedure (dict): Migration procedure
        config (LayoutApplyConfig): Configuration object.
        applyID (str): layoutapply ID
        action (str): action type. apply or resume. If not specified, apply action.
    Returns:
        response_code (int): response status_code
        return_data (dict): response content
        proc.pid (str): process id
    """
    response_code, return_data = None, None
    # Execute subprocess asynchronously.
    try:
        proc = Process(target=run, args=(procedure, config, applyID, action))
        proc.start()
    except Exception as err:  # pylint: disable=W0703
        exc = FailedStartSubprocessException(err)
        response_code = exc.status_code
        return_data = {"code": "E40026", "message": exc.message}
        logger.error(f"[E40026]{exc.message}")
    return response_code, return_data, proc.pid


@app.exception_handler(RequestValidationError)
async def pydantic_handler(request: Request, exc: RequestValidationError):  # pylint:disable=W0613
    """Custom error handler. Call when a validation error occurs with Pydantic and return a response"""
    # If the request is for migration procedure generation, the code changes, so it is being determined.
    code = "E50001" if request.url.path.endswith("migration-procedures") else "E40001"
    cus_exc = RequestError(exc)
    return JSONResponse(
        content={"code": code, "message": cus_exc.message},
        status_code=cus_exc.status_code,
    )


@app.exception_handler(ValidationError)
async def jsonschema_handler(request: Request, exc: ValidationError):  # pylint:disable=W0613
    """Custom error handler. Call and return a response in case of a validation error by the JSON schema"""
    # If the request is for migration procedure generation, the code changes, so it is being determined.
    code = "E50001" if request.url.path.endswith("migration-procedures") else "E40001"
    cus_exc = JsonSchemaError(exc)
    return JSONResponse(
        content={"code": code, "message": cus_exc.message},
        status_code=cus_exc.status_code,
    )


@app.exception_handler(psycopg2.OperationalError)
async def operational_error_handler(_, exc: psycopg2.OperationalError):  # pylint:disable=W0613
    """Custom error handler. Return a response in case of a DB connection error."""
    cus_exc = OperationalError(exc)
    return_data = {
        "code": "E40018",
        "message": cus_exc.message,
    }
    return JSONResponse(status_code=cus_exc.status_code, content=return_data)


@app.exception_handler(psycopg2.ProgrammingError)
async def programming_error_handler(_, exc: psycopg2.ProgrammingError):  # pylint:disable=W0613
    """Custom error handler. Return a response when a DB connection query fails."""
    cus_exc = ProgrammingError(exc)
    return_data = {"code": "E40019", "message": cus_exc.message}
    return JSONResponse(status_code=cus_exc.status_code, content=return_data)


@app.exception_handler(IdNotFoundException)
async def id_not_found_handler(request: Request, exc: IdNotFoundException):  # pylint:disable=W0613
    """Custom error handler. Return a response when a non-existent ID is specified."""
    code = "E50010" if request.url.path.endswith("migration-procedures") else "E40020"
    return_data = {
        "code": code,
        "message": exc.message,
    }
    return JSONResponse(status_code=exc.status_code, content=return_data)


@app.exception_handler(SettingFileLoadException)
async def setting_file_load_failed_handler(request: Request, exc: SettingFileLoadException):  # pylint:disable=W0613
    """Custom error handler. Return a response for a configuration file loading error."""
    # If the request is for migration procedure generation, the code changes, so it is being determined.
    code = "E50002" if request.url.path.endswith("migration-procedures") else "E40002"
    return_data = {
        "code": code,
        "message": exc.message,
    }
    return JSONResponse(status_code=exc.status_code, content=return_data)


@app.exception_handler(SecretInfoGetException)
async def secret_file_load_failed_handler(request: Request, exc: SecretInfoGetException):  # pylint:disable=W0613
    """Custom error handler. Return a response for a secret file loading error."""
    # If the request is for migration procedure generation, the code changes, so it is being determined.
    code = "E50008" if request.url.path.endswith("migration-procedures") else "E40030"
    return_data = {
        "code": code,
        "message": exc.message,
    }
    return JSONResponse(status_code=exc.status_code, content=return_data)


@app.exception_handler(LoggerLoadException)
async def logger_load_failed_handler(request: Request, exc: LoggerLoadException):  # pylint:disable=W0613
    """Custom error handler. Return a response for an error when loading logger information."""
    # If the request is for migration procedure generation, the code changes, so it is being determined.
    code = "E50009" if request.url.path.endswith("migration-procedures") else "E40031"
    return_data = {
        "code": code,
        "message": exc.message,
    }
    return JSONResponse(status_code=exc.status_code, content=return_data)


@app.exception_handler(MultipleInstanceError)
async def multiple_instance_exception_handler(_: Request, exc: MultipleInstanceError):
    """Returning a response if a custom error handler fails to MultipleInstanceError"""
    return_data = {"code": "E40010", "message": exc.message}
    return JSONResponse(status_code=exc.status_code, content=return_data)


@app.exception_handler(SuspendedDataExistException)
async def suspended_data_exist_exception_handler(_: Request, exc: SuspendedDataExistException):
    """Returning a response if a custom error handler fails to SuspendedDataExistException"""
    return_data = {"code": "E40027", "message": exc.message}
    return JSONResponse(status_code=exc.status_code, content=return_data)


def main():  # pragma: no cover
    """entry point"""
    try:
        config = LayoutApplyConfig()
    except (SettingFileLoadException, ValidationError) as error:
        exc = SettingFileLoadException(error.message)
        print(
            exc.message,
            file=sys.stderr,
        )
        sys.exit(exc.exit_code)
    except SecretInfoGetException as error:
        exc = SecretInfoGetException(error.message)
        print(
            exc.message,
            file=sys.stderr,
        )
        sys.exit(exc.exit_code)

    try:
        uvicorn.run(
            "layoutapply.server:app",
            host=config.layout_apply["host"],
            port=config.layout_apply["port"],
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()  # pragma: no cover
