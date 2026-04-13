"""Launch configuration: build CLI args from launch_settings dict."""
import shlex

# Cross Attention option → CLI arg mapping
_CROSS_ATTENTION_MAP = {
    "pytorch": "--use-pytorch-cross-attention",
    "split": "--use-split-cross-attention",
    "quad": "--use-quad-cross-attention",
    "sage": "--use-sage-attention",
    "flash": "--use-flash-attention",
    "disable_xformers": "--disable-xformers",
}

# VRAM mode → CLI arg mapping
_VRAM_MODE_MAP = {
    "gpu_only": "--gpu-only",
    "high": "--highvram",
    "normal": "--normalvram",
    "low": "--lowvram",
    "no": "--novram",
    "cpu": "--cpu",
}


def build_launch_args(settings: dict) -> list:
    """Build CLI arg list from launch_settings dict.

    EXCLUDED args (handled by launcher.start() parameters directly):
    - --port: passed as launcher.start(port=...)
    - --auto-launch: mapped to launcher.start(auto_open=...)
    Port and auto_launch are extracted via extract_launch_params() instead.
    """
    args = []

    # Cross Attention (mutually exclusive)
    cross_attn = settings.get("cross_attention", "auto")
    if cross_attn in _CROSS_ATTENTION_MAP:
        args.append(_CROSS_ATTENTION_MAP[cross_attn])

    # VRAM mode (mutually exclusive) — skip "normal" as it's the default
    vram_mode = settings.get("vram_mode", "normal")
    if vram_mode != "normal" and vram_mode in _VRAM_MODE_MAP:
        args.append(_VRAM_MODE_MAP[vram_mode])

    # Reserve VRAM
    reserve = settings.get("reserve_vram")
    if reserve is not None:
        try:
            val = float(reserve)
            if val > 0:
                args.extend(["--reserve-vram", str(val)])
        except (ValueError, TypeError):
            pass

    # Async offload
    async_offload = settings.get("async_offload", "auto")
    if async_offload == "enable":
        args.append("--async-offload")
    elif async_offload == "disable":
        args.append("--disable-async-offload")

    # Smart memory
    if not settings.get("smart_memory", True):
        args.append("--disable-smart-memory")

    # Listen: only emit --listen when the toggle is on.
    # Empty/whitespace IP defaults to 0.0.0.0 so "enabled + blank" means "all interfaces".
    if settings.get("listen_enabled"):
        ip = (settings.get("listen") or "").strip() or "0.0.0.0"
        args.extend(["--listen", ip])

    # CORS
    cors = settings.get("cors_origin", "")
    if cors:
        args.extend(["--enable-cors-header", cors])

    # TLS
    tls_key = settings.get("tls_keyfile", "")
    tls_cert = settings.get("tls_certfile", "")
    if tls_key:
        args.extend(["--tls-keyfile", tls_key])
    if tls_cert:
        args.extend(["--tls-certfile", tls_cert])

    # Custom args — appended last, raw
    custom = settings.get("custom_args", "")
    if custom and custom.strip():
        try:
            args.extend(shlex.split(custom))
        except ValueError:
            # Fallback: split on whitespace if shlex fails (unmatched quotes)
            args.extend(custom.split())

    return args


def extract_launch_params(settings: dict) -> dict:
    """Extract parameters that are passed directly to launcher.start(),
    NOT as CLI args. These are excluded from build_launch_args().
    """
    return {
        "port": int(settings.get("port", 8188)),
        "auto_open": bool(settings.get("auto_launch", True)),
    }
