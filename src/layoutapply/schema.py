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
"""jsonschema"""

config = {
    # same settings are defined separately and referenced for each hardware control API.
    "$defs": {
        "hwapi": {
            "type": "object",
            "properties": {
                # Definition of retry
                "retry": {
                    "type": "object",
                    "properties": {
                        # Definition of responses subject to retry
                        "targets": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    # HTTP status codes assumed for retry
                                    "status_code": {
                                        "type": "integer",
                                    },
                                    # Error codes assuming retry implementation
                                    "code": {
                                        "type": "string",
                                    },
                                    # Retry interval (unit: s, maximum 60s)
                                    "interval": {
                                        "type": "integer",
                                        "minimum": 0,
                                        "maximum": 60,
                                    },
                                    # Retry max count (maximum 10)
                                    "max_count": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "maximum": 10,
                                    },
                                },
                            },
                        },
                        # Definition of retry on error occurrence
                        "default": {
                            "type": "object",
                            "properties": {
                                # Retry interval (unit: s, maximum 60s)
                                "interval": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "maximum": 60,
                                },
                                # Retry max count (maximum 10)
                                "max_count": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 10,
                                },
                            },
                        },
                    },
                },
                # Timeout seconds (unit s, maximum 600s)
                "timeout": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 600,
                },
            },
        },
        "pollingschema": {
            "type": "object",
            "required": ["polling"],
            "properties": {
                # Definition of polling for the Device Information Retrieval API
                "polling": {
                    "type": "object",
                    "properties": {
                        # Number of polls (minimum 1, maximum 240)
                        "count": {
                            "type": ["integer", "null"],
                            "minimum": 1,
                            "maximum": 240,
                        },
                        # Polling interval (unit: s, minimum 0s, maximum 240s)
                        "interval": {
                            "type": ["integer", "null"],
                            "minimum": 0,
                            "maximum": 240,
                        },
                    },
                }
            },
        },
    },
    "type": "object",
    "required": [
        "layout_apply",
        "hardware_control",
        "configuration_manager",
        "migration_procedure_generator",
    ],
    "properties": {
        # Log definition
        "log": {
            "type": "object",
            "properties": {
                # Log level
                "logging_level": {
                    "type": "string",
                    "enum": ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"],
                },
                # Log directory
                "log_dir": {
                    "type": "string",
                },
                # Log file name
                "file": {
                    "type": "string",
                },
                # Rotation file size
                "rotation_size": {
                    "type": "integer",
                },
                # Number of log file backups
                "backup_files": {
                    "type": "integer",
                },
                # If "true" is specified, the log is also output to the standard output.
                "stdout": {
                    "type": "boolean",
                },
            },
        },
        # Configuration LayoutApply related settings
        "layout_apply": {
            "type": "object",
            "required": ["host", "port"],
            "properties": {
                # IP/HOST
                "host": {
                    "type": "string",
                    "minLength": 1,
                },
                # Port
                "port": {
                    "type": "integer",
                },
                # Request Collection
                "request": {
                    "type": "object",
                    "properties": {
                        # Max_workers for layoutapply
                        "max_workers": {
                            "type": ["integer", "null"],
                            "minimum": 1,
                            "maximum": 128,
                        },
                    },
                },
            },
        },
        # Configuration Database related settings
        "db": {
            "type": "object",
            "properties": {
                # database name
                "dbname": {"type": "string"},
                # user name
                "user": {"type": "string"},
                # password
                "password": {"type": "string"},
                # IP/HOST
                "host": {
                    "type": "string",
                },
                # Port
                "port": {
                    "type": "integer",
                },
            },
        },
        # Configuration get_information related settings
        "get_information": {
            "type": "object",
            "required": ["host", "port", "uri", "specs"],
            "properties": {
                # IP/HOST
                "host": {
                    "type": "string",
                },
                # Port
                "port": {
                    "type": "integer",
                },
                # URI
                "uri": {
                    "type": "string",
                },
                "specs": {
                    "type": "object",
                    "required": ["poweroff", "connect", "disconnect"],
                    "properties": {
                        # Definition of execution after poweroff
                        "poweroff": {
                            "$ref": "#/$defs/pollingschema",
                        },
                        # Definition before executing connect
                        "connect": {
                            "$ref": "#/$defs/pollingschema",
                        },
                        # Definition after executing disconnect
                        "disconnect": {
                            "$ref": "#/$defs/pollingschema",
                        },
                        # Timeout duration (unit: s, maximum 600s)
                        "timeout": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 600,
                        },
                    },
                },
            },
        },
        # Configuration hardware_control related settings
        "hardware_control": {
            "type": "object",
            "required": ["host", "port", "uri", "isosboot"],
            "properties": {
                # IP/HOST
                "host": {
                    "type": "string",
                },
                # Port
                "port": {
                    "type": "integer",
                },
                # URI
                "uri": {
                    "type": "string",
                },
                # Settings related to the operation type "disconnect"
                "disconnect": {
                    "$ref": "#/$defs/hwapi",
                },
                # Settings related to the operation type "connect"
                "connect": {
                    "$ref": "#/$defs/hwapi",
                },
                # Settings related to the operation type "poweroff"
                "poweroff": {
                    "$ref": "#/$defs/hwapi",
                },
                # Settings related to the operation type "poweron"
                "poweron": {
                    "$ref": "#/$defs/hwapi",
                },
                # Settings related to the operation type "isosboot"
                "isosboot": {
                    "type": "object",
                    "required": ["polling"],
                    "properties": {
                        # Definition regarding polling for isOSboot API
                        "polling": {
                            "type": "object",
                            "properties": {
                                # Number of polls (minimum 1, maximum 240)
                                "count": {
                                    "type": ["integer", "null"],
                                    "minimum": 1,
                                    "maximum": 240,
                                },
                                # Polling interval (unit: s, minimum 0s, maximum 240s)
                                "interval": {
                                    "type": ["integer", "null"],
                                    "minimum": 0,
                                    "maximum": 240,
                                },
                                # Definition regarding the response to skip the isOSboot API
                                "skip": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["status_code", "code"],
                                        "properties": {
                                            # HTTP status codes to skip
                                            "status_code": {
                                                "type": "integer",
                                            },
                                            # Error codes to assume to skip
                                            "code": {
                                                "type": "string",
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        # Definition of parameters related to the isOSboot API
                        "request": {
                            "type": "object",
                            "properties": {
                                # Timeout value to be used as a parameter for the isOSboot API
                                "timeout": {
                                    "type": ["integer", "null"],
                                    "minimum": 1,
                                    "maximum": 3,
                                },
                            },
                        },
                        # Timeout seconds (unit s, maximum 600s)
                        "timeout": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 600,
                        },
                    },
                },
            },
        },
        # Configuration migration_procedure_generator related settings
        "migration_procedure_generator": {
            "type": "object",
            "required": ["host", "port", "uri"],
            "properties": {
                "host": {"type": "string", "minLength": 1},
                "port": {"type": "integer"},
                "uri": {"type": "string"},
                # Timeout seconds (unit s, maximum 600s)
                "timeout": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 600,
                },
            },
        },
        # Configuration configuration_manager related settings
        "configuration_manager": {
            "type": "object",
            "required": ["host", "port", "uri"],
            "properties": {
                "host": {"type": "string", "minLength": 1},
                "port": {"type": "integer"},
                "uri": {"type": "string"},
                # Timeout seconds (unit s, maximum 600s)
                "timeout": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 600,
                },
            },
        },
        # Configuration server_connection related settings
        "server_connection": {
            "type": "object",
            "properties": {
                # Retry value
                "retry": {
                    "type": "object",
                    "properties": {
                        "interval": {
                            "type": ["integer", "null"],
                            "minimum": 0,
                            "maximum": 60,
                        },
                        "max_count": {
                            "type": ["integer", "null"],
                            "minimum": 1,
                            "maximum": 10,
                        },
                    },
                },
            },
        },
    },
}

