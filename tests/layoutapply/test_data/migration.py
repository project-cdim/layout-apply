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

MIGRATION_API_RESP_DATA = [
    {
        "operationID": 1,
        "operation": "connect",
        "targetCPUID": "3B4EBEEA-B6DD-45DA-8C8A-2CA2F8F728D6",
        "targetDeviceID": "895DFB43-68CD-41D6-8996-EAC8D1EA1E3F",
        "dependencies": [],
    },
    {
        "operationID": 2,
        "operation": "boot",
        "targetDeviceID": "3B4EBEEA-B6DD-45DA-8C8A-2CA2F8F728D6",
        "dependencies": [1],
    },
]

CONF_NODES_API_RESP_DATA = {
    "count": 1,
    "nodes": [
        {
            "id": str(uuid4()),
            "resources": [
                {
                    "device": {
                        "deviceID": str(uuid4()),
                        "type": "cpu",
                        "status": {"state": "Normal", "health": "Normal"},
                    },
                    "resourceGroupIDs": [str(uuid4())],
                    "annotation": {"available": True},
                    "detected": True,
                }
            ],
        }
    ],
}

CONF_NODES_API_RESP_DATA_MULTIDEVICE = {
    "count": 1,
    "nodes": [
        {
            "id": str(uuid4()),
            "resources": [
                {
                    "device": {
                        "deviceID": str(uuid4()),
                        "type": "cpu",
                        "status": {"state": "Normal", "health": "Normal"},
                    },
                    "resourceGroupIDs": [str(uuid4())],
                    "annotation": {"available": True},
                    "detected": True,
                },
                {
                    "device": {
                        "deviceID": str(uuid4()),
                        "type": "memory",
                        "status": {"state": "Normal", "health": "Normal"},
                    },
                    "resourceGroupIDs": [str(uuid4())],
                    "annotation": {"available": True},
                    "detected": True,
                },
                {
                    "device": {
                        "deviceID": str(uuid4()),
                        "type": "storage",
                        "status": {"state": "Normal", "health": "Normal"},
                    },
                    "resourceGroupIDs": [str(uuid4())],
                    "annotation": {"available": True},
                    "detected": True,
                },
                {
                    "device": {
                        "deviceID": str(uuid4()),
                        "type": "storage",
                        "status": {"state": "Normal", "health": "Normal"},
                    },
                    "resourceGroupIDs": [str(uuid4())],
                    "annotation": {"available": True},
                    "detected": True,
                },
            ],
        },
        {
            "id": str(uuid4()),
            "resources": [
                {
                    "device": {
                        "deviceID": str(uuid4()),
                        "type": "cpu",
                        "status": {"state": "Normal", "health": "Normal"},
                    },
                    "resourceGroupIDs": [str(uuid4())],
                    "annotation": {"available": True},
                    "detected": True,
                },
                {
                    "device": {
                        "deviceID": str(uuid4()),
                        "type": "memory",
                        "status": {"state": "Normal", "health": "Normal"},
                    },
                    "resourceGroupIDs": [str(uuid4())],
                    "annotation": {"available": True},
                    "detected": True,
                },
            ],
        },
    ],
}

