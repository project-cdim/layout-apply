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
"""Model classes for the layout-apply API server."""

from typing import Optional

from jsonschema import validate
from pydantic import BaseModel, Field, field_validator

from layoutapply.schema import desiredLayout as desiredLayout_schema
from layoutapply.schema import procedure as procedure_schema
from layoutapply.schema import targetNodeID as targetNodeID_schema


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
