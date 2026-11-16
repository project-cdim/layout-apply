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
"""Layoutapply util package"""

import secrets
import string

from layoutapply.const import Result


def create_randomname(length: int) -> str:
    """Generate a random string

    Args:
        length (int): Length of the string

    Returns:
        str: Generated string
    """
    randlst = [secrets.choice(string.hexdigits) for i in range(length)]
    return "".join(randlst).lower()


def create_applystatus_response(applystatus: dict) -> dict:
    """create get_appplystatus response

    Args:
        applystatus (dict): get_appplystatus result

    Returns:
        dict: get_appplystatus response
    """

    response_dict = applystatus

    # Adjusting response content based on status
    if applystatus.get("status") is not None and applystatus.get("status") == Result.IN_PROGRESS:
        response_dict = {
            "applyID": applystatus.get("applyID"),
            "status": applystatus.get("status"),
            "startedAt": applystatus.get("startedAt"),
        }
        if applystatus.get("resumedAt") is not None:
            response_dict["resumedAt"] = applystatus.get("resumedAt")
    elif applystatus.get("status") is not None and applystatus.get("status") == Result.CANCELING:
        response_dict = {
            "applyID": applystatus.get("applyID"),
            "status": applystatus.get("status"),
            "startedAt": applystatus.get("startedAt"),
            "canceledAt": applystatus.get("canceledAt"),
            "executeRollback": applystatus.get("executeRollback"),
        }
        if applystatus.get("executeRollback") is True and applystatus.get("rollbackStartedAt") is not None:
            response_dict["rollbackStartedAt"] = applystatus.get("rollbackStartedAt")
        if applystatus.get("resumedAt") is not None:
            response_dict["resumedAt"] = applystatus.get("resumedAt")

    return response_dict


def set_date_dict(
    started_at_since: str,
    started_at_until: str,
    ended_at_since: str,
    ended_at_until: str,
) -> dict:
    """Set dict of spicified date

    Args:
        started_at_since (str): started_at_since of args
        started_at_until (str): started_at_until of args
        ended_at_since (str): ended_at_since of args
        ended_at_until (str): ended_at_until of args

    Returns:
        dict: Set dict
    """
    date_dict = {}
    key_name_list = [
        "startedat_since",
        "startedat_until",
        "endedat_since",
        "endedat_until",
    ]
    value_list = [started_at_since, started_at_until, ended_at_since, ended_at_until]
    for key, value in zip(key_name_list, value_list):
        if value is not None:
            date_dict[key] = value
    return date_dict
