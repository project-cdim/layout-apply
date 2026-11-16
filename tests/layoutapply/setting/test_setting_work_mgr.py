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
"""Test for setting"""

import copy

import pytest

from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.setting import LayoutApplyConfig
from tests.layoutapply.conftest import BASE_CONFIG, LOG_BASE_CONFIG


class TestLayoutApplyConfigWorkflowManager:
    """Tests for features and workflow_manager dependency/validation."""

    @pytest.mark.parametrize(
        "update_config",
        [
            {
                "features": {
                    "workflow_managerr": True,
                },
            },
            {},
        ],
    )
    def test_setting_config_default_value_applied_when_features_config(self, mocker, update_config):
        """Test setting default values are applied correctly when features config is provided."""
        config = copy.deepcopy(BASE_CONFIG)
        if "features" in update_config:
            config["features"] = update_config["features"]
        else:
            del config["features"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        features_conf = LayoutApplyConfig().features
        assert features_conf.get("workflow_manager") is False

    @pytest.mark.parametrize(
        "false_pattern",
        ["no_features", "no_features.workflow_manager", "specify_False"],
    )
    def test_setting_success_when_features_workflow_manager_false_pattern_without_workflow_manager_config(
        self, mocker, false_pattern
    ):
        """Test setting success when features
        workflow manager is set to a false pattern without workflow manager config."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["workflow_manager"]
        if false_pattern == "no_features":
            del config["features"]
        elif false_pattern == "no_features.workflow_manager":
            del config["features"]["workflow_manager"]
        else:
            config["features"]["workflow_manager"] = False
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")

        features_conf = LayoutApplyConfig().features
        assert features_conf.get("workflow_manager") is False

    def test_setting_failure_when_features_workflow_manager_true_without_workflow_manager_config(self, mocker):
        """Test setting failure when features workflow manager is set to True without workflow manager config."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["workflow_manager"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        with pytest.raises(SettingFileLoadException):
            assert LayoutApplyConfig().features is not None

    @pytest.mark.parametrize(
        "update_confg",
        [
            # workflow_manager is no existent
            "",
            # host is no existent
            {
                "workflow_manager": {
                    "port": 48889,
                    "uri": "api/v1",
                },
            },
            # port is no existent
            {
                "workflow_manager": {
                    "host": "localhost",
                    "uri": "api/v1",
                },
            },
            # uri is no existent
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                },
            },
            # host is type error
            {
                "workflow_manager": {
                    "host": 127001,
                    "port": 48889,
                    "uri": "api/v1",
                },
            },
            # port is type error
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": "port",
                    "uri": "api/v1",
                },
            },
            # uri is type error
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": 654321,
                },
            },
            # interval max +1
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "extended-procedure": {
                        "retry": {
                            "default": {"interval": 61, "max_count": 5},
                        },
                    },
                },
            },
            # interval min -1
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "extended-procedure": {
                        "retry": {
                            "default": {"interval": -1, "max_count": 5},
                        },
                    },
                },
            },
            # interval is type error
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "extended-procedure": {
                        "retry": {
                            "default": {"interval": "interval", "max_count": 5},
                        },
                    },
                },
            },
            # max_count max +1
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "extended-procedure": {
                        "retry": {
                            "default": {"interval": 5, "max_count": 11},
                        },
                    },
                },
            },
            # max_count min -1
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "extended-procedure": {
                        "retry": {
                            "default": {"interval": 5, "max_count": 0},
                        },
                    },
                },
            },
            # max_count minus
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "extended-procedure": {
                        "retry": {
                            "default": {"interval": 5, "max_count": -1},
                        },
                    },
                },
            },
            # max_count is type error
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "extended-procedure": {
                        "retry": {
                            "default": {"interval": 5, "max_count": "max_count"},
                        },
                    },
                },
            },
            # polling.count max +1
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "extended-procedure": {
                        "polling": {"count": 241, "interval": 30},
                    },
                },
            },
            # polling.count min -1
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "extended-procedure": {
                        "polling": {"count": 0, "interval": 30},
                    },
                },
            },
            # polling.count minus
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "extended-procedure": {
                        "polling": {"count": -1, "interval": 30},
                    },
                },
            },
            # polling.count is type error
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "extended-procedure": {
                        "polling": {"count": "count", "interval": 30},
                    },
                },
            },
            # polling.interval max +1
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "extended-procedure": {
                        "polling": {"count": 60, "interval": 241},
                    },
                },
            },
            # polling.interval min -1
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "extended-procedure": {
                        "polling": {"count": 60, "interval": -1},
                    },
                },
            },
            # polling.interval is type error
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "extended-procedure": {
                        "polling": {"count": 60, "interval": "interval"},
                    },
                },
            },
            # timeout max +1
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": 601,
                },
            },
            # timeout min -1
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": 0,
                },
            },
            # timeout minus
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": -1,
                },
            },
            # timeout is type error
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": "timeout",
                },
            },
        ],
    )
    def test_setting_failure_when_invalid_workflow_manager_config(self, mocker, update_confg):
        """Test setting failure when the workflow manager config is invalid."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["workflow_manager"]
        if update_confg == "":
            pass
        else:
            config["workflow_manager"] = update_confg["workflow_manager"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        with pytest.raises((SettingFileLoadException, AttributeError)):
            assert LayoutApplyConfig().workflow_manager is not None

    @pytest.mark.parametrize(
        "update_confg",
        [
            # Normal value
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "cdim/api/v1",
                    "extended-procedure": {
                        "retry": {
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "polling": {
                            "count": 60,
                            "interval": 30,
                        },
                    },
                    "timeout": 30,
                },
            },
            # Boundary value (minimum)
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "cdim/api/v1",
                    "extended-procedure": {
                        "retry": {
                            "default": {
                                "interval": 0,
                                "max_count": 1,
                            },
                        },
                        "polling": {
                            "count": 1,
                            "interval": 0,
                        },
                    },
                    "timeout": 1,
                },
            },
            # Boundary value (maximum)
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "cdim/api/v1",
                    "extended-procedure": {
                        "retry": {
                            "default": {
                                "interval": 60,
                                "max_count": 10,
                            },
                        },
                        "polling": {
                            "count": 240,
                            "interval": 240,
                        },
                    },
                    "timeout": 600,
                },
            },
        ],
    )
    def test_setting_success_when_workflow_manager_config_normal(self, mocker, update_confg):
        """Test setting success when the workflow manager config is normal."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["workflow_manager"]
        config["workflow_manager"] = update_confg["workflow_manager"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        workflow_manager_conf = LayoutApplyConfig().workflow_manager
        expected_wf = update_confg["workflow_manager"]
        assert workflow_manager_conf.get("host") == "localhost"
        assert workflow_manager_conf.get("port") == 48889
        assert workflow_manager_conf.get("uri") == "cdim/api/v1"
        extended_procedure_conf = workflow_manager_conf.get("extended-procedure")
        expected_extended = expected_wf["extended-procedure"]
        assert (
            extended_procedure_conf.get("retry").get("default").get("interval")
            == expected_extended["retry"]["default"]["interval"]
        )
        assert (
            extended_procedure_conf.get("retry").get("default").get("max_count")
            == expected_extended["retry"]["default"]["max_count"]
        )
        assert extended_procedure_conf.get("polling").get("count") == expected_extended["polling"]["count"]
        assert extended_procedure_conf.get("polling").get("interval") == expected_extended["polling"]["interval"]
        assert workflow_manager_conf.get("timeout") == expected_wf["timeout"]

    @pytest.mark.parametrize(
        "update_confg",
        [
            # workflow_manager is no existent
            "",
            # host is no existent
            {
                "workflow_manager": {
                    "port": 48889,
                    "uri": "api/v1",
                },
            },
            # port is no existent
            {
                "workflow_manager": {
                    "host": "localhost",
                    "uri": "api/v1",
                },
            },
            # uri is no existent
            {
                "workflow_manager": {
                    "host": "localhost",
                    "port": 48889,
                },
            },
        ],
    )
    def test_setting_success_when_features_workflow_manager_false_without_workflow_manager_config_pattern(
        self, mocker, update_confg
    ):
        """Test setting success when features workflow manager is set to False without workflow manager config."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["features"]
        del config["workflow_manager"]
        if update_confg == "":
            pass
        else:
            config["workflow_manager"] = update_confg["workflow_manager"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")

        features_conf = LayoutApplyConfig().features
        assert features_conf.get("workflow_manager") is False
