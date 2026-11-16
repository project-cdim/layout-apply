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
"Subprocess executor helper"

import argparse
import os
import pickle
import sys
from dataclasses import asdict

from layoutapply.cdimlogger import Logger
from layoutapply.setting import LayoutApplyConfig

sys.path.append(os.path.abspath("."))

# pylint: disable=wrong-import-position
from layoutapply.cli import SubprocOpt  # noqa: E402
from layoutapply.custom_exceptions import FailedStartSubprocessException  # noqa: E402
from layoutapply.main import run  # noqa: E402


def exec_run():
    """Method invocation executed in a subprocess"""
    parser = argparse.ArgumentParser()
    parser.add_argument("file_name")
    file_path = parser.parse_args().file_name
    try:
        with open(file_path, "r", encoding="utf-8") as fp:
            args: SubprocOpt = pickle.loads(bytes.fromhex(fp.read()), encoding="utf-8")
        os.remove(file_path)
    except Exception as err:  # pylint: disable=W0703
        exc = FailedStartSubprocessException(err)
        Logger(**LayoutApplyConfig().logger_args).error(f"[E40026]{exc.message}")
        sys.exit(exc.exit_code)

    run(**asdict(args))


if __name__ == "__main__":  # pragma: no cover
    exec_run()
