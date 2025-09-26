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

from uuid import uuid4

without_required_key = [
    #########################
    # 1.procedure
    # 2.operationID
    # 3.operation
    # 4.dependencies
    #########################
    (
        {
            "test": [
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ]
        }
    ),
    (
        {
            "procedures": [
                {
                    "test": 1,
                    "operation": "shutdown",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "test": "shutdown",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    # (This test is commented out because targetDeviceID is no longer required.
    #     {
    #         "procedures": [
    #             {
    #                 "operationID": 1,
    #                 "operation": "shutdown",
    #                 "test": str(uuid4()),
    #                 "dependencies": [],
    #             }
    #         ],
    #     }
    # ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "targetDeviceID": str(uuid4()),
                    "test": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "connect",
                    "targetDeviceID": str(uuid4()),
                    "test": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "disconnect",
                    "targetDeviceID": str(uuid4()),
                    "test": [],
                }
            ],
        }
    ),
]
invalid_data_type = [
    #########################
    # 1.procedure
    # 2.operationID
    # 3.operation
    # 4.targetCPUID
    # 5.targetDeviceID
    # 6.dependencies
    # 7.targetServiceID
    #########################
    (
        {
            "procedures": {
                "operationID": 1,
                "operation": "shutdown",
                "targetDeviceID": str(uuid4()),
                "dependencies": [],
            }
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": "test",
                    "operation": "shutdown",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": True,
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "poweroff",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "targetDeviceID": 1,
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "connect",
                    "targetCPUID": [],
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": "test",
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "start",
                    "targetCPUID": str(uuid4()),
                    "targetServiceID": [],
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "start",
                    "targetCPUID": str(uuid4()),
                    "targetServiceID": 1,
                    "dependencies": [],
                }
            ],
        }
    ),
]

invalid_value = [
    #########################
    # 1.targetDeviceID is empty
    # 2.targetCPUID is empty
    # 3.targetService is empty
    #########################
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "targetDeviceID": "",
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "test": "connect",
                    "targetCPUID": "",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "test": "start",
                    "targetCPUID": str(uuid4()),
                    "targetServiceID": "",
                    "dependencies": [],
                }
            ],
        }
    ),
]

any_key_combination = [
    #########################
    # 1.operation:connect    CPU ID key does not exist.
    # 2.operation:connect    Device ID key does not exist
    # 3.operation:disconnect CPU ID key does not exist.
    # 4.operation:disconnect Device ID key does not exist
    # 5.operation:boot       Device ID key does not exist
    # 6.operation:shutdown   Device ID key does not exist
    # 7.operation:start      CPU ID key does not exist.
    # 8.operation:start      Service ID key does not exist
    # 9.operation:stop       CPU ID key does not exist.
    # 10.operation:stop      Service ID key does not exist
    #########################
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "connect",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "connect",
                    "targetCPUID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "disconnect",
                    "targetCPUID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "disconnect",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "boot",
                    "targetCPUID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "targetServiceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "start",
                    "targetServiceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "start",
                    "targetCPUID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "stop",
                    "targetServiceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "stop",
                    "targetCPUID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        }
    ),
]

################################
# Input data of generate migration procedure
################################

newLayout_invalid_value = [
    #########################
    # 1.deviceIDs is []
    #########################
    (
        {
            "desiredLayout": {
                "nodes": [
                    {
                        "device": {
                            "memory": {"deviceIDs": []},
                        }
                    },
                ]
            }
        }
    ),
]

newLayout_unkown_device = [
    #########################
    # 1.(device type)  is invalid
    #########################
    (
        {
            "desiredLayout": {
                "nodes": [
                    {
                        "device": {
                            "switch": {"deviceIDs": [str(uuid4())]},
                        }
                    },
                ]
            }
        }
    ),
]

newLayout_invalid_data_type = [
    #########################
    # 1.desiredLayout
    # 2.nodes
    # 3.device
    # 4.(Device type)
    # 5.deviceIDs
    # 6.(Device type) pattern
    #########################
    (
        {
            "desiredLayout": [
                {
                    "nodes": [
                        {
                            "device": {
                                "cpu": {"deviceIDs": [str(uuid4())]},
                                "memory": {"deviceIDs": [str(uuid4())]},
                            }
                        },
                    ]
                }
            ]
        }
    ),
    (
        {
            "desiredLayout": {
                "nodes": {
                    "node": [
                        {
                            "device": {
                                "cpu": {"deviceIDs": [str(uuid4())]},
                                "memory": {"deviceIDs": [str(uuid4())]},
                            }
                        },
                    ]
                }
            }
        }
    ),
    (
        {
            "desiredLayout": {
                "nodes": [
                    {
                        "device": [
                            {
                                "cpu": {"deviceIDs": [str(uuid4())]},
                            },
                            {
                                "memory": {"deviceIDs": [str(uuid4())]},
                            },
                        ]
                    },
                ]
            }
        }
    ),
    (
        {
            "desiredLayout": {
                "nodes": [
                    {
                        "device": {
                            "cpu": [{"deviceIDs": [str(uuid4())]}],
                            "memory": [{"deviceIDs": [str(uuid4())]}],
                        }
                    },
                ]
            }
        }
    ),
    (
        {
            "desiredLayout": {
                "nodes": [
                    {
                        "device": {
                            "cpu": {"deviceIDs": {"deviceID": str(uuid4())}},
                        }
                    },
                ]
            }
        }
    ),
    (
        {
            "desiredLayout": {
                "nodes": [
                    {
                        "device": {
                            "cpu": {"deviceIDs": [str(uuid4())]},
                            "networkInterface": {"deviceIDs": [str(uuid4())]},
                            "network-Interface": {"deviceIDs": [str(uuid4())]},
                        }
                    },
                ]
            }
        }
    ),
]

newLayout_without_required_key = [
    #########################
    # 1.desiredLayout
    # 2.nodes
    #########################
    (
        {
            "test": {
                "nodes": [
                    {
                        "device": {
                            "cpu": {"deviceIDs": [str(uuid4())]},
                            "memory": {"deviceIDs": [str(uuid4())]},
                        }
                    },
                ]
            }
        }
    ),
    (
        {
            "desiredLayout": {
                "test": [
                    {
                        "device": {
                            "cpu": {"deviceIDs": [str(uuid4())]},
                            "memory": {"deviceIDs": [str(uuid4())]},
                        }
                    },
                ]
            }
        }
    ),
]
