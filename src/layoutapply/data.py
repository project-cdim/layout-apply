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
"""Data class for migration steps"""

# pylint: disable=invalid-name
from dataclasses import dataclass, field
from typing import Any

from layoutapply.const import Operation


@dataclass
class Procedure:
    """Migration Procedure"""

    operationID: int
    operation: str
    dependencies: list
    targetDeviceID: str
    targetCPUID: str = field(default=None)

    @classmethod
    def init_from_dict(cls, procedure_dict):
        """Generate an instance of the Procedure class by reading data
        from a dict type object of migration procedure

        Args:
            procedure_dict (dict): Migration procedure dict type object

        Returns:
            Procedure: Return a Procedure instance
        """
        return cls(**procedure_dict)


def procedure_dict_factory(items: list[tuple[str, Any]]) -> dict[str, Any]:
    """Dict factory method of the Procedure class.
    If the operation is boot or shutdown, do not include targetCPUID in the Dict

    Args:
        items (list[tuple[str, Any]]): Details items.

    Returns:
        dict[str, Any]: Details dict
    """
    adict = {}
    for key, value in items:
        adict[key] = value
    if adict["operation"] in (Operation.POWEROFF, Operation.POWERON):
        del adict["targetCPUID"]
    return adict


def get_procedure_list(procedure: dict) -> list[Procedure]:
    """Return the migration steps as a list of dataclasses for easy access

    Args:
        procedure (dict): Migration procedures

    Returns:
        list: List of migration procedures
    """

    return [Procedure.init_from_dict(i) for i in procedure.get("procedures")]


@dataclass
class Details:
    """Implementation details of the migration procedure"""

    operationID: int = ""
    status: str = ""
    uri: str = ""
    method: str = ""
    statusCode: int = ""
    queryParameter: any = ""
    requestBody: any = ""
    responseBody: any = ""
    isOSBoot: any = ""
    getInformation: any = ""
    startedAt: str = ""
    endedAt: str = ""


@dataclass
class IsOsBoot:
    """Details of OS startup verification"""

    uri: str = ""
    method: str = ""
    statusCode: int = ""
    queryParameter: any = ""
    responseBody: any = ""


def details_dict_factory(items: list[tuple[str, Any]]) -> dict[str, Any]:
    """Dict factory method of the Details class.
    If the value is empty, do not include it in the Dict

    Args:
        items (list[tuple[str, Any]]): Details items.

    Returns:
        dict[str, Any]: Details dict
    """
    adict = {}
    for key, value in items:
        if value != "":
            adict[key] = value

    return adict
