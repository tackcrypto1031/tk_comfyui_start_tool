from src.core.addons import ADDONS, find_addon, Addon


def test_registry_has_expected_ids():
    ids = {a.id for a in ADDONS}
    assert ids == {
        "sage-attention", "flash-attention", "insightface",
        "nunchaku", "trellis2",
    }


def test_find_existing():
    addon = find_addon("sage-attention")
    assert addon is not None
    assert addon.requires_compile is True


def test_find_missing():
    assert find_addon("ghost") is None


def test_pip_package_addon_has_no_repo():
    insight = find_addon("insightface")
    assert insight.install_method == "pip_package"
    assert insight.repo is None
    assert insight.pip_package == "insightface"


def test_git_clone_addon_has_repo_and_post_install():
    sage = find_addon("sage-attention")
    assert sage.install_method == "git_clone"
    assert sage.repo
    assert sage.post_install_cmd == ["pip", "install", "-e", "."]