# list of migration procedure
procedure = {
    "type": "object",
    "required": ["procedures"],
    "properties": {
        "procedures": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "operationID",
                    "operation",
                    "targetDeviceID",
                    "dependencies",
                ],
                "properties": {
                    # ID of step 1 operation of the migration procedure
                    "operationID": {
                        "type": "integer",
                    },
                    # Operation types for migration procedure
                    "operation": {
                        "type": "string",
                        "enum": ["boot", "shutdown", "connect", "disconnect"],
                    },
                    # Target CPU device ID
                    "targetCPUID": {
                        "type": "string",
                        "minLength": 1,
                    },
                    # Target device ID
                    "targetDeviceID": {
                        "type": "string",
                        "minLength": 1,
                    },
                    # A list storing operationIDs of dependent migration operations
                    "dependencies": {
                        "type": "array",
                        "items": {
                            "type": "integer",
                        },
                    },
                },
                "if": {
                    "properties": {"operation": {"enum": ["connect", "disconnect"]}},
                },
                "then": {"required": ["targetCPUID"]},
            },
        },
    },
}

# ApplyID
apply_id = {
    "type": "string",
    "pattern": "^[0-9a-f]+$",
    "minLength": 10,
    "maxLength": 10,
}

# Status specified as search condition for list acquisition
status = {
    "type": "string",
    "enum": [
        "IN_PROGRESS",
        "COMPLETED",
        "FAILED",
        "CANCELING",
        "CANCELED",
        "SUSPENDED",
    ],
}

