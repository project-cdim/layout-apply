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
"""Test for setting migration_procedure_generator"""

import copy

import pytest

from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.setting import LayoutApplyConfig
from tests.layoutapply.conftest import BASE_CONFIG, LOG_BASE_CONFIG


class TestLayoutApplyConfigMigrationProcedure:
    """Tests for migration procedure generator settings."""

    @pytest.mark.parametrize(
        "update_confg",
        [
            # Normal value
            {
                "migration_procedure_generator": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "cdim/api/v1",
                    "timeout": 30,
                },
            },
            # Boundary value (minimum value)
            {
                "migration_procedure_generator": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "cdim/api/v1",
                    "timeout": 1,
                },
            },
            # Boundary value (maximum value)
            {
                "migration_procedure_generator": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "cdim/api/v1",
                    "timeout": 600,
                },
            },
        ],
    )
    def test_setting_success_when_migration_step_generation_api_config_normal(self, mocker, update_confg):
        """Test setting success when migration step generation API config is normal."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["migration_procedure_generator"]
        config["migration_procedure_generator"] = update_confg["migration_procedure_generator"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        migration_procedure_generator_conf = LayoutApplyConfig().migration_procedure
        assert migration_procedure_generator_conf.get("host") == "localhost"
        assert migration_procedure_generator_conf.get("port") == 48889
        assert migration_procedure_generator_conf.get("uri") == "cdim/api/v1"
        assert (
            migration_procedure_generator_conf.get("timeout")
            == update_confg["migration_procedure_generator"]["timeout"]
        )

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host is no existent
            {
                "migration_procedure_generator": {
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": 10,
                },
            },
            # port is no existent
            {
                "migration_procedure_generator": {
                    "host": "localhost",
                    "uri": "api/v1",
                    "timeout": 10,
                },
            },
            # uri is no existent
            {
                "migration_procedure_generator": {
                    "host": "localhost",
                    "port": 48889,
                    "timeout": 10,
                },
            },
            # host is type error
            {
                "migration_procedure_generator": {
                    "host": 127001,
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": 10,
                },
            },
            # port is type error
            {
                "migration_procedure_generator": {
                    "host": "localhost",
                    "port": "port",
                    "uri": "api/v1",
                    "timeout": 10,
                },
            },
            # uri is type error
            {
                "migration_procedure_generator": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": 654321,
                    "timeout": 10,
                },
            },
            # timeout max +1
            {
                "migration_procedure_generator": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": 601,
                },
            },
            # timeout min -1
            {
                "migration_procedure_generator": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": 0,
                },
            },
            # timeout is minus
            {
                "migration_procedure_generator": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": -1,
                },
            },
            # timeout is type error
            {
                "migration_procedure_generator": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": "timeout",
                },
            },
        ],
    )
    def test_setting_failure_when_invalid_migration_step_generation_api_config(self, mocker, update_confg):
        """Test setting failure when migration step generation API config is invalid."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["migration_procedure_generator"]
        config["migration_procedure_generator"] = update_confg["migration_procedure_generator"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        with pytest.raises(SettingFileLoadException):
            assert LayoutApplyConfig().migration_procedure is not None
