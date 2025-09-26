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
"""Test for setting"""

import copy
import logging
import os

import pytest
import requests
from requests.exceptions import ConnectionError, RequestException, Timeout

from layoutapply.custom_exceptions import SecretInfoGetException, SettingFileLoadException
from layoutapply.setting import LayoutApplyConfig, LayoutApplyLogConfig

BASE_CONFIG = {
    "layout_apply": {"host": "0.0.0.0", "port": 8003, "request": {}},
    "db": {
        "dbname": "layoutapply",
        "user": "user01",
        "password": "P@ssw0rd",
        "host": "localhost",
        "port": 5435,
    },
    "get_information": {
        "host": "localhost",
        "port": 48889,
        "uri": "api/v1",
        "specs": {
            "poweroff": {
                "polling": {
                    "count": 5,
                    "interval": 1,
                },
            },
            "connect": {
                "polling": {
                    "count": 5,
                    "interval": 1,
                },
            },
            "disconnect": {
                "polling": {
                    "count": 5,
                    "interval": 1,
                },
            },
            "timeout": 10,
        },
    },
    "workflow_manager": {
        "host": "0.0.0.0",
        "port": 8008,
        "uri": "cdim/api/v1",
        "extended-procedure": {
            "retry": {
                "default": {
                    "interval": 5,
                    "max_count": 5,
                },
            },
            "polling": {
                "count": 5,
                "interval": 5,
            },
        },
        "timeout": 30,
    },
    "hardware_control": {
        "host": "localhost",
        "port": 48889,
        "uri": "cdim/api/v1",
        "disconnect": {
            "retry": {
                "targets": [
                    {
                        "status_code": 503,
                        "code": "ER005BAS001",
                        "interval": 5,
                        "max_count": 5,
                    },
                ],
                "default": {
                    "interval": 5,
                    "max_count": 5,
                },
            },
            "timeout": 10,
        },
        "isosboot": {
            "polling": {
                "count": 5,
                "interval": 1,
                "targets": [
                    {
                        "status_code": 204,
                    },
                ],
                "skip": [
                    {"status_code": 400, "code": "EF003BAS010"},
                ],
            },
            "request": {"timeout": 2},
            "timeout": 10,
        },
    },
    "migration_procedure_generator": {
        "host": "localhost",
        "port": 48889,
        "uri": "cdim/api/v1",
        "timeout": 30,
    },
    "configuration_manager": {
        "host": "localhost",
        "port": 48889,
        "uri": "cdim/api/v1",
        "timeout": 30,
    },
    "message_broker": {
        "host": "localhost",
        "port": 3500,
        "pubsub": "layout_apply_apply",
        "topic": "layout_apply_apply.completed",
    },
}

LOG_BASE_CONFIG = {
    "version": 1,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(message)s",
            "datefmt": "%Y/%m/%d %H:%M:%S.%f",
        }
    },
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "standard",
            "filename": "/var/log/cdim/app_layout_apply.log",
            "maxBytes": 100000000,
            "backupCount": 72,
            "encoding": "utf-8",
        },
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["file"],
    },
}