CONF_NODES_API_RESP_DATA_MULTIDEVICE_WITH_NODEID = {
    "count": 2,
    "nodes": [
        {
            "id": "b477ea1c-db3d-48b3-9725-b0ce6e25efc2",
            "resources": [
                {
                    "annotation": {"available": True},
                    "detected": True,
                    "device": {
                        "deviceID": "2eb602dc-e4c2-4064-b272-e409ad5c9b42",
                        "status": {"health": "Disabled", "state": "Enabled"},
                        "type": "networkInterface",
                    },
                    "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
                },
                {
                    "annotation": {"available": True},
                    "detected": True,
                    "device": {
                        "deviceID": "4ca84d71-22da-4faf-94d8-5e159397115b",
                        "status": {"health": "OK", "state": "InTest"},
                        "type": "memory",
                    },
                    "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
                },
                {
                    "annotation": {"available": True},
                    "detected": True,
                    "device": {
                        "deviceID": "7c6f9db2-5d35-4310-90f6-7e004ad2f35a",
                        "status": {"health": "OK", "state": "Starting"},
                        "type": "memory",
                    },
                    "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
                },
                {
                    "annotation": {"available": True},
                    "detected": True,
                    "device": {
                        "deviceID": "b477ea1c-db3d-48b3-9725-b0ce6e25efc2",
                        "status": {"health": "OK", "state": "Disabled"},
                        "type": "CPU",
                    },
                    "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
                },
                {
                    "annotation": {"available": True},
                    "detected": True,
                    "device": {
                        "deviceID": "e56a1a1c-0556-42ca-8cbb-7c6dc86561eb",
                        "status": {"health": "Critical", "state": "Enabled"},
                        "type": "storage",
                    },
                    "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
                },
                {
                    "annotation": {"available": True},
                    "detected": True,
                    "device": {
                        "deviceID": "e63fbe90-1b8f-44bd-9f66-ca3a9ce159b2",
                        "status": {"health": "Warning", "state": "Enabled"},
                        "type": "GPU",
                    },
                    "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
                },
            ],
        },
        {
            "id": "b9a1e642-da2e-403a-88f5-fa0eca0d9c52",
            "resources": [
                {
                    "annotation": {"available": True},
                    "detected": True,
                    "device": {
                        "deviceID": "0ca6a442-784d-47c7-ba0c-c4077953da48",
                        "status": {"health": "OK", "state": "Enabled"},
                        "type": "GPU",
                    },
                    "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
                },
                {
                    "annotation": {"available": True},
                    "detected": True,
                    "device": {
                        "deviceID": "54fd3675-8ad1-42d7-8d61-067dea3f446a",
                        "status": {"health": "OK", "state": "Enabled"},
                        "type": "memory",
                    },
                    "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
                },
                {
                    "annotation": {"available": True},
                    "detected": True,
                    "device": {
                        "deviceID": "98260b19-f7de-4461-b6e2-63bc60bd1783",
                        "status": {"health": "OK", "state": "Enabled"},
                        "type": "memory",
                    },
                    "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
                },
                {
                    "annotation": {"available": True},
                    "detected": True,
                    "device": {
                        "deviceID": "b9a1e642-da2e-403a-88f5-fa0eca0d9c52",
                        "status": {"health": "OK", "state": "Enabled"},
                        "type": "CPU",
                    },
                    "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
                },
                {
                    "annotation": {"available": True},
                    "detected": True,
                    "device": {
                        "deviceID": "bfac0e5a-f1b7-42eb-bc69-2e28b5c9f9f8",
                        "status": {"health": "OK", "state": "Enabled"},
                        "type": "networkInterface",
                    },
                    "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
                },
                {
                    "annotation": {"available": True},
                    "detected": True,
                    "device": {
                        "deviceID": "f843ae2c-4157-4469-9635-300fb04fdb7b",
                        "status": {"health": "OK", "state": "Enabled"},
                        "type": "storage",
                    },
                    "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
                },
            ],
        },
        {
            "id": str(uuid4()),
            "resources": [
                {
                    "device": {
                        "deviceID": str(uuid4()),
                        "type": "cpu",
                        "status": {"state": "Normal", "health": "Normal"},
                    },
                    "resourceGroupIDs": [str(uuid4())],
                    "annotation": {"available": True},
                    "detected": True,
                }
            ],
        },
    ],
}


