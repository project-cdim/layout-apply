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
"""CLI Related Package Test"""

from layoutapply.common.config import BaseConfig


class DummyConig(BaseConfig):
    """Dummy Class for Testing ICommandLine"""

    def __init__(self) -> None:
        """Constructor. Passes the package name and file name to the BaseConfig constructor.

        Args:
            package (str): The package name indicating the location of the configuration file.
            file_name (str): The file name of the configuration file.
        """

        super().__init__("tests.layoutapply.common", "test_config.ini")

    @property
    def list_config(self):
        """Getter for the list_config configuration values.

        Returns:
            list: The configuration list for `list_config`.
        """
        return self._config["list_config"]

    @property
    def scalar_config(self):
        """Getter for the scalar_config configuration value.

        Returns:
            str: The configuration value for `scalar_config`.
        """
        return self._config["scalar_config"]

    @property
    def object_config(self):
        """Getter for the object_config configuration value.

        Returns:
            dict: The configuration dictionary for `object_config`.
        """
        return self._config["object_config"]


class TestDummyConig:
    """Test for Abstract Class of Command Line Interface"""

    def test_read_yaml_read_conf_in_yaml_format(self):
        """Ensure that configuration files in YAML format can be loaded."""
        # arrange

        # act
        dummy_config = DummyConig()

        # assert
        assert type(dummy_config.list_config) is list
        assert dummy_config.list_config[0] == "list_val1"
        assert dummy_config.list_config[1] == "list_val2"
        assert type(dummy_config.scalar_config) is str
        assert dummy_config.scalar_config == "scalar_val"
        assert type(dummy_config.object_config) is dict
        assert dummy_config.object_config["obj1"] == "obj_val1"
        assert dummy_config.object_config["obj2"] == "obj_val2"
