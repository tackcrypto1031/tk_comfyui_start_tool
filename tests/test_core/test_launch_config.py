"""Tests for src/core/launch_config.py"""
import pytest
from src.core.launch_config import build_launch_args, extract_launch_params
from src.models.environment import LAUNCH_SETTINGS_DEFAULTS


class TestBuildLaunchArgs:
    """Test CLI arg generation from launch_settings."""

    def test_defaults_produce_empty_args(self):
        """All defaults should produce no extra CLI args."""
        args = build_launch_args(dict(LAUNCH_SETTINGS_DEFAULTS))
        assert args == []

    def test_cross_attention_pytorch(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "cross_attention": "pytorch"}
        assert "--use-pytorch-cross-attention" in build_launch_args(s)

    def test_cross_attention_split(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "cross_attention": "split"}
        assert "--use-split-cross-attention" in build_launch_args(s)

    def test_cross_attention_quad(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "cross_attention": "quad"}
        assert "--use-quad-cross-attention" in build_launch_args(s)

    def test_cross_attention_sage(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "cross_attention": "sage"}
        assert "--use-sage-attention" in build_launch_args(s)

    def test_cross_attention_flash(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "cross_attention": "flash"}
        assert "--use-flash-attention" in build_launch_args(s)

    def test_cross_attention_disable_xformers(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "cross_attention": "disable_xformers"}
        assert "--disable-xformers" in build_launch_args(s)

    def test_cross_attention_auto_no_arg(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "cross_attention": "auto"}
        args = build_launch_args(s)
        attn_args = [a for a in args if "attention" in a or "xformers" in a]
        assert attn_args == []

    def test_vram_mode_low(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "vram_mode": "low"}
        assert "--lowvram" in build_launch_args(s)

    def test_vram_mode_high(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "vram_mode": "high"}
        assert "--highvram" in build_launch_args(s)

    def test_vram_mode_gpu_only(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "vram_mode": "gpu_only"}
        assert "--gpu-only" in build_launch_args(s)

    def test_vram_mode_no(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "vram_mode": "no"}
        assert "--novram" in build_launch_args(s)

    def test_vram_mode_cpu(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "vram_mode": "cpu"}
        assert "--cpu" in build_launch_args(s)

    def test_vram_mode_normal_no_arg(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "vram_mode": "normal"}
        args = build_launch_args(s)
        vram_args = [a for a in args if "vram" in a.lower() or a in ("--cpu",)]
        assert vram_args == []

    def test_reserve_vram(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "reserve_vram": 2.5}
        args = build_launch_args(s)
        assert "--reserve-vram" in args
        idx = args.index("--reserve-vram")
        assert args[idx + 1] == "2.5"

    def test_reserve_vram_none_no_arg(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "reserve_vram": None}
        assert "--reserve-vram" not in build_launch_args(s)

    def test_reserve_vram_zero_no_arg(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "reserve_vram": 0}
        assert "--reserve-vram" not in build_launch_args(s)

    def test_async_offload_enable(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "async_offload": "enable"}
        assert "--async-offload" in build_launch_args(s)

    def test_async_offload_disable(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "async_offload": "disable"}
        assert "--disable-async-offload" in build_launch_args(s)

    def test_async_offload_auto_no_arg(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "async_offload": "auto"}
        args = build_launch_args(s)
        assert "--async-offload" not in args
        assert "--disable-async-offload" not in args

    def test_smart_memory_disabled(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "smart_memory": False}
        assert "--disable-smart-memory" in build_launch_args(s)

    def test_smart_memory_enabled_no_arg(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "smart_memory": True}
        assert "--disable-smart-memory" not in build_launch_args(s)

    def test_listen_ip(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "listen_enabled": True, "listen": "0.0.0.0"}
        args = build_launch_args(s)
        assert "--listen" in args
        idx = args.index("--listen")
        assert args[idx + 1] == "0.0.0.0"

    def test_listen_empty_no_arg(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "listen": ""}
        assert "--listen" not in build_launch_args(s)

    def test_cors_origin(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "cors_origin": "*"}
        args = build_launch_args(s)
        assert "--enable-cors-header" in args
        idx = args.index("--enable-cors-header")
        assert args[idx + 1] == "*"

    def test_tls_files(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "tls_keyfile": "key.pem", "tls_certfile": "cert.pem"}
        args = build_launch_args(s)
        assert "--tls-keyfile" in args
        assert "--tls-certfile" in args

    def test_custom_args(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "custom_args": "--force-fp16 --deterministic"}
        args = build_launch_args(s)
        assert "--force-fp16" in args
        assert "--deterministic" in args

    def test_custom_args_with_quotes(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "custom_args": '--output-directory "/my path/out"'}
        args = build_launch_args(s)
        assert "--output-directory" in args
        assert "/my path/out" in args

    def test_custom_args_empty_no_arg(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "custom_args": ""}
        assert build_launch_args(s) == []

    # ── CRITICAL: Excluded args ──

    def test_no_port_in_args(self):
        """build_launch_args must NEVER emit --port (handled by launcher.start parameter)."""
        s = {**LAUNCH_SETTINGS_DEFAULTS, "port": 9999}
        args = build_launch_args(s)
        assert "--port" not in args

    def test_no_auto_launch_in_args(self):
        """build_launch_args must NEVER emit --auto-launch (handled by launcher.start auto_open)."""
        s = {**LAUNCH_SETTINGS_DEFAULTS, "auto_launch": True}
        args = build_launch_args(s)
        assert "--auto-launch" not in args

    def test_no_auto_launch_false_in_args(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "auto_launch": False}
        args = build_launch_args(s)
        assert "--auto-launch" not in args

    # ── Combined settings ──

    def test_multiple_settings_combined(self):
        s = {
            **LAUNCH_SETTINGS_DEFAULTS,
            "cross_attention": "flash",
            "vram_mode": "low",
            "smart_memory": False,
            "listen_enabled": True,
            "listen": "0.0.0.0",
            "custom_args": "--force-fp16",
        }
        args = build_launch_args(s)
        assert "--use-flash-attention" in args
        assert "--lowvram" in args
        assert "--disable-smart-memory" in args
        assert "--listen" in args
        assert "--force-fp16" in args
        # custom_args should be last
        assert args[-1] == "--force-fp16"