MIGRATION_IN_DATA = {
    "desiredLayout": {
        "nodes": [
            {
                "device": {
                    "cpu": {"deviceIDs": ["3B4EBEEA-B6DD-45DA-8C8A-2CA2F8F728D6"]},
                    "memory": {"deviceIDs": ["A4D1A195-4A54-11EF-A1DC-000C29C8CA82"]},
                    "storage": {"deviceIDs": ["895DFB43-68CD-41D6-8996-EAC8D1EA1E3F"]},
                    "networkInterface": {"deviceIDs": ["5DFB4893-C16D-4968-89D6-8D1EAECEA31F"]},
                }
            },
            {
                "device": {
                    "cpu": {"deviceIDs": ["2CA6D4DF-2739-45BA-ACA4-6ABE93E81E15"]},
                    "memory": {"deviceIDs": ["035AA32D-6C3F-488E-9602-62286A509288"]},
                    "storage": {"deviceIDs": ["42243124-9655-4B12-B638-A15BFE021065"]},
                    "networkInterface": {"deviceIDs": ["0E9A2838-6AA9-40D2-B3E0-EA7B15E8F18D"]},
                }
            },
        ]
    },
}

MIGRATION_IN_DATA_WITH_TARGETNODEID = {
    "targetNodeIDs": ["b477ea1c-db3d-48b3-9725-b0ce6e25efc2"],
    "desiredLayout": {
        "nodes": [
            {
                "device": {
                    "cpu": {"deviceIDs": ["3B4EBEEA-B6DD-45DA-8C8A-2CA2F8F728D6"]},
                    "memory": {"deviceIDs": ["A4D1A195-4A54-11EF-A1DC-000C29C8CA82"]},
                    "storage": {"deviceIDs": ["895DFB43-68CD-41D6-8996-EAC8D1EA1E3F"]},
                    "networkInterface": {"deviceIDs": ["5DFB4893-C16D-4968-89D6-8D1EAECEA31F"]},
                }
            },
            {
                "device": {
                    "cpu": {"deviceIDs": ["2CA6D4DF-2739-45BA-ACA4-6ABE93E81E15"]},
                    "memory": {"deviceIDs": ["035AA32D-6C3F-488E-9602-62286A509288"]},
                    "storage": {"deviceIDs": ["42243124-9655-4B12-B638-A15BFE021065"]},
                    "networkInterface": {"deviceIDs": ["0E9A2838-6AA9-40D2-B3E0-EA7B15E8F18D"]},
                }
            },
        ]
    },
}

MIGRATION_IN_DATA_WITH_TARGETNODEID_MULTIPLE = {
    "targetNodeIDs": ["b477ea1c-db3d-48b3-9725-b0ce6e25efc2", "b9a1e642-da2e-403a-88f5-fa0eca0d9c52"],
    "desiredLayout": {
        "nodes": [
            {
                "device": {
                    "cpu": {"deviceIDs": ["3B4EBEEA-B6DD-45DA-8C8A-2CA2F8F728D6"]},
                    "memory": {"deviceIDs": ["A4D1A195-4A54-11EF-A1DC-000C29C8CA82"]},
                    "storage": {"deviceIDs": ["895DFB43-68CD-41D6-8996-EAC8D1EA1E3F"]},
                    "networkInterface": {"deviceIDs": ["5DFB4893-C16D-4968-89D6-8D1EAECEA31F"]},
                }
            },
            {
                "device": {
                    "cpu": {"deviceIDs": ["2CA6D4DF-2739-45BA-ACA4-6ABE93E81E15"]},
                    "memory": {"deviceIDs": ["035AA32D-6C3F-488E-9602-62286A509288"]},
                    "storage": {"deviceIDs": ["42243124-9655-4B12-B638-A15BFE021065"]},
                    "networkInterface": {"deviceIDs": ["0E9A2838-6AA9-40D2-B3E0-EA7B15E8F18D"]},
                }
            },
        ]
    },
}

