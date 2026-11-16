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
import logging

PREFIX_LOWER = "cdim"

DEBUG = logging.DEBUG
INFO = logging.INFO
WARN = logging.WARN
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL
TRAIL_REQ = 60
TRAIL_RES = 61
EVENT_PUB = 70
EVENT_SUB = 71

TAG_APP_HWCONTROL = "APP.HWCONTROL"
TAG_APP_POLICY = "APP.POLICY"
TAG_APP_LAYOUTDESIGN = "APP.LAYOUTDESIGN"
TAG_APP_LAYOUTAPPLY = "APP.LAYOUTAPPLY"
TAG_APP_CONFIGMGR = "APP.CONFIGMGR"
TAG_APP_CONFIGCOLLECT = "APP.CONFIGCOLLECT"
TAG_APP_PERFORMCOLLECT = "APP.PERFORMCOLLECT"
TAG_APP_EXPORTER = "APP.EXPORTER"
TAG_BACKUP_WORKER = "BACKUP.WORKER"
TAG_BACKUP_CONTROLLER = "BACKUP.CONTROLLER"
TAG_TRAIL = "TRAIL"
TAG_EVENT = "EVENT"

LOG_DIR = f"/var/log/{PREFIX_LOWER}"
LOG_FILES = {
    TAG_APP_HWCONTROL: "app_hw_control.log",
    TAG_APP_POLICY: "app_policy.log",
    TAG_APP_LAYOUTDESIGN: "app_layout_design.log",
    TAG_APP_LAYOUTAPPLY: "app_layout_apply.log",
    TAG_APP_CONFIGMGR: "app_config_mgr.log",
    TAG_APP_CONFIGCOLLECT: "app_config_collect.log",
    TAG_APP_PERFORMCOLLECT: "app_perform_collect.log",
    TAG_APP_EXPORTER: "app_exporter.log",
    TAG_BACKUP_WORKER: "backup_worker.log",
    TAG_BACKUP_CONTROLLER: "backup_controller.log",
    TAG_TRAIL: "trail.log",
    TAG_EVENT: "event.log",
}
LOG_DEFAULT_FILE = "default.log"

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
LOG_ROTATION_SIZE = 100000000
LOG_BACKUP_FILES = 72
LOG_ENCODING = "utf-8"
LOG_MODE = "a"

LOG_TIME_FORMAT = "%Y/%m/%d %H:%M:%S.{}{}"
LOG_MSEC_FORMAT = ""
