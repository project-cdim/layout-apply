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
"Configuration File Related Packages"

from importlib import resources

import yaml


class BaseConfig:
    "Base class for configuration files"

    def __init__(self, package: str, file_name: str) -> None:
        """Constructor

        Args:
            package (str): The name of the package where the resources are located.
            file_name (str): The file name of the resource to be loaded.
        """
        self._config = self._read_yaml(package, file_name)

    def _read_yaml(self, pacakge: str, file_name: str):
        """Load a YAML format configuration file added as a resource.

        Args:
            package (str): The name of the package where the resources are located.
            file_name (str): The file name of the resource to be loaded.

        Returns:
            _type_: _description_
        """
        return yaml.safe_load(resources.read_text(pacakge, file_name))