MIGRATION_IN_DATA_WITH_TARGETNODEID_EMPTY = {
    "targetNodeIDs": [],
    "desiredLayout": {
        "nodes": [
            {
                "device": {
                    "cpu": {"deviceIDs": ["3B4EBEEA-B6DD-45DA-8C8A-2CA2F8F728D6"]},
                    "memory": {"deviceIDs": ["A4D1A195-4A54-11EF-A1DC-000C29C8CA82"]},
                    "storage": {"deviceIDs": ["895DFB43-68CD-41D6-8996-EAC8D1EA1E3F"]},
                    "networkInterface": {"deviceIDs": ["5DFB4893-C16D-4968-89D6-8D1EAECEA31F"]},
                }
            },
            {
                "device": {
                    "cpu": {"deviceIDs": ["2CA6D4DF-2739-45BA-ACA4-6ABE93E81E15"]},
                    "memory": {"deviceIDs": ["035AA32D-6C3F-488E-9602-62286A509288"]},
                    "storage": {"deviceIDs": ["42243124-9655-4B12-B638-A15BFE021065"]},
                    "networkInterface": {"deviceIDs": ["0E9A2838-6AA9-40D2-B3E0-EA7B15E8F18D"]},
                }
            },
        ]
    },
}

MIGRATION_IN_DATA_EMPTY = {"desiredLayout": {"nodes": []}}
MIGRATION_IN_DATA_WITH_TARGETNODEID_INVALID = {
    "targetNodeIDs": ["a477ea1c-db3d-48b3-9725-b0ce6e25efc1"],
    "desiredLayout": {"nodes": []},
}

GET_AVAILABLE_RESOURCES_API_RESP = {
    "count": 4,
    "resources": [
        {
            "annotation": {"available": True},
            "detected": True,
            "device": {
                "LTSSMState": "L0",
                "TDPWatts": 100,
                "baseSpeedMHz": 1200,
                "constraints": {
                    "nonRemovableDevices": [
                        {"deviceID": "ce89426d-cf11-4e84-8efa-c5145933a829"},
                        {"deviceID": "42e46154-ac4b-4ad6-a76e-300249e28186"},
                        {"deviceID": "cc464ed7-1dd3-4164-9a48-95d20f495ee8"},
                    ]
                },
                "deviceID": "00c9f066-eae2-4be0-bdd9-aac528d6416c",
                "infoTimestamp": "2025-01-29T04:09:58Z",
                "instructionSet": "x86-64",
                "links": [
                    {"deviceID": "ce89426d-cf11-4e84-8efa-c5145933a829", "type": "networkInterface"},
                    {"deviceID": "080a625d-7de8-4481-98b0-7125977eb205", "type": "storage"},
                    {"deviceID": "cc464ed7-1dd3-4164-9a48-95d20f495ee8", "type": "memory"},
                    {"deviceID": "683d448c-ef83-49e2-80a0-0745f765dcda", "type": "GPU"},
                    {"deviceID": "42e46154-ac4b-4ad6-a76e-300249e28186", "type": "memory"},
                    {"deviceID": "d7d3b33b-bb4f-44c9-844e-36e0a2746407", "type": "networkInterface"},
                ],
                "manufacturer": "Intel(R) Corporation",
                "memorySummary": {"ECCModeEnabled": True, "totalCacheSizeMiB": 4096, "totalMemorySizeMiB": 8192},
                "model": "cpu_2",
                "operatingSpeedMHz": 3200,
                "powerCapability": True,
                "powerState": "On",
                "processorArchitecture": "x86",
                "processorID": {
                    "effectiveFamily": "0x42",
                    "effectiveModel": "0x61",
                    "identificationRegister": "0x34AC34DC8901274A",
                    "microcodeInfo": "0x429943",
                    "protectedIdentificationNumber": "123456",
                    "step": "0x1",
                    "vendorID": "GenuineIntel",
                },
                "processorMemories": [{"capacityMiB": 4096, "integrated": True, "speedMHz": 1200, "type": "DDR"}],
                "serialNumber": "PROCESSOR4",
                "socketNum": 1,
                "status": {"health": "OK", "state": "Enabled"},
                "totalCores": 4,
                "totalEnabledCores": 4,
                "totalThreads": 8,
                "type": "CPU",
            },
            "nodeIDs": ["00c9f066-eae2-4be0-bdd9-aac528d6416c"],
            "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
        },
        {
            "annotation": {"available": True},
            "detected": True,
            "device": {
                "TDPWatts": 100,
                "deviceID": "ce89426d-cf11-4e84-8efa-c5145933a829",
                "type": "networkInterface",
            },
            "nodeIDs": ["ce89426d-cf11-4e84-8efa-c5145933a829"],
            "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
        },
        {
            "annotation": {"available": True},
            "detected": True,
            "device": {
                "deviceID": "42e46154-ac4b-4ad6-a76e-300249e28186",
                "links": [
                    {"deviceID": "065b9a5e-b1e5-4511-aee2-4929f0bf946c", "type": "memory"},
                    {"deviceID": "5e803aee-4734-41ce-aabd-abef3eb969f1", "type": "storage"},
                    {"deviceID": "c0a017fc-aa27-4dbd-a6db-f8ac4bef2b51", "type": "memory"},
                    {"deviceID": "c00ec7fa-10db-4683-be34-40e714ead004", "type": "GPU"},
                    {"deviceID": "88333d9a-20ff-4851-8e2d-dd5d19f628e7", "type": "networkInterface"},
                    {"deviceID": "eb9ff5b9-d6b6-4089-a98f-47212ad1cade", "type": "networkInterface"},
                ],
                "memorySummary": {"ECCModeEnabled": True, "totalCacheSizeMiB": 4096, "totalMemorySizeMiB": 8192},
                "powerCapability": True,
                "type": "memory",
            },
            "nodeIDs": ["42e46154-ac4b-4ad6-a76e-300249e28186"],
            "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
        },
        {
            "annotation": {"available": True},
            "detected": True,
            "device": {
                "deviceID": "cc464ed7-1dd3-4164-9a48-95d20f495ee8",
                "memorySummary": {"ECCModeEnabled": True, "totalCacheSizeMiB": 4096, "totalMemorySizeMiB": 8192},
                "powerCapability": True,
                "type": "memory",
            },
            "nodeIDs": ["cc464ed7-1dd3-4164-9a48-95d20f495ee8"],
            "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
        },
    ],
}


