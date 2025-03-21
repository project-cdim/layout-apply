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
"""Test for CLI Related Package"""

import sys

import pytest

from layoutapply.common.cli import AbstractBaseCommandLine


class DummyCommandLine(AbstractBaseCommandLine):
    """Dummy Class for Testing AbstractBaseCommandLine"""

    def _add_arguments(self):
        """Define Arguments"""
        self.parser.add_argument("-d", "--dummy", type=str, help="Dummy argument")

    def run(self, dummy):
        """Processing body of the command

        Args:
            arg (Any): System argument

        Returns:
            str: Returns the content of the dummy option
        """
        return dummy


class TestAbstractBaseCommandLine:
    """Test for abstract class for command line interface"""

    @pytest.mark.parametrize(
        "arg_name, arg_val",
        [
            ("-d", "dummy_value1"),
            ("--dummy", "dummy_value2"),
        ],
    )
    def test_get_args_can_execute_when_having_arguments(self, arg_name, arg_val):
        """The ability to execute with specified arguments"""
        # arrange
        # Mocking the arguments (sys.argv) (insert a placeholder string since the first one contains the executed file name)
        sys.argv = [
            "DummyCommandLine.py",
            arg_name,
            arg_val,
        ]

        # act
        dummy_commandline = DummyCommandLine("Dummy command line interface")
        args = dummy_commandline.get_args()
        result = dummy_commandline.run(args.dummy)

        # assert
        assert result == arg_val
