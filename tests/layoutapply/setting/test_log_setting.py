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
from layoutapply.setting import LayoutApplyLogConfig
from tests.layoutapply.conftest import LOG_BASE_CONFIG


class TestLayoutApplyLogConfig:
    """Test class for LayoutApplyLogConfig."""

    @pytest.mark.parametrize(
        "update_confg1",
        [
            {
                "handlers": {
                    "file": {
                        "level": "INFO",
                    }
                }
            },
            {
                "handlers": {
                    "file": {
                        "level": "ERROR",
                    }
                }
            },
            {
                "handlers": {
                    "file": {
                        "level": "WARN",
                    }
                }
            },
            {
                "handlers": {
                    "file": {
                        "level": "CRITICAL",
                    }
                }
            },
            {
                "handlers": {
                    "file": {
                        "level": "DEBUG",
                    }
                }
            },
        ],
    )
    @pytest.mark.parametrize(
        "update_confg2",
        [
            {
                "handlers": {
                    "console": {
                        "level": "INFO",
                    },
                }
            },
            {
                "handlers": {
                    "console": {
                        "level": "ERROR",
                    },
                }
            },
            {
                "handlers": {
                    "console": {
                        "level": "WARN",
                    },
                },
            },
            {
                "handlers": {
                    "console": {
                        "level": "CRITICAL",
                    },
                }
            },
            {
                "handlers": {
                    "console": {
                        "level": "DEBUG",
                    },
                }
            },
        ],
    )
    @pytest.mark.parametrize(
        "update_confg3",
        [
            {
                "root": {
                    "level": "INFO",
                },
            },
            {
                "root": {
                    "level": "ERROR",
                },
            },
            {
                "root": {
                    "level": "WARN",
                },
            },
            {
                "root": {
                    "level": "DEBUG",
                },
            },
            {
                "root": {
                    "level": "CRITICAL",
                },
            },
        ],
    )
    def test_setting_success_when_log_config_normal(self, mocker, update_confg1, update_confg2, update_confg3):
        """Test setting success when log config is normal."""
        config = copy.deepcopy(LOG_BASE_CONFIG)
        config["handlers"]["file"]["level"] = update_confg1["handlers"]["file"]["level"]
        config["handlers"]["console"]["level"] = update_confg2["handlers"]["console"]["level"]
        config["root"]["level"] = update_confg3["root"]["level"]
        mocker.patch("yaml.safe_load").return_value = config
        _ = LayoutApplyLogConfig().log_config

    def test_setting_default_set_when_log_dir_missing(self, mocker):
        """Test setting default set when log directory is missing."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["filename"] = ""
        mocker.patch("yaml.safe_load").return_value = base_config
        _ = LayoutApplyLogConfig().log_config

    def test_setting_default_set_when_log_dir_file_not_found(self, mocker):
        """Test setting default set when log directory file is not found."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["filename"] = "/test/test/test.log"
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException) as exc_info:
            _ = LayoutApplyLogConfig().log_config

        assert "Directory not found at path" in str(exc_info.value)

    @pytest.mark.parametrize(
        "update_confg",
        [
            # level is type mismatch
            {
                "version": "aaa",
            },
        ],
    )
    def test_setting_failure_when_invalid_log_version(self, mocker, update_confg):
        """Test setting failure when log version is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["version"] = update_confg["version"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException) as exc_info:
            _ = LayoutApplyLogConfig().log_config

        assert "'aaa' is not of type 'integer'" in str(exc_info.value)

    @pytest.mark.parametrize(
        "update_confg",
        [
            # level is type mismatch
            {
                "formatters": {
                    "standard": {
                        "format": 1,
                    }
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_log_formatters_standard_format(self, mocker, update_confg):
        """Test setting failure when log formatters standard format is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["formatters"]["standard"]["format"] = update_confg["formatters"]["standard"]["format"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException) as exc_info:
            _ = LayoutApplyLogConfig().log_config

        assert "1 is not of type 'string'" in str(exc_info.value)

    @pytest.mark.parametrize(
        "update_confg",
        [
            # level is type mismatch
            {
                "formatters": {
                    "standard": {
                        "datefmt": 1,
                    }
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_log_formatters_standard_datefmt(self, mocker, update_confg):
        """Test setting failure when log formatters standard datefmt is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["formatters"]["standard"]["datefmt"] = update_confg["formatters"]["standard"]["datefmt"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException) as exc_info:
            _ = LayoutApplyLogConfig().log_config

        assert "1 is not of type 'string'" in str(exc_info.value)

    @pytest.mark.parametrize(
        "update_confg",
        [
            # level is unexpected string
            {
                "handlers": {
                    "file": {
                        "level": "INFORMATION",
                    }
                }
            },
            # level is type mismatch
            {
                "handlers": {
                    "file": {
                        "level": 1,
                    }
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_log_handlers_file_level(self, mocker, update_confg):
        """Test setting failure when log handlers file level is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["level"] = update_confg["handlers"]["file"]["level"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException):
            _ = LayoutApplyLogConfig().log_config

    @pytest.mark.parametrize(
        "update_confg",
        [
            # filename is type mismatch
            {
                "handlers": {
                    "file": {
                        "filename": 1,
                    }
                }
            },
            # filename is no existent
            {
                "handlers": {
                    "file": {
                        "filename": "./unknown/direcotry",
                    }
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_log_handlers_file_filename(self, mocker, update_confg):
        """Test setting failure when log handlers file filename is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["filename"] = update_confg["handlers"]["file"]["filename"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException):
            _ = LayoutApplyLogConfig().log_config

    @pytest.mark.parametrize(
        "update_confg",
        [
            # formatter is type mismatch
            {
                "handlers": {
                    "file": {
                        "formatter": 1,
                    }
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_log_handlers_file_formatter(self, mocker, update_confg):
        """Test setting failure when log handlers file formatter is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["formatter"] = update_confg["handlers"]["file"]["formatter"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException):
            _ = LayoutApplyLogConfig().log_config

    @pytest.mark.parametrize(
        "update_confg",
        [
            # maxBytes is type mismatch
            {
                "handlers": {
                    "file": {
                        "maxBytes": "1",
                    }
                }
            }
        ],
    )
    def test_setting_failure_when_invalid_log_handlers_file_maxBytes(
        self, mocker, update_confg
    ):  # pylint: disable=invalid-name
        """Test setting failure when log handlers file maxBytes is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["maxBytes"] = update_confg["handlers"]["file"]["maxBytes"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException):
            _ = LayoutApplyLogConfig().log_config

    @pytest.mark.parametrize(
        "update_confg",
        [
            # backupCount is type mismatch
            {
                "handlers": {
                    "file": {
                        "backupCount": "1",
                    }
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_log_handlers_file_backupCount(
        self, mocker, update_confg
    ):  # pylint: disable=invalid-name
        """Test setting failure when log handlers file backupCount is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["backupCount"] = update_confg["handlers"]["file"]["backupCount"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException):
            _ = LayoutApplyLogConfig().log_config

    @pytest.mark.parametrize(
        "update_confg",
        [
            # encoding is type mismatch
            {
                "handlers": {
                    "file": {
                        "encoding": 1,
                    }
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_log_handlers_file_encoding(self, mocker, update_confg):
        """Test setting failure when log handlers file encoding is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["encoding"] = update_confg["handlers"]["file"]["encoding"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException):
            _ = LayoutApplyLogConfig().log_config

    @pytest.mark.parametrize(
        "update_confg",
        [
            # level is unexpected string
            {
                "handlers": {
                    "console": {
                        "level": "INFORMATION",
                    }
                }
            },
            # level is type mismatch
            {
                "handlers": {
                    "console": {
                        "level": 1,
                    }
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_log_handlers_console_level(self, mocker, update_confg):
        """Test setting failure when log handlers console level is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["console"]["level"] = update_confg["handlers"]["console"]["level"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException):
            _ = LayoutApplyLogConfig().log_config

    @pytest.mark.parametrize(
        "update_confg",
        [
            # level is type mismatch
            {
                "handlers": {
                    "console": {
                        "class": 1,
                    }
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_log_handlers_console_class(self, mocker, update_confg):
        """Test setting failure when log handlers console class is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["console"]["class"] = update_confg["handlers"]["console"]["class"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException):
            _ = LayoutApplyLogConfig().log_config

    @pytest.mark.parametrize(
        "update_confg",
        [
            # level is type mismatch
            {
                "handlers": {
                    "console": {
                        "formatter": 1,
                    }
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_log_handlers_console_formatter(self, mocker, update_confg):
        """Test setting failure when log handlers console formatter is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["console"]["formatter"] = update_confg["handlers"]["console"]["formatter"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException):
            _ = LayoutApplyLogConfig().log_config

    @pytest.mark.parametrize(
        "update_confg",
        [
            # level is type mismatch
            {
                "handlers": {
                    "console": {
                        "stream": 1,
                    }
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_log_handlers_console_stream(self, mocker, update_confg):
        """Test setting failure when log handlers console stream is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["console"]["stream"] = update_confg["handlers"]["console"]["stream"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException):
            _ = LayoutApplyLogConfig().log_config

    @pytest.mark.parametrize(
        "update_confg",
        [
            # level is unexpected string
            {
                "root": {
                    "level": "INFORMATION",
                }
            },
            # level is type mismatch
            {
                "root": {
                    "level": 1,
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_log_root_level(self, mocker, update_confg):
        """Test setting failure when log root level is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["root"]["level"] = update_confg["root"]["level"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException):
            _ = LayoutApplyLogConfig().log_config

    @pytest.mark.parametrize(
        "update_confg",
        [
            # handlers is type mismatch
            {
                "root": {
                    "handlers": "INFORMATION",
                }
            },
            # handlers is type mismatch
            {
                "root": {
                    "handlers": 1,
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_log_root_handlers(self, mocker, update_confg):
        """Test setting failure when log root handlers is invalid."""
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["root"]["handlers"] = update_confg["root"]["handlers"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(SettingFileLoadException):
            _ = LayoutApplyLogConfig().log_config
