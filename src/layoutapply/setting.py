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
"""Configuration file loading class"""

import json
import os

import requests
from jsonschema import validate

from layoutapply.common.config import BaseConfig
from layoutapply.const import DbConfigName, RequestParameter
from layoutapply.custom_exceptions import SecretInfoGetException, SettingFileLoadException
from layoutapply.schema import config as config_schema
from layoutapply.schema import db_config_schema, log_config_schema


class LayoutApplyLogConfig(BaseConfig):
    """Class for reading logging configuration files of the LayoutApply function"""

    def __init__(self) -> None:
        try:
            super().__init__("layoutapply.config", "layoutapply_log_config.yaml")
            validate(instance=self._config, schema=log_config_schema)
            self._validate_log_dir()
        except Exception as error:
            raise SettingFileLoadException(error.args, "layoutapply_log_config.yaml") from error

    def _validate_log_dir(self):
        """validate log dir setting.

        Raises:
            FileNotFoundError: Directory not found.
        """
        filename = self._config.get("handlers", {}).get("file", {}).get("filename")
        log_dir = os.path.dirname(filename)
        if log_dir:
            self._check_directory_path(log_dir)

    def _check_directory_path(self, path: str) -> None:
        """Check if the directory exists.

        Args:
            path (str): Directory path

        Raises:
            FileNotFoundError: Directory not found.
        """
        if not os.path.isdir(path):
            raise FileNotFoundError(f"Directory not found at path: {path}")

    @property
    def log_config(self) -> dict:
        """Reading log configuration data from an settings file

        Returns:
            dict: read config date
        """
        return self._config