class TestLayoutApplyLogConfig:
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
        config = copy.deepcopy(LOG_BASE_CONFIG)
        config["handlers"]["file"]["level"] = update_confg1["handlers"]["file"]["level"]
        config["handlers"]["console"]["level"] = update_confg2["handlers"]["console"]["level"]
        config["root"]["level"] = update_confg3["root"]["level"]
        mocker.patch("yaml.safe_load").return_value = config
        _ = LayoutApplyLogConfig().log_config

    def test_setting_default_set_when_log_dir_missing(self, mocker):
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["filename"] = ""
        mocker.patch("yaml.safe_load").return_value = base_config
        _ = LayoutApplyLogConfig().log_config

    def test_setting_default_set_when_log_dir_file_not_found(self, mocker):
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
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["level"] = update_confg["handlers"]["file"]["level"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(Exception):
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
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["filename"] = update_confg["handlers"]["file"]["filename"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(Exception):
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
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["formatter"] = update_confg["handlers"]["file"]["formatter"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(Exception):
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
    def test_setting_failure_when_invalid_log_handlers_file_maxBytes(self, mocker, update_confg):
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["maxBytes"] = update_confg["handlers"]["file"]["maxBytes"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(Exception):
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
    def test_setting_failure_when_invalid_log_handlers_file_backupCount(self, mocker, update_confg):
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["backupCount"] = update_confg["handlers"]["file"]["backupCount"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(Exception):
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
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["file"]["encoding"] = update_confg["handlers"]["file"]["encoding"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(Exception):
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
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["console"]["level"] = update_confg["handlers"]["console"]["level"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(Exception):
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
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["console"]["class"] = update_confg["handlers"]["console"]["class"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(Exception):
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
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["console"]["level"] = update_confg["handlers"]["console"]["level"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(Exception):
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
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["console"]["formatter"] = update_confg["handlers"]["console"]["formatter"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(Exception):
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
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["handlers"]["console"]["stream"] = update_confg["handlers"]["console"]["stream"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(Exception):
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
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["root"]["level"] = update_confg["root"]["level"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(Exception):
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
        base_config = copy.deepcopy(LOG_BASE_CONFIG)
        base_config["root"]["handlers"] = update_confg["root"]["handlers"]
        mocker.patch("yaml.safe_load").return_value = base_config
        with pytest.raises(Exception):
            _ = LayoutApplyLogConfig().log_config


class TestLayoutApplyConfig:

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host
            {
                "layout_apply": {"host": "0.0.0.0", "port": 8003, "request": {}},
            },
            {
                "layout_apply": {"host": "nec.test.com", "port": 8003, "request": {"max_workers": 1}},
            },
            # port
            {
                "layout_apply": {"host": "nec.test.com", "port": 0, "request": {"max_workers": 1}},
            },
        ],
    )
    def test_setting_success_when_server_config_normal(self, mocker, update_confg):
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["layout_apply"]
        config = {**base_config, **update_confg}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        LayoutApplyConfig().layout_apply

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host is type mismatch
            {
                "layout_apply": {"host": 0, "port": 8003, "request": {"max_workers": 2}},
            },
            # port is type mismatch
            {
                "layout_apply": {"host": "nec.test.com", "port": "0", "request": {"max_workers": 2}},
            },
            # request is type mismatch
            {
                "layout_apply": {"host": "nec.test.com", "port": "0", "request": 1},
            },
            # request.max_workers is type mismatch
            {
                "layout_apply": {"host": "nec.test.com", "port": "0", "request": {"max_workers": "2"}},
            },
            # request.max_workers over min
            {
                "layout_apply": {"host": "nec.test.com", "port": "0", "request": {"max_workers": 0}},
            },
            # request.max_workers over max
            {
                "layout_apply": {"host": "nec.test.com", "port": "0", "request": {"max_workers": 129}},
            },
            # empty
            {},
        ],
    )
    def test_setting_failure_when_invalid_server_config(self, mocker, update_confg):
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["layout_apply"]
        config = {**base_config, **update_confg}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        with pytest.raises(Exception):
            LayoutApplyConfig().layout_apply

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host
            {
                "hardware_control": {
                    "host": "127.0.0.1",
                    "port": 8888,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # port
            {
                "hardware_control": {
                    "host": "127.0.0.1",
                    "port": 0,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # uri is correct
            {
                "hardware_control": {
                    "host": "127.0.0.1",
                    "port": 8888,
                    "uri": "cdim/api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - interval min
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 0,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - interval max
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 60,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - max_count min
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 1,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - max_count max
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 10,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - targets
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS002",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # timeout - min
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 1,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # timeout - max
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 600,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
        ],
    )
    def test_setting_success_when_hardware_api_config_normal(self, mocker, update_confg):
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["hardware_control"]
        config = {**base_config, **update_confg}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        LayoutApplyConfig().hardware_control

    def test_setting_default_set_when_no_retry_setting(self, mocker):
        config = {
            "layout_apply": {"host": "0.0.0.0", "port": 8003, "request": {}},
            "db": {
                "dbname": "layoutapply",
                "user": "user01",
                "password": "P@ssw0rd",
                "host": "localhost",
                "port": 5435,
            },
            "hardware_control": {
                "host": "localhost",
                "port": 8888,
                "uri": "api/v1",
                "disconnect": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                            },
                        ],
                        "default": {
                            "interval": 5,
                            "max_count": 5,
                        },
                    },
                    "timeout": 10,
                },
                "connect": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 5,
                                "max_count": 5,
                            },
                        ],
                    },
                    "timeout": 10,
                },
                "poweroff": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "max_count": 5,
                            },
                        ],
                        "default": {
                            "interval": 5,
                        },
                    },
                    "timeout": 10,
                },
                "poweron": {
                    "retry": {
                        "default": {
                            "max_count": 5,
                        },
                    },
                },
                "isosboot": {
                    "polling": {
                        "count": 5,
                        "interval": 1,
                        "targets": [
                            {
                                "status_code": 204,
                            },
                        ],
                        "skip": [
                            {"status_code": 400, "code": "EF003BAS010"},
                        ],
                    },
                    "request": {"timeout": 2},
                    "timeout": 10,
                },
            },
            "migration_procedure_generator": {
                "host": "localhost",
                "port": 48889,
                "uri": "cdim/api/v1",
                "timeout": 30,
            },
            "configuration_manager": {
                "host": "localhost",
                "port": 48889,
                "uri": "cdim/api/v1",
                "timeout": 30,
            },
        }
        # unset values will default.
        mocker.patch("yaml.safe_load").return_value = config
        mocker.patch("requests.get")
        conf = LayoutApplyConfig().disconnect
        assert conf["retry"]["targets"] == [
            {
                "status_code": 503,
                "code": "ER005BAS001",
                "interval": 5,
                "max_count": 5,
            },
        ]
        assert conf["retry"]["default"]["interval"] == 5
        assert conf["retry"]["default"]["max_count"] == 5
        assert conf["timeout"] == 10

        conf = LayoutApplyConfig().connect
        assert conf["retry"]["targets"] == [
            {
                "status_code": 503,
                "code": "ER005BAS001",
                "interval": 5,
                "max_count": 5,
            },
        ]
        assert conf["retry"]["default"]["interval"] == 5
        assert conf["retry"]["default"]["max_count"] == 5
        assert conf["timeout"] == 10

        conf = LayoutApplyConfig().poweroff
        assert conf["retry"]["targets"] == [
            {
                "status_code": 503,
                "code": "ER005BAS001",
                "interval": 5,
                "max_count": 5,
            },
        ]
        assert conf["retry"]["default"]["interval"] == 5
        assert conf["retry"]["default"]["max_count"] == 5
        assert conf["timeout"] == 10

        conf = LayoutApplyConfig().poweron
        assert not conf["retry"]["targets"]
        assert conf["retry"]["default"]["interval"] == 5
        assert conf["retry"]["default"]["max_count"] == 5
        assert conf["timeout"] == 60

    def test_setting_default_set_when_no_retry_config(self, mocker):
        config = {
            "layout_apply": {"host": "0.0.0.0", "port": 8003, "request": {}},
            "db": {
                "dbname": "layoutapply",
                "user": "user01",
                "password": "P@ssw0rd",
                "host": "localhost",
                "port": 5435,
            },
            "workflow_manager": {
                "host": "localhost",
                "port": 8008,
                "uri": "cdim/api/v1",
                "extended-procedure": {"retry": {"default": {}}, "polling": {}},
            },
            "hardware_control": {
                "host": "localhost",
                "port": 8888,
                "uri": "api/v1",
                "disconnect": {},
                "isosboot": {
                    "polling": {
                        "count": 5,
                        "interval": 1,
                        "targets": [
                            {
                                "status_code": 204,
                            },
                        ],
                        "skip": [
                            {"status_code": 400, "code": "EF003BAS010"},
                        ],
                    },
                    "request": {"timeout": 2},
                    "timeout": 10,
                },
            },
            "migration_procedure_generator": {
                "host": "localhost",
                "port": 48889,
                "uri": "cdim/api/v1",
                "timeout": 30,
            },
            "configuration_manager": {
                "host": "localhost",
                "port": 48889,
                "uri": "cdim/api/v1",
                "timeout": 30,
            },
        }
        # all values will default.
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        conf = LayoutApplyConfig().disconnect
        assert conf["retry"]["targets"] == []
        assert conf["retry"]["default"]["interval"] == 5
        assert conf["retry"]["default"]["max_count"] == 5
        assert conf["timeout"] == 60

    def test_setting_default_set_when_no_polling_config(self, mocker):
        config = {
            "layout_apply": {"host": "0.0.0.0", "port": 8003, "request": {}},
            "db": {
                "dbname": "layoutapply",
                "user": "user01",
                "password": "P@ssw0rd",
                "host": "localhost",
                "port": 5435,
            },
            "workflow_manager": {
                "host": "localhost",
                "port": 8008,
                "uri": "cdim/api/v1",
                "extended-procedure": {
                    "retry": {"default": {}},
                    "polling": {},
                },
                "timeout": None,
            },
            "hardware_control": {
                "host": "localhost",
                "port": 8888,
                "uri": "api/v1",
                "disconnect": {},
                "isosboot": {
                    "polling": {
                        "count": 5,
                        "interval": 1,
                        "targets": [
                            {
                                "status_code": 204,
                            },
                        ],
                        "skip": [
                            {"status_code": 400, "code": "EF003BAS010"},
                        ],
                    },
                    "request": {"timeout": 2},
                    "timeout": 10,
                },
            },
            "migration_procedure_generator": {
                "host": "localhost",
                "port": 48889,
                "uri": "cdim/api/v1",
                "timeout": 30,
            },
            "configuration_manager": {
                "host": "localhost",
                "port": 48889,
                "uri": "cdim/api/v1",
                "timeout": 30,
            },
        }
        # all values will default.
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        extended_conf = LayoutApplyConfig().workflow_manager
        assert extended_conf["extended-procedure"]["polling"]["count"] == 60
        assert extended_conf["extended-procedure"]["polling"]["interval"] == 30
        assert extended_conf["timeout"] == 60
        assert extended_conf["extended-procedure"]["retry"]["default"]["interval"] == 5
        assert extended_conf["extended-procedure"]["retry"]["default"]["max_count"] == 5

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host
            {
                "hardware_control": {
                    "host": 1,
                    "port": 8888,
                    "uri": "api/v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": None,
                    "port": 8888,
                    "uri": "api/v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # port
            {
                "hardware_control": {
                    "host": "127.0.0.1",
                    "port": "0",
                    "uri": "api/v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": "127.0.0.1",
                    "port": None,
                    "uri": "api/v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # uri
            {
                "hardware_control": {
                    "host": "127.0.0.1",
                    "port": 8888,
                    "uri": 89398398,
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": "127.0.0.1",
                    "port": 8888,
                    "uri": None,
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - interval min-1
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": -1,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - interval max + 1
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 61,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": "5",
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": None,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - max_count min - 1
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 0,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - max_count max + 1
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 11,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": None,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - targets
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": "503",
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": 8988,
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # timeout - min -1
            {
                "hardware_control": {
                    "host": 1,
                    "port": 8888,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 0,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # timeout - max + 1
            {
                "hardware_control": {
                    "host": 1,
                    "port": 8888,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 601,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # empty
            {},
        ],
    )
    def test_setting_failure_when_invalid_hardware_api_config(self, mocker, update_confg):
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["hardware_control"]
        config = {**base_config, **update_confg}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        with pytest.raises(Exception):
            LayoutApplyConfig().hardware_control

    def test_setting_default_set_when_invalid_logging_level(self, mocker):
        mocker.patch("yaml.safe_load").return_value = LOG_BASE_CONFIG

        obj = LayoutApplyLogConfig().log_config
        assert obj["handlers"]["file"]["level"] == "INFO"
        assert obj["handlers"]["console"]["level"] == "INFO"
        assert obj["root"]["level"] == "INFO"

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host is valid
            {
                "db": {
                    "dbname": "layoutapply",
                    "user": "user01",
                    "password": "P@ssw0rd",
                    "host": "127.0.0.1",
                    "port": 5435,
                },
            },
            {
                "db": {
                    "dbname": "layoutapply",
                    "user": "user01",
                    "password": "P@ssw0rd",
                    "host": "localhost",
                    "port": 5435,
                },
            },
            # port is valid
            {
                "db": {
                    "dbname": "layoutapply",
                    "user": "user01",
                    "password": "P@ssw0rd",
                    "host": "localhost",
                    "port": 9999,
                },
            },
            # empty
            {},
        ],
    )
    def test_setting_success_when_db_config_normal(self, mocker, update_confg, docker_services):
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["db"]
        config = {**base_config, **update_confg}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        LayoutApplyConfig().db_config

    @pytest.mark.parametrize(
        "update_confg",
        [
            # dbname is type mismatch
            {
                "db": {
                    "dbname": 0,
                    "user": "user01",
                    "password": "P@ssw0rd",
                    "host": "127.0.0.1",
                    "port": 5435,
                },
            },
            # user is type mismatch
            {
                "db": {
                    "dbname": "layoutapply",
                    "user": 0,
                    "password": "P@ssw0rd",
                    "host": "127.0.0.1",
                    "port": 5435,
                },
            },
            # password is type mismatch
            {
                "db": {
                    "dbname": "layoutapply",
                    "user": "user01",
                    "password": 0,
                    "host": "127.0.0.1",
                    "port": 5435,
                },
            },
            # host is type mismatch
            {
                "db": {
                    "dbname": "layoutapply",
                    "user": "user01",
                    "password": "P@ssw0rd",
                    "host": 0,
                    "port": 5435,
                },
            },
            # port is type mismatch
            {
                "db": {
                    "dbname": "layoutapply",
                    "user": "user01",
                    "password": "P@ssw0rd",
                    "host": "127.0.0.1",
                    "port": "5435",
                },
            },
            # empty
            #            {},
        ],
    )
    def test_setting_failure_when_invalid_db_config(self, mocker, update_confg):
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["db"]
        config = {**base_config, **update_confg}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        with pytest.raises(Exception):
            LayoutApplyConfig().db_config

    def test_setting_failure_when_port_that_retrieved_from_secret_store_cannot_be_converted_int(self, mocker):
        update_config = {
            "db": {
                "dbname": "ApplyStatusDB",
                "password": "P@ssword",
                "user": "user01",
                "host": "0.0.0.0",
            }
        }
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["db"]
        config = {**base_config, **update_config}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mock_connection = mocker.MagicMock()
        mock_connection.content = b'{"port": "XXXX"}'
        mocker.patch("requests.get", return_value=mock_connection)

        with pytest.raises(SecretInfoGetException):
            LayoutApplyConfig().db_config

    def test_setting_failure_when_missing_required_items_from_secret_store(self, mocker):
        update_config = {
            "db": {
                "dbname": "ApplyStatusDB",
                "password": "P@ssword",
                "user": "user01",
                "host": "0.0.0.0",
            }
        }
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["db"]
        config = {**base_config, **update_config}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mock_connection = mocker.MagicMock()
        mock_connection.content = b"{}"
        mocker.patch("requests.get", return_value=mock_connection)

        with pytest.raises(SecretInfoGetException):
            LayoutApplyConfig().db_config

    @pytest.mark.parametrize("exc", [{RequestException()}, {Timeout()}, {ConnectionError()}, {Exception()}])
    def test_setting_failure_when_failed_to_get_item_from_secret_store(self, mocker, exc):
        update_config = {
            "db": {
                "dbname": "ApplyStatusDB",
                "user": "user01",
                "host": "0.0.0.0",
                "port": 5432,
            }
        }
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["db"]
        config = {**base_config, **update_config}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        requests.get.side_effect = exc

        with pytest.raises(SecretInfoGetException):
            LayoutApplyConfig().db_config

    @pytest.mark.parametrize(
        "update_confg",
        [
            # count is min
            {
                "polling": {
                    "count": 1,
                    "interval": 1,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # count is max
            {
                "polling": {
                    "count": 240,
                    "interval": 1,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # interval is min
            {
                "polling": {
                    "count": 8,
                    "interval": 0,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # interval is max
            {
                "polling": {
                    "count": 8,
                    "interval": 240,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # request.timeout is min
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 1},
                "timeout": 10,
            },
            # request.timeout is max
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 3},
                "timeout": 10,
            },
            # request.timeout is not exist
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                # "request": {"timeout": 3},
                "timeout": 10,
            },
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {},
                "timeout": 10,
            },
            # request.timeout is None
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": None},
                "timeout": 10,
            },
            # timeout is min
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 3},
                "timeout": 1,
            },
            # timeout is max
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 3},
                "timeout": 600,
            },
        ],
    )
    def test_setting_success_when_os_boot_check_api_config_normal(self, mocker, update_confg):
        config = copy.deepcopy(BASE_CONFIG)
        del config["hardware_control"]["isosboot"]
        config["hardware_control"]["isosboot"] = update_confg
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        LayoutApplyConfig().isosboot

    @pytest.mark.parametrize(
        "update_confg",
        [
            # count is min-1
            {
                "polling": {
                    "count": 0,
                    "interval": 1,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # count is max+1
            {
                "polling": {
                    "count": 241,
                    "interval": 1,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # interval is min-1
            {
                "polling": {
                    "count": 8,
                    "interval": -1,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # interval is max+1
            {
                "polling": {
                    "count": 8,
                    "interval": 241,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # request.timeout is min-1
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 0},
                "timeout": 10,
            },
            # request.timeout is max+1
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 4},
                "timeout": 10,
            },
            # timeout is None
            {
                "polling": {
                    "count": 8,
                    "interval": 0,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 3},
                "timeout": None,
            },
            # timeout is min-1
            {
                "polling": {
                    "count": 8,
                    "interval": 0,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 3},
                "timeout": 0,
            },
            # timeout is max+1
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 3},
                "timeout": 601,
            },
            # polling is not exist
            {
                "request": {"timeout": 3},
                "timeout": 601,
            },
        ],
    )
    def test_setting_failure_when_invalid_os_boot_check_api_config(self, mocker, update_confg):
        config = copy.deepcopy(BASE_CONFIG)
        del config["hardware_control"]["isosboot"]
        config["hardware_control"]["isosboot"] = update_confg
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        with pytest.raises(Exception):
            LayoutApplyConfig().isosboot

    @pytest.mark.parametrize(
        "update_confg",
        [
            {
                "polling": {
                    # "count": 10,
                    # "interval": 11,
                },
                "request": {"timeout": 2},
                # "timeout": 13,
            },
        ],
    )
    def test_setting_default_set_when_no_optional_os_boot_check_api_item(self, mocker, update_confg):
        config = copy.deepcopy(BASE_CONFIG)
        del config["hardware_control"]["isosboot"]
        config["hardware_control"]["isosboot"] = update_confg
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        is_os_boot_conf = LayoutApplyConfig().isosboot
        assert is_os_boot_conf.get("polling").get("count") == 8
        assert is_os_boot_conf.get("polling").get("interval") == 30
        assert is_os_boot_conf.get("timeout") == 60

    @pytest.mark.parametrize(
        ("update_confg", "operation"),
        [
            (
                {
                    "polling": {
                        "test_count": 0,
                        "test_interval": 0,
                    }
                },
                "poweroff",
            ),
            (
                {
                    "polling": {
                        "test_count": 0,
                        "test_interval": 0,
                    }
                },
                "connect",
            ),
            (
                {
                    "polling": {
                        "test_count": 0,
                        "test_interval": 0,
                    }
                },
                "disconnect",
            ),
        ],
    )
    def test_setting_get_information_default_set_when_invalid_item(self, mocker, update_confg, operation):
        config = copy.deepcopy(BASE_CONFIG)
        del config["get_information"]["specs"][operation]
        del config["get_information"]["specs"]["timeout"]
        config["get_information"]["specs"][operation] = update_confg
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        get_info_conf = LayoutApplyConfig().get_information
        assert get_info_conf["specs"][operation].get("polling").get("count") == 8
        assert get_info_conf["specs"][operation].get("polling").get("interval") == 30
        assert get_info_conf["specs"].get("timeout") == 60

    @pytest.mark.parametrize(
        "update_confg",
        [
            {
                "polling": {
                    "count": 10,
                    "interval": 11,
                },
                "request": {"timeout": 2},
                "timeout": 13,
            },
        ],
    )
    def test_setting_config_value_applied_when_os_boot_check_api_config(self, mocker, update_confg):
        config = copy.deepcopy(BASE_CONFIG)
        del config["hardware_control"]["isosboot"]
        config["hardware_control"]["isosboot"] = update_confg
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        is_os_boot_conf = LayoutApplyConfig().isosboot
        assert is_os_boot_conf.get("polling").get("count") == 10
        assert is_os_boot_conf.get("polling").get("interval") == 11
        assert is_os_boot_conf.get("request").get("timeout") == 2
        assert is_os_boot_conf.get("timeout") == 13

    @pytest.mark.parametrize(
        "update_confg",
        [
            # polling
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
        ],
    )
    def test_setting_config_value_applied_when_device_info_api_config(self, mocker, update_confg):
        config = copy.deepcopy(BASE_CONFIG)
        del config["get_information"]
        config["get_information"] = update_confg["get_information"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        get_information_conf = LayoutApplyConfig().get_information
        assert get_information_conf.get("host") == "localhost"
        assert get_information_conf.get("port") == 48889
        assert get_information_conf.get("uri") == "api/v1"
        specs_conf = get_information_conf.get("specs")
        assert specs_conf.get("poweroff").get("polling").get("count") == 5
        assert specs_conf.get("poweroff").get("polling").get("interval") == 1
        assert specs_conf.get("timeout") == 10

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host is valid
            {
                "get_information": {
                    "host": "127.0.0.1",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # port is valid
            {
                "get_information": {
                    "host": "localhost",
                    "port": 8000,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # uri is correct
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "cdim/api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # count is min
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 1,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 1,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 1,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # count is max
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 240,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 240,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 240,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # interval is min
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 0,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 5,
                                "interval": 0,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 5,
                                "interval": 0,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # interval is max
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 240,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 5,
                                "interval": 240,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 5,
                                "interval": 240,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # timeout is min
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 1,
                    },
                },
            },
            # timeout is max
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 600,
                    },
                },
            },
        ],
    )
    def test_setting_success_when_device_info_api_config_normal(self, mocker, update_confg):
        config = copy.deepcopy(BASE_CONFIG)
        del config["get_information"]
        config["get_information"] = update_confg["get_information"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        LayoutApplyConfig().get_information

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host is type error
            {
                "get_information": {
                    "host": 127001,
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # port is type error
            {
                "get_information": {
                    "host": "localhost",
                    "port": "port",
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # uri is type error
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": 654321,
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # count is min-1
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 0,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # count is max+1
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 241,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # interval is min-1
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": -1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # interval is max+1
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 241,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # timeout is max+1
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 601,
                    },
                },
            },
            # timeout is max-1
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 0,
                    },
                },
            },
            # host is not exist
            {
                "get_information": {
                    # "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # specs is not exist
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    # "specs":{
                    #     "poweroff": {
                    #         "polling": {
                    #             "count": 5,
                    #             "interval": 1,
                    #         },
                    #     },
                    #     "timeout": 10
                    # }
                },
            },
            # poweroff is not exist
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        # "poweroff": {
                        #     "polling": {
                        #         "count": 5,
                        #         "interval": 1,
                        #     },
                        # },
                        "timeout": 10
                    },
                },
            },
            # polling is not exist
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            # "polling": {
                            #     "count": 5,
                            #     "interval": 1,
                            # },
                        },
                        "connect": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
        ],
    )
    def test_setting_failure_when_invalid_device_info_api_config(self, mocker, update_confg):
        config = copy.deepcopy(BASE_CONFIG)
        del config["get_information"]
        config["get_information"] = update_confg["get_information"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        with pytest.raises(Exception):
            LayoutApplyConfig().get_information

    @pytest.mark.parametrize(
        "update_confg",
        [
            # polling: timeout
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                # "count": 5,
                                # "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                # "count": 5,
                                # "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                # "count": 5,
                                # "interval": 1,
                            },
                        },
                        # "timeout": 10
                    },
                },
            },
        ],
    )
    def test_setting_default_set_when_no_optional_device_info_api_item(self, mocker, update_confg):
        config = copy.deepcopy(BASE_CONFIG)
        del config["get_information"]
        config["get_information"] = update_confg["get_information"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        get_information_conf = LayoutApplyConfig().get_information
        specs_conf = get_information_conf.get("specs")
        assert specs_conf.get("poweroff").get("polling").get("count") == 8
        assert specs_conf.get("poweroff").get("polling").get("interval") == 30
        assert specs_conf.get("timeout") == 60

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
        ],
    )
    def test_setting_success_when_migration_step_generation_api_config_normal(self, mocker, update_confg):
        config = copy.deepcopy(BASE_CONFIG)
        del config["migration_procedure_generator"]
        config["migration_procedure_generator"] = update_confg["migration_procedure_generator"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        with pytest.raises(Exception):
            LayoutApplyConfig().migration_procedure

    @pytest.mark.parametrize(
        "update_confg",
        [
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
        ],
    )
    def test_setting_failure_when_invalid_migration_step_generation_api_config(self, mocker, update_confg):
        config = copy.deepcopy(BASE_CONFIG)
        del config["migration_procedure_generator"]
        config["migration_procedure_generator"] = update_confg["migration_procedure_generator"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        with pytest.raises(Exception):
            LayoutApplyConfig().migration_procedure

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host is no existent
            {
                "configuration_manager": {
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": 10,
                },
            },
            # port is no existent
            {
                "configuration_manager": {
                    "host": "localhost",
                    "uri": "api/v1",
                    "timeout": 10,
                },
            },
            # uri is no existent
            {
                "configuration_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "timeout": 10,
                },
            },
        ],
    )
    def test_setting_success_when_config_info_management_api_config_normal(self, mocker, update_confg):
        config = copy.deepcopy(BASE_CONFIG)
        del config["configuration_manager"]
        config["configuration_manager"] = update_confg["configuration_manager"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        with pytest.raises(Exception):
            LayoutApplyConfig().configuration_manager

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host is type error
            {
                "configuration_manager": {
                    "host": 127001,
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": 10,
                },
            },
            # port is type error
            {
                "configuration_manager": {
                    "host": "localhost",
                    "port": "port",
                    "uri": "api/v1",
                    "timeout": 10,
                },
            },
            # uri is type error
            {
                "configuration_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": 654321,
                    "timeout": 10,
                },
            },
        ],
    )
    def test_setting_failure_when_invalid_config_info_management_api_config(self, mocker, update_confg):
        config = copy.deepcopy(BASE_CONFIG)
        del config["configuration_manager"]
        config["configuration_manager"] = update_confg["configuration_manager"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        with pytest.raises(Exception):
            LayoutApplyConfig().configuration_manager

    @pytest.mark.parametrize(
        "update_config",
        [
            {
                "server_connection": {
                    "retry": {
                        "intervals": 5,
                        "max_counts": 10,
                    },
                },
            },
            {
                "server_connection": {
                    "retryy": {
                        "interval": 6,
                        "max_count": 8,
                    },
                },
            },
        ],
    )
    def test_setting_config_default_value_applied_when_server_connection_config(self, mocker, update_config):
        config = copy.deepcopy(BASE_CONFIG)
        config["server_connection"] = update_config["server_connection"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        server_connection_conf = LayoutApplyConfig().server_connection
        assert server_connection_conf.get("retry").get("interval") == 2
        assert server_connection_conf.get("retry").get("max_count") == 4

    @pytest.mark.parametrize(
        "update_config",
        [
            {
                "server_connection": {
                    "retry": {
                        "interval": 1,
                        "max_count": 2,
                    },
                },
            }
        ],
    )
    def test_setting_config_update_value_applied_when_server_connection_config(self, mocker, update_config):
        config = copy.deepcopy(BASE_CONFIG)
        config["server_connection"] = update_config["server_connection"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        server_connection_conf = LayoutApplyConfig().server_connection
        assert server_connection_conf.get("retry").get("interval") == 1
        assert server_connection_conf.get("retry").get("max_count") == 2

    @pytest.mark.parametrize(
        "update_config",
        [
            # server_connection is type mismatch
            {"server_connection": 1},
            # retry is type mismatch
            {
                "server_connection": {"retry": 1},
            },
            # retry.interval is type mismatch
            {
                "server_connection": {"retry": {"interval": "1", "max_count": 2}},
            },
            # retry.max_count is type mismatch
            {
                "server_connection": {"retry": {"interval": 1, "max_count": "2"}},
            },
            # retry.interval over min
            {
                "server_connection": {"retry": {"interval": -1, "max_count": 2}},
            },
            # retry.interval over max
            {
                "server_connection": {"retry": {"interval": 61, "max_count": 2}},
            },
            # retry.interval over min
            {
                "server_connection": {"retry": {"interval": 1, "max_count": -1}},
            },
            # retry.interval over max
            {
                "server_connection": {"retry": {"interval": 1, "max_count": 11}},
            },
        ],
    )
    def test_setting_failure_when_invalid_server_connection_config(self, mocker, update_config):
        base_config = copy.deepcopy(BASE_CONFIG)
        config = {**base_config, **update_config}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        with pytest.raises(Exception):
            LayoutApplyConfig().server_connection

    @pytest.mark.parametrize(
        "update_config",
        [
            {
                "message_broker": {
                    "host": "localhost",
                    "port": 3500,
                    "pubsub": "layout_apply_apply",
                    "topic": "layout_apply_apply.completed",
                }
            }
        ],
    )
    def test_setting_config_update_value_applied_when_message_broker_config(self, mocker, update_config):
        config = copy.deepcopy(BASE_CONFIG)
        config["message_broker"] = update_config["message_broker"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        message_broker_conf = LayoutApplyConfig().message_broker
        assert message_broker_conf.get("host") == "localhost"
        assert message_broker_conf.get("port") == 3500
        assert message_broker_conf.get("pubsub") == "layout_apply_apply"
        assert message_broker_conf.get("topic") == "layout_apply_apply.completed"

    @pytest.mark.parametrize(
        "update_config",
        [
            # message broker is type mismatch
            {"message_broker": 1},
            # host is not found
            {
                "message_broker": {
                    "port": 3500,
                    "pubsub": "layout_apply_apply",
                    "topic": "layout_apply_apply.completed",
                }
            },
            # port is not found
            {
                "message_broker": {
                    "host": "localhost",
                    "pubsub": "layout_apply_apply",
                    "topic": "layout_apply_apply.completed",
                }
            },
            # pubsub is not found
            {
                "message_broker": {
                    "host": "localhost",
                    "port": 3500,
                    "topic": "layout_apply_apply.completed",
                }
            },
            # topic is not found
            {
                "message_broker": {
                    "host": "localhost",
                    "port": 3500,
                    "pubsub": "layout_apply_apply",
                }
            },
            # host is type mismatch
            {
                "message_broker": {
                    "host": [1],
                    "port": 3500,
                    "pubsub": "layout_apply_apply",
                    "topic": "layout_apply_apply.completed",
                }
            },
            # port is type mismatch
            {
                "message_broker": {
                    "host": "localhost",
                    "port": [1],
                    "pubsub": "layout_apply_apply",
                    "topic": "layout_apply_apply.completed",
                }
            },
            # pubsub is type mismatch
            {
                "message_broker": {
                    "host": "localhost",
                    "port": 3500,
                    "pubsub": ["layout_apply_apply"],
                    "topic": "layout_apply_apply.completed",
                }
            },
            # topic is type mismatch
            {
                "message_broker": {
                    "host": "localhost",
                    "port": 3500,
                    "pubsub": "layout_apply_apply",
                    "topic": ["layout_apply_apply.completed"],
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_message_broker_config(self, mocker, update_config):
        base_config = copy.deepcopy(BASE_CONFIG)
        config = {**base_config, **update_config}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        with pytest.raises(Exception):
            LayoutApplyConfig().server_connection