class TestExtractLaunchParams:
    """Test parameter extraction for launcher.start()."""

    def test_default_port(self):
        params = extract_launch_params(LAUNCH_SETTINGS_DEFAULTS)
        assert params["port"] == 8188

    def test_custom_port(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "port": 9090}
        params = extract_launch_params(s)
        assert params["port"] == 9090

    def test_auto_open_true(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "auto_launch": True}
        params = extract_launch_params(s)
        assert params["auto_open"] is True

    def test_auto_open_false(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "auto_launch": False}
        params = extract_launch_params(s)
        assert params["auto_open"] is False


class TestBackwardCompatibility:
    """Test that old environments without launch_settings work correctly."""

    def test_empty_settings_use_defaults(self):
        """An empty dict (old env) should produce no extra args."""
        merged = {**LAUNCH_SETTINGS_DEFAULTS, **{}}
        args = build_launch_args(merged)
        assert args == []

    def test_partial_settings_merge(self):
        """Partial settings should merge with defaults."""
        partial = {"cross_attention": "split"}
        merged = {**LAUNCH_SETTINGS_DEFAULTS, **partial}
        args = build_launch_args(merged)
        assert "--use-split-cross-attention" in args
        # Other defaults should not produce args
        assert "--port" not in args
        assert "--lowvram" not in args

    def test_listen_disabled_emits_nothing(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "listen_enabled": False, "listen": "192.168.1.5"}
        args = build_launch_args(s)
        assert "--listen" not in args

    def test_listen_enabled_empty_ip_defaults_to_0000(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "listen_enabled": True, "listen": ""}
        args = build_launch_args(s)
        assert args[args.index("--listen") + 1] == "0.0.0.0"

    def test_listen_enabled_respects_explicit_ip(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "listen_enabled": True, "listen": "192.168.1.5"}
        args = build_launch_args(s)
        assert args[args.index("--listen") + 1] == "192.168.1.5"

    def test_listen_enabled_whitespace_ip_defaults_to_0000(self):
        s = {**LAUNCH_SETTINGS_DEFAULTS, "listen_enabled": True, "listen": "   "}
        args = build_launch_args(s)
        assert args[args.index("--listen") + 1] == "0.0.0.0"