class LayoutApplyConfig(BaseConfig):
    """Class for reading configuration files of the LayoutApply function"""

    def __init__(self) -> None:
        try:
            super().__init__("layoutapply.config", "layoutapply_config.yaml")
            validate(instance=self._config, schema=config_schema)
            self._load_configs()
        except Exception as error:
            raise SettingFileLoadException(error.args, "layoutapply_config.yaml") from error

        try:
            self._get_secret()
            validate(self._config["db"], db_config_schema)
        except Exception as error:
            raise SecretInfoGetException(error.args) from error

        self._log_config = None

    def _load_configs(self):
        """load config classes"""
        self._db_config = self._config.get("db", {})
        self._layout_apply_config = self._config.get("layout_apply", {})

    def _get_secret(self) -> None:
        """get secret information for secret store"""
        tmp_config = {}
        results = requests.get(
            url=f"{RequestParameter.URL}",
            timeout=100,
        )
        if "db" not in self._config:
            self._config["db"] = {}
        for key in list(DbConfigName.__dict__.get("_value2member_map_").keys()):
            if key not in self._config.get("db"):
                secret_data = self._retrieve_secret_store(results, key)
                if secret_data:
                    tmp_config[key] = secret_data
        self._config["db"].update(tmp_config)

    def _retrieve_secret_store(self, results, key) -> int | str:
        """stores information acquired

        Args:
            results (response): get secret store info
            key (str): get secret key
        return:
            secret_info (int,str): db config
        """
        secret_info = json.loads(results.content.decode()).get(key)
        if key == DbConfigName.PORT:
            try:
                secret_info = int(secret_info)
            except Exception:  # pylint:disable=W0718
                # If the conversion to int type fails, return the value without doing anything and
                # let the error occur in the json_schema validation check.
                pass
        return secret_info

    def load_log_configs(self):
        """load log config classes"""
        self._log_config = LayoutApplyLogConfig()

    @property
    def layout_apply(self) -> dict:
        """Layout_apply configuration group getter

        Returns:
            dict: Settings group of layout_apply
        """
        return self._layout_apply_config

    @property
    def db_config(self) -> dict:
        """Db configuration group getter

        Returns:
            dict: Settings group of db
        """
        return self._db_config

    @property
    def log_config(self) -> dict:
        """Reading log configuration data from an settings file

        Returns:
            dict: read config date
        """
        return self._log_config.log_config if self._log_config else None

    @property
    def get_information(self) -> dict:
        """Get_information configuration group getter

        Returns:
            dict: Settings group of get_information
        """
        default_specs = {
            "poweroff": {"polling": {"count": 8, "interval": 30}},
            "connect": {"polling": {"count": 8, "interval": 30}},
            "disconnect": {"polling": {"count": 8, "interval": 30}},
            "timeout": 60,
        }

        read_conf = self._config.get("get_information")
        specs_conf = read_conf.get("specs")
        read_conf["specs"] = default_specs
        # Set the timeout excluding the one at the same level
        for o in [x for x, y in default_specs.items() if x != "timeout"]:
            _set_specs_polling_count(read_conf, o, specs_conf.get(o).get("polling"))
            _set_specs_polling_interval(read_conf, o, specs_conf.get(o).get("polling"))
        _set_specs_timeout(read_conf, specs_conf)

        return read_conf

    @property
    def workflow_manager(self) -> dict:
        """Workflow_manager configuration group getter

        Returns:
            dict: Settings group of workflow_manager
        """
        default_workflow_manager_conf = {
            "extended-procedure": {
                "polling": {"count": 60, "interval": 30},
                "retry": {"default": {"interval": 5, "max_count": 5}},
            },
            "timeout": 60,
        }

        timeout_conf = read_conf = self._config.get("workflow_manager")
        polling_conf = read_conf.get("extended-procedure").get("polling", {})
        retry_conf = read_conf.get("extended-procedure").get("retry", {})
        read_conf["timeout"] = default_workflow_manager_conf["timeout"]
        read_conf["extended-procedure"] = default_workflow_manager_conf["extended-procedure"]
        _set_timeout(read_conf, timeout_conf)
        if polling_conf:
            _set_polling_count(read_conf["extended-procedure"], polling_conf)
            _set_polling_interval(read_conf["extended-procedure"], polling_conf)
        if retry_conf.get("default"):
            _set_retry_default(read_conf["extended-procedure"], retry_conf)

        return read_conf

    @property
    def hardware_control(self) -> dict:
        """Hardware_control configuration group getter

        Returns:
            dict: Settings group of hardware_control
        """
        return self._config.get("hardware_control")

    def _get_hwapi_setting(self, key: str):
        """Obtaining API settings for each request type

        Args:
            key (str): Key value of the request type

        Returns:
            dict: The obtained set of configuration values for each request type
        """
        conf = {
            "retry": {
                "targets": [],
                "default": {
                    "interval": 5,
                    "max_count": 5,
                },
            },
            "timeout": 60,
        }
        read_conf = self.hardware_control.get(key, {})
        # Overwrite the default settings with the obtained values.
        if "retry" in read_conf:
            retry_conf = read_conf["retry"]
            _set_retry_targets(conf, retry_conf)
            _set_retry_default(conf, retry_conf)
        _set_timeout(conf, read_conf)
        return conf

    @property
    def disconnect(self) -> dict:
        """Disconnect configuration group getter

        Returns:
            dict: Settings group of disconnect
        """
        return self._get_hwapi_setting("disconnect")

    @property
    def connect(self) -> dict:
        """Connect configuration group getter

        Returns:
            dict: Settings group of connect
        """
        return self._get_hwapi_setting("connect")

    @property
    def poweroff(self) -> dict:
        """Poweroff configuration group getter

        Returns:
            dict: Settings group of poweroff
        """
        return self._get_hwapi_setting("poweroff")

    @property
    def poweron(self) -> dict:
        """Poweron configuration group getter

        Returns:
            dict: Settings group of poweron
        """
        return self._get_hwapi_setting("poweron")

    @property
    def isosboot(self) -> dict:
        """Isosboot configuration group getter

        Returns:
            dict: Settings group of isosboot
        """
        conf = {
            "polling": {
                "count": 8,
                "interval": 30,
                "skip": [],
            },
            "request": {
                "timeout": None,
            },
            "timeout": 60,
        }
        read_conf = self.hardware_control.get("isosboot", {})
        # Overwrite the default settings with the obtained values
        polling_conf = read_conf["polling"]
        _set_polling_count(conf, polling_conf)
        _set_polling_interval(conf, polling_conf)
        _set_polling_skip(conf, polling_conf)
        _set_request(conf, read_conf)
        _set_timeout(conf, read_conf)
        return conf

    @property
    def migration_procedure(self) -> dict:
        """Configuration getter for migration procedure generation API

        Returns:
            dict: Settings group for generating migration procedures
        """
        conf = self._config.get("migration_procedure_generator")
        conf["timeout"] = conf.get("timeout", 30)
        return conf

    @property
    def configuration_manager(self) -> dict:
        """Configuration information management settings

        Returns:
            dict: Configuration information management settings group.
        """
        conf = self._config.get("configuration_manager")
        conf["timeout"] = conf.get("timeout", 30)
        return conf

    @property
    def server_connection(self) -> dict:
        """server_connection configuration group getter

        Returns:
            dict: Settings group of server_connection
        """
        conf = {
            "retry": {
                "interval": 2,
                "max_count": 4,
            },
        }
        read_conf = self._config.get("server_connection", {})
        # Overwrite the default settings with the obtained values.
        if "retry" in read_conf:
            retry_conf = read_conf["retry"]
            conf["retry"]["interval"] = retry_conf.get("interval", 2)
            conf["retry"]["max_count"] = retry_conf.get("max_count", 4)
        return conf

    @property
    def message_broker(self) -> dict:
        """message_broker configuration group getter

        Returns:
            dict: Settings group of message_broker
        """
        return self._config.get("message_broker", {})


