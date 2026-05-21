GPU_PROFILE = {
    "NVIDIA": {
        "device_key": "NVIDIA/GPU",
        "resource_name": "nvidia.com/gpu",
        "deploy_type": "NvidiaInfer",
        "package": "mtworkflow_x86.zip",
        "workdir": "mtworkflow_x86",
        "image": "nvidia/cuda:11.6.2-cudnn8-devel-ubuntu20.04_v1",
    },
    "Huawei": {
        "device_key": "Huawei/Ascend310P",
        "resource_name": "huawei.com/Ascend310P",
        "deploy_type": "HuaweiInfer",
        "package": "mtworkflow_arm.zip",
        "workdir": "mtworkflow_arm",
        "image": "ascend-ubuntu20.04-8.1.rc1",
    },
}


def get_gpu_profile(vendor: str) -> dict:
    return GPU_PROFILE[vendor]
