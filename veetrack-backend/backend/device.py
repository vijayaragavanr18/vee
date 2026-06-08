import torch

def get_device() -> str:
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"[VeeTrack] GPU: {name} ({vram:.1f}GB VRAM)")
        return "cuda"
    print("[VeeTrack] No GPU found — using CPU")
    return "cpu"

DEVICE = get_device()