# Action types required by LayoutApply
action = {
    "type": "string",
    "enum": ["cancel", "resume"],
}

# Device information
# Use type and powerState to identify the device when turning off the power
# and to check the power status after poweroff.
device_information = {
    "type": "object",
    "required": ["type"],
    "properties": {
        # Device type to retrieve device information from
        "type": {
            "type": "string",
            "enum": [
                "CPU",
                "ACCELERATOR",
                "DSP",
                "FPGA",
                "GPU",
                "UNKNOWNPROCESSOR",
                "MEMORY",
                "STORAGE",
                "NETWORKINTERFACE",
                "GRAPHICCONTROLLER",
                "VIRTUALMEDIA",
                "SWITCH",
            ],
        },
        # Current power state of the processor
        "powerState": {
            "type": "string",
            "enum": ["Off", "On", "PoweringOff", "PoweringOn", "Paused", "Unknown"],
        },
        # Whether the power control function is enabled
        "powerCapability": {
            "type": "boolean",
        },
    },
}

# Specify the items to be included in the search results. If not specified, all columns will be retrieved.
fields = {
    "type": "array",
    "uniqueItems": True,
    "items": {
        "type": "string",
        "enum": [
            "procedures",
            "applyResult",
            "rollbackProcedures",
            "rollbackResult",
            "resumeProcedures",
            "resumeResult",
        ],
    },
    "minItems": 1,
}

# Time format for start and end time search parameters
# Reference[https://qiita.com/Astro1123/items/58bbb47a66347b52f4c8#%E6%97%A5%E4%BB%98]
time_format = {
    "type": "string",
    "pattern": "^(\\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\\d|3[01])T([01]\\d|2[0-3])"
    ":([0-5]\\d):([0-5]\\d)(Z|[+-]([01]\\d|2[0-3]):([0-5]\\d))$",
}

# Sort items
sortBy = {
    "type": "string",
    "enum": [
        "startedAt",
        "endedAt",
    ],
}

# Sort order: "asc/desc". If unspecified, it defaults to ascending.
orderBy = {
    "type": "string",
    "enum": [
        "asc",
        "desc",
    ],
}

# Number of items obtained. Acquires the status for the specified number of items.
limit = {
    "type": "integer",
    "minimum": 1,
}

# Acquire starting line number. Retrieve status from the specified line.
offset = {
    "type": "integer",
    "minimum": 0,
}

# desiredLayout
desiredLayout = {
    "type": "object",
    "required": ["nodes"],
    "properties": {
        # list of node
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    # Device info
                    "device": {
                        "type": "object",
                        "additionalProperties": False,
                        "patternProperties": {
                            "^(.+)$": {
                                "type": "object",
                                "properties": {
                                    "deviceIDs": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {"type": "string"},
                                    }
                                },
                                "additionalProperties": False,
                            }
                        },
                    },
                },
            },
        },
    },
}

targetNodeID = {
    "targetNodeIDs": {
        "type": "array",
        "items": {
            "type": "string",
            "minLength": 1,
        },
    }
}

configmanager_api_resp = {
    "type": "object",
    "required": ["nodes"],
    "properties": {
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["resources"],
                "properties": {
                    "resources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["device"],
                            "properties": {
                                "device": {
                                    "type": "object",
                                    "required": ["deviceID", "type"],
                                    "properties": {
                                        "deviceID": {"type": "string"},
                                        "type": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }
    },
}

get_resources_available_api_resp = {
    "type": "object",
    "required": ["resources"],
    "properties": {
        "resources": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["device"],
                "properties": {
                    "device": {
                        "type": "object",
                        "required": ["type", "deviceID"],
                        "properties": {
                            "type": {
                                "type": "string",
                            },
                            "deviceID": {
                                "type": "string",
                            },
                            "constraints": {
                                "type": "object",
                                "properties": {
                                    "nonRemovableDevices": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "deviceID": {
                                                    "type": "string",
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}

# Add required items to the DB schema and configure them.
db_required_item = {"required": ["dbname", "user", "password", "host", "port"]}
db_config_schema = {**config["properties"]["db"], **db_required_item}