GET_AVAILABLE_RESOURCES_API_RESP_MULTI = {
    "count": 6,
    "resources": [
        {
            "annotation": {"available": True},
            "detected": True,
            "device": {
                "LTSSMState": "L0",
                "constraints": {
                    "nonRemovableDevices": [
                        {"deviceID": "ce89426d-cf11-4e84-8efa-c5145933a829"},
                    ]
                },
                "deviceID": "00c9f066-eae2-4be0-bdd9-aac528d6416c",
                "type": "CPU",
            },
            "nodeIDs": ["00c9f066-eae2-4be0-bdd9-aac528d6416c"],
            "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
        },
        {
            "annotation": {"available": True},
            "detected": True,
            "device": {
                "TDPWatts": 100,
                "deviceID": "ce89426d-cf11-4e84-8efa-c5145933a829",
                "type": "networkInterface",
            },
            "nodeIDs": ["ce89426d-cf11-4e84-8efa-c5145933a829"],
            "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
        },
        {
            "annotation": {"available": True},
            "detected": True,
            "device": {
                "deviceID": "42e46154-ac4b-4ad6-a76e-300249e28186",
                "constraints": {
                    "nonRemovableDevices": [
                        {"deviceID": "33c9f066-eae2-4be0-bdd9-aac528d64199"},
                    ]
                },
                "links": [
                    {"deviceID": "065b9a5e-b1e5-4511-aee2-4929f0bf946c", "type": "memory"},
                    {"deviceID": "5e803aee-4734-41ce-aabd-abef3eb969f1", "type": "storage"},
                    {"deviceID": "c0a017fc-aa27-4dbd-a6db-f8ac4bef2b51", "type": "memory"},
                    {"deviceID": "c00ec7fa-10db-4683-be34-40e714ead004", "type": "GPU"},
                    {"deviceID": "88333d9a-20ff-4851-8e2d-dd5d19f628e7", "type": "networkInterface"},
                    {"deviceID": "eb9ff5b9-d6b6-4089-a98f-47212ad1cade", "type": "networkInterface"},
                ],
                "memorySummary": {"ECCModeEnabled": True, "totalCacheSizeMiB": 4096, "totalMemorySizeMiB": 8192},
                "powerCapability": True,
                "type": "memory",
            },
            "nodeIDs": ["42e46154-ac4b-4ad6-a76e-300249e28186"],
            "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
        },
        {
            "annotation": {"available": True},
            "detected": True,
            "device": {
                "LTSSMState": "L0",
                "constraints": {
                    "nonRemovableDevices": [
                        {"deviceID": "42e46154-ac4b-4ad6-a76e-300249e28186"},
                    ]
                },
                "deviceID": "33c9f066-eae2-4be0-bdd9-aac528d64199",
                "type": "CPU",
            },
            "nodeIDs": ["33c9f066-eae2-4be0-bdd9-aac528d64199"],
            "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
        },
        {
            "annotation": {"available": True},
            "detected": True,
            "device": {
                "deviceID": "12e46154-ac4b-4ad6-a76e-300249e28134",
                "constraints": {
                    "nonRemovableDevices": [
                        {"deviceID": "bbc9f066-eae2-4be0-bdd9-aac528d641cc"},
                    ]
                },
                "links": [
                    {"deviceID": "065b9a5e-b1e5-4511-aee2-4929f0bf946c", "type": "memory"},
                    {"deviceID": "5e803aee-4734-41ce-aabd-abef3eb969f1", "type": "storage"},
                    {"deviceID": "c0a017fc-aa27-4dbd-a6db-f8ac4bef2b51", "type": "memory"},
                    {"deviceID": "c00ec7fa-10db-4683-be34-40e714ead004", "type": "GPU"},
                    {"deviceID": "88333d9a-20ff-4851-8e2d-dd5d19f628e7", "type": "networkInterface"},
                    {"deviceID": "eb9ff5b9-d6b6-4089-a98f-47212ad1cade", "type": "networkInterface"},
                ],
                "memorySummary": {"ECCModeEnabled": True, "totalCacheSizeMiB": 4096, "totalMemorySizeMiB": 8192},
                "powerCapability": True,
                "type": "memory",
            },
            "nodeIDs": ["12e46154-ac4b-4ad6-a76e-300249e28134"],
            "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
        },
        {
            "annotation": {"available": True},
            "detected": True,
            "device": {
                "LTSSMState": "L0",
                "constraints": {
                    "nonRemovableDevices": [
                        {"deviceID": "12e46154-ac4b-4ad6-a76e-300249e28134"},
                    ]
                },
                "deviceID": "bbc9f066-eae2-4be0-bdd9-aac528d641cc",
                "type": "memory",
            },
            "nodeIDs": ["bbc9f066-eae2-4be0-bdd9-aac528d641cc"],
            "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
        },
    ],
}

NOTHING_NON_REMOVABLE_DEVICES_RESP = {
    "count": 1,
    "resources": [
        {
            "annotation": {"available": True},
            "detected": True,
            "device": {
                "LTSSMState": "L0",
                "deviceID": "00c9f066-eae2-4be0-bdd9-aac528d6416c",
                "type": "CPU",
            },
            "nodeIDs": ["00c9f066-eae2-4be0-bdd9-aac528d6416c"],
            "resourceGroupIDs": ["00000000-0000-7000-8000-000000000000"],
        }
    ],
}
