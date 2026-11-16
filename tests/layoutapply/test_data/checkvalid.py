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
    # 4.targetDeviceID
    # 5.dependencies
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
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "test": str(uuid4()),
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
]

invalid_value = [
    #########################
    # 1.targetDeviceID is empty
    # 2.targetCPUID is empty
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
    )
]

newLayout_invalid_data_type = [
    #########################
    # 1.desiredLayout
    # 2.nodes
    # 3.device
    # 4.(Device type)
    # 5.deviceIDs
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
