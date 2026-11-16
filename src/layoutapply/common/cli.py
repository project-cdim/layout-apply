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
"CLI-related Packages"

import argparse
from abc import ABC, abstractmethod


class AbstractBaseCommandLine(ABC):
    "Abstract class for command-line interface (CLI)"

    def __init__(self, description: str) -> None:
        """Constructor. Executes the add_arguments method to add command-line arguments.

        Args:
            description (str): The description of the command.
        """
        self.parser = argparse.ArgumentParser(description=description)
        self._add_arguments()
        self.args = self.parser.parse_args()

    @abstractmethod
    def run(self):
        """Describes the main process of each component.

        Raises:
            NotImplementedError: Raises an exception if not implemented.
        """
        raise NotImplementedError()  # pragma: no cover

    @abstractmethod
    def _add_arguments(self):
        """An abstract method to add command-line argument configurations to argparse.
        Implement add_arguments for ArgumentParser as shown below:
        self.parser.add_argument('-f', '--file', type=str, help='File path for migration steps')

        Raises:
            NotImplementedError: Raises an exception if not implemented.
        """
        raise NotImplementedError()  # pragma: no cover

    def get_args(self):
        """Parse command-line arguments and return a dictionary with option names as keys.

        Returns:
            dict: The result of parsing the command-line arguments.
        """
        return self.parser.parse_args()