def _set_specs_polling_count(read_conf: dict, operation: str, polling_conf: dict):
    """set config value if exists.

    Args:
        conf (dict): target config dict.
        operation (str): operation
        polling_conf (dict): default config value.
    """
    if "count" in polling_conf:
        read_conf["specs"][operation]["polling"]["count"] = polling_conf["count"]


def _set_specs_polling_interval(read_conf: dict, operation: str, polling_conf: dict):
    """set config value if exists.

    Args:
        conf (dict): target config dict.
        operation (str): operation
        polling_conf (dict): default config value.
    """
    if "interval" in polling_conf:
        read_conf["specs"][operation]["polling"]["interval"] = polling_conf["interval"]


def _set_specs_timeout(read_conf: dict, specs_conf: dict):
    """set config value if exists.

    Args:
        conf (dict): target config dict.
        specs_conf (dict): default config value.
    """
    if "timeout" in specs_conf:
        read_conf["specs"]["timeout"] = specs_conf["timeout"]


def _set_retry_targets_interval(conf: dict, index: int, target: dict):
    """set config value if exists.

    Args:
        conf (dict): target config dict.
        retry_conf (dict): default config value.
    """
    if "interval" not in target:
        conf["retry"]["targets"][index]["interval"] = 5


def _set_retry_targets_max_count(conf: dict, index: int, target: dict):
    """set config value if exists.

    Args:
        conf (dict): target config dict.
        retry_conf (dict): default config value.
    """
    if "max_count" not in target:
        conf["retry"]["targets"][index]["max_count"] = 5


def _set_retry_targets(conf: dict, retry_conf: dict):
    """set config value if exists.

    Args:
        conf (dict): target config dict.
        retry_conf (dict): default config value.
    """
    if "targets" in retry_conf:
        conf["retry"]["targets"] = retry_conf["targets"]
        for index, target in enumerate(conf["retry"]["targets"]):
            _set_retry_targets_interval(conf, index, target)
            _set_retry_targets_max_count(conf, index, target)


def _set_retry_default(conf: dict, retry_conf: dict):
    """set config value if exists.

    Args:
        conf (dict): target config dict.
        retry_conf (dict): default config value.
    """
    if "default" in retry_conf:
        if "interval" in retry_conf["default"]:
            conf["retry"]["default"]["interval"] = retry_conf["default"]["interval"]
        if "max_count" in retry_conf["default"]:
            conf["retry"]["default"]["max_count"] = retry_conf["default"]["max_count"]


def _set_polling_count(conf: dict, polling_conf: dict):
    """set config value if exists.

    Args:
        conf (dict): target config dict.
        polling_conf (dict): default config value.
    """
    if "count" in polling_conf:
        conf["polling"]["count"] = polling_conf["count"]


def _set_polling_interval(conf: dict, polling_conf: dict):
    """set config value if exists.

    Args:
        conf (dict): target config dict.
        polling_conf (dict): default config value.
    """
    if "interval" in polling_conf:
        conf["polling"]["interval"] = polling_conf["interval"]


def _set_polling_skip(conf: dict, polling_conf: dict):
    """set config value if exists.

    Args:
        conf (dict): target config dict.
        polling_conf (dict): default config value.
    """
    if "skip" in polling_conf:
        conf["polling"]["skip"] = polling_conf["skip"]


def _set_request(conf: dict, read_conf: dict):
    """set config value if exists.

    Args:
        conf (dict): target config dict.
        read_conf (dict): default config value.
    """
    if "request" in read_conf:
        request_conf = read_conf["request"]
        if "timeout" in request_conf:
            conf["request"]["timeout"] = request_conf["timeout"]


def _set_timeout(conf: dict, read_conf: dict):
    """set config value if exists.

    Args:
        conf (dict): target config dict.
        read_conf (dict): default config value.
    """
    if "timeout" in read_conf:
        conf["timeout"] = read_conf["timeout"]
