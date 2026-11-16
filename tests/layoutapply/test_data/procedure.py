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
"""migration procedure data"""

from uuid import uuid4

dummy_data = {
    "procedures": [
        {
            "operationID": 1,
            "operation": "shutdown",
            "targetDeviceID": str(uuid4()),
            "dependencies": [],
        }
    ]
}


single_pattern = [
    #########################
    # Singular migration procedure
    #########################
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ]
        },
        0.1,
        "123456789a",
    )
]
single_pattern_cancel = [
    #########################
    # Singular migration procedure for cancel
    #########################
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ]
        },
        0.1,
        "012345678e",
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "boot",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        },
        0.2,
        "012345678f",
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "connect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        },
        0.3,
        "123456780e",
    ),
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "disconnect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                }
            ],
        },
        0.4,
        "123456780f",
    ),
]
multi_pattern = [
    #########################
    # Multiple migration procedure(Integration with dependencies available)
    #########################
    # (
    #     {
    #         "procedures": [
    #             {
    #                 "operationID": 1,
    #                 "operation": "shutdown",
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #             {
    #                 "operationID": 2,
    #                 "operation": "disconnect",
    #                 "targetCPUID": str(uuid4()),
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [1],
    #             },
    #             {
    #                 "operationID": 3,
    #                 "operation": "connect",
    #                 "targetCPUID": str(uuid4()),
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [2],
    #             },
    #             {
    #                 "operationID": 4,
    #                 "operation": "boot",
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [3],
    #             },
    #         ]
    #     },
    #     0.1,
    #     "123456789a",
    # ),
    # #########################
    # Multiple migration procedure(No dependencies, all in parallel)
    # #########################
    # (
    #     {
    #         "procedures": [
    #             {
    #                 "operationID": 1,
    #                 "operation": "shutdown",
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #             {
    #                 "operationID": 2,
    #                 "operation": "disconnect",
    #                 "targetCPUID": str(uuid4()),
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #             {
    #                 "operationID": 3,
    #                 "operation": "connect",
    #                 "targetCPUID": str(uuid4()),
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #             {
    #                 "operationID": 4,
    #                 "operation": "boot",
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #         ]
    #     },
    #     0.2,
    #     "123456789b",
    # ),
    #########################
    # Multiple migration procedure(One operationID in dependencies)
    #########################
    (
        {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                },
                {
                    "operationID": 2,
                    "operation": "start",
                    "targetCPUID": str(uuid4()),
                    "targetRequestInstanceID": str(uuid4()),
                    "dependencies": [1],
                },
                {
                    "operationID": 3,
                    "operation": "disconnect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [2],
                },
                {
                    "operationID": 4,
                    "operation": "connect",
                    "targetCPUID": str(uuid4()),
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [],
                },
                {
                    "operationID": 5,
                    "operation": "stop",
                    "targetCPUID": str(uuid4()),
                    "targetRequestInstanceID": str(uuid4()),
                    "dependencies": [4],
                },
                {
                    "operationID": 6,
                    "operation": "boot",
                    "targetDeviceID": str(uuid4()),
                    "dependencies": [5],
                },
            ]
        },
        0.3,
        "123456789c",
    ),
    # #########################
    # Multiple migration procedure(Multiple operationIDs in dependencies)
    # #########################
    # (
    #     {
    #         "procedures": [
    #             {
    #                 "operationID": 1,
    #                 "operation": "shutdown",
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #             {
    #                 "operationID": 2,
    #                 "operation": "disconnect",
    #                 "targetCPUID": str(uuid4()),
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #             {
    #                 "operationID": 3,
    #                 "operation": "connect",
    #                 "targetCPUID": str(uuid4()),
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #             {
    #                 "operationID": 4,
    #                 "operation": "boot",
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [1, 2, 3],
    #             },
    #         ]
    #     },
    #     0.4,
    #     "123456789d",
    # ),
    # #########################
    # Multiple migration procedure(The same operation is executed simultaneously)
    # #########################
    # (
    #     {
    #         "procedures": [
    #             {
    #                 "operationID": 1,
    #                 "operation": "shutdown",
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #             {
    #                 "operationID": 2,
    #                 "operation": "shutdown",
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #         ]
    #     },
    #     0.5,
    #     "123456789e",
    # ),
    # (
    #     {
    #         "procedures": [
    #             {
    #                 "operationID": 1,
    #                 "operation": "boot",
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #             {
    #                 "operationID": 2,
    #                 "operation": "boot",
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #         ]
    #     },
    #     0.6,
    #     "123456789f",
    # ),
    # (
    #     {
    #         "procedures": [
    #             {
    #                 "operationID": 1,
    #                 "operation": "connect",
    #                 "targetCPUID": str(uuid4()),
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #             {
    #                 "operationID": 2,
    #                 "operation": "connect",
    #                 "targetCPUID": str(uuid4()),
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #         ]
    #     },
    #     0.7,
    #     "123456789g",
    # ),
    # (
    #     {
    #         "procedures": [
    #             {
    #                 "operationID": 1,
    #                 "operation": "disconnect",
    #                 "targetCPUID": str(uuid4()),
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #             {
    #                 "operationID": 2,
    #                 "operation": "disconnect",
    #                 "targetCPUID": str(uuid4()),
    #                 "targetDeviceID": str(uuid4()),
    #                 "dependencies": [],
    #             },
    #         ]
    #     },
    #     0.8,
    #     "123456789h",
    # ),
]

proc_empty_pattern = [
    #########################
    # Empty migration procedure
    #########################
    (
        {"procedures": []},
        0.1,
    )
]
