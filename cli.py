"""CLI entry point for tack_comfyui_start_tool."""
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path when invoked directly under the
# embeddable Python (safe_path=1 suppresses the default script-dir entry).
_root_str = str(Path(__file__).resolve().parent)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

import click
from rich.console import Console

from src.utils.fs_ops import load_config

def _get_version():
    vf = Path(__file__).parent / "VERSION.json"
    if vf.exists():
        with open(vf, "r", encoding="utf-8") as f:
            return json.load(f).get("version", "0.0.0")
    return "0.0.0"
from src.core.env_manager import EnvManager
from src.core.snapshot_manager import SnapshotManager
from src.core.version_controller import VersionController
from src.core.comfyui_launcher import ComfyUILauncher
from src.core.conflict_analyzer import ConflictAnalyzer

console = Console()


@click.group()
@click.version_option(version=_get_version(), prog_name="tack_comfyui_start_tool")
@click.option("--config", default="config.json", help="Path to config file.")
@click.pass_context
def cli(ctx, config):
    """tack_comfyui_start_tool - ComfyUI Environment Manager"""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    try:
        from src.core.migrations import migrate_env_meta_0_4_0
        _cfg = load_config(config)
        migrate_env_meta_0_4_0(_cfg)
    except Exception as _exc:
        import logging as _logging
        _logging.getLogger(__name__).warning("0.4.0 migration failed: %s", _exc)


# --- env group ---

@cli.group()
@click.pass_context
def env(ctx):
    """Manage ComfyUI environments."""
    pass


@env.command("list")
@click.pass_context
def env_list(ctx):
    """List all environments."""
    config = load_config(ctx.obj["config_path"])
    manager = EnvManager(config)
    envs = manager.list_environments()
    if not envs:
        console.print("No environments found.")
        return
    from rich.table import Table
    table = Table(title="Environments")
    table.add_column("Name", style="cyan")
    table.add_column("Branch")
    table.add_column("Commit")
    table.add_column("Sandbox")
    table.add_column("Created")
    for e in envs:
        table.add_row(
            e.name, e.comfyui_branch, e.comfyui_commit[:7],
            "Yes" if e.is_sandbox else "", e.created_at[:10],
        )
    console.print(table)


@env.command("create")
@click.argument("name")
@click.option("--branch", default="master", help="ComfyUI branch to clone.")
@click.option("--commit", default=None, help="Specific commit to checkout.")
@click.option("--tag", default=None, help="Install from a specific tag (e.g. v0.3.4)")
@click.pass_context
def env_create(ctx, name, branch, commit, tag):
    """Create a new environment."""
    config = load_config(ctx.obj["config_path"])
    manager = EnvManager(config)
    if tag:
        branch = tag
        commit = tag
    try:
        console.print(f"[bold]Creating environment '{name}'...[/bold]")
        env = manager.create_environment(name, branch=branch, commit=commit)
        console.print(f"[green]Environment '{env.name}' created successfully.[/green]")
        console.print(f"  ComfyUI: {env.comfyui_branch} @ {env.comfyui_commit[:7]}")
        console.print(f"  Python:  {env.python_version}")
    except (ValueError, FileExistsError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Failed to create environment: {e}[/red]")
        raise SystemExit(1)


@env.command("delete")
@click.argument("name")
@click.option("--force", is_flag=True, help="Skip confirmation.")
@click.pass_context
def env_delete(ctx, name, force):
    """Delete an environment."""
    config = load_config(ctx.obj["config_path"])
    manager = EnvManager(config)
    if not force:
        click.confirm(f"Delete environment '{name}'?", abort=True)
    try:
        manager.delete_environment(name, force=force)
        console.print(f"[green]Environment '{name}' deleted.[/green]")
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@env.command("clone")
@click.argument("source")
@click.argument("new_name")
@click.option("--sandbox/--no-sandbox", default=True, help="Mark as sandbox.")
@click.pass_context
def env_clone(ctx, source, new_name, sandbox):
    """Clone an environment."""
    config = load_config(ctx.obj["config_path"])
    manager = EnvManager(config)
    try:
        console.print(f"[bold]Cloning '{source}' to '{new_name}'...[/bold]")
        env = manager.clone_environment(source, new_name, as_sandbox=sandbox)
        console.print(f"[green]Environment '{new_name}' cloned from '{source}'.[/green]")
        console.print(f"  Sandbox: {env.is_sandbox}")
    except (ValueError, FileExistsError, FileNotFoundError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@env.command("info")
@click.argument("name")
@click.pass_context
def env_info(ctx, name):
    """Show environment details."""
    config = load_config(ctx.obj["config_path"])
    manager = EnvManager(config)
    try:
        env = manager.get_environment(name)
        console.print(f"[bold]{env.name}[/bold]")
        console.print(f"  Branch:    {env.comfyui_branch}")
        console.print(f"  Commit:    {env.comfyui_commit}")
        console.print(f"  Python:    {env.python_version}")
        console.print(f"  Sandbox:   {env.is_sandbox}")
        console.print(f"  Parent:    {env.parent_env or 'N/A'}")
        console.print(f"  Created:   {env.created_at}")
        console.print(f"  Snapshots: {len(env.snapshots)}")
        console.print(f"  Packages:  {len(env.pip_freeze)}")
    except FileNotFoundError:
        console.print(f"[red]Environment '{name}' not found.[/red]")
        raise SystemExit(1)


@env.command("merge")
@click.argument("source")
@click.argument("target")
@click.option("--strategy", type=click.Choice(["add", "replace"]), default="add", help="Merge strategy.")
@click.pass_context
def env_merge(ctx, source, target, strategy):
    """Merge changes from source into target environment."""
    config = load_config(ctx.obj["config_path"])
    manager = EnvManager(config)
    click.confirm(f"Merge '{source}' into '{target}' ({strategy} strategy)?", abort=True)
    try:
        result = manager.merge_env(source, target, strategy=strategy)
        console.print(f"[green]Merge complete.[/green]")
        if result["new_packages"]:
            console.print(f"  New packages: {', '.join(result['new_packages'].keys())}")
        if result["changed_packages"]:
            console.print(f"  Changed packages: {', '.join(result['changed_packages'].keys())}")
        if result["new_nodes"]:
            console.print(f"  New nodes: {', '.join(result['new_nodes'])}")
        if not any(result.values()):
            console.print("  No differences found.")
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@env.command("analyze")
@click.argument("env_name")
@click.argument("node_path")
@click.option("--output", type=click.Choice(["table", "json"]), default="table")
@click.pass_context
def env_analyze(ctx, env_name, node_path, output):
    """Analyze a plugin for dependency conflicts."""
    config = load_config(ctx.obj["config_path"])
    analyzer = ConflictAnalyzer(config)
    try:
        report = analyzer.analyze(env_name, node_path)
        if output == "json":
            import json as _json
            console.print(_json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        else:
            risk_colors = {
                "GREEN": "green", "YELLOW": "yellow",
                "HIGH": "red", "CRITICAL": "magenta",
            }
            color = risk_colors.get(report.risk_level.value, "white")
            console.print(
                f"\n[bold {color}]Risk Level: {report.risk_level.value}[/bold {color}]"
            )
            console.print(f"Plugin: {report.plugin_name}")
            console.print(f"Summary: {report.summary}")
            if report.conflicts:
                from rich.table import Table
                table = Table(title="Conflicts")
                table.add_column("Package", style="cyan")
                table.add_column("Current")
                table.add_column("New")
                table.add_column("Type")
                table.add_column("Critical")
                table.add_column("Risk")
                for c in report.conflicts:
                    table.add_row(
                        c.package, c.current_version, c.resolved_version,
                        c.change_type, "!" if c.is_critical else "",
                        c.risk_level.value,
                    )
                console.print(table)
            for rec in report.recommendations:
                console.print(f"  -> {rec}")
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@env.command("rescan")
@click.option("--force", is_flag=True, help="Force yaml regeneration for all enabled environments.")
@click.pass_context
def env_rescan(ctx, force):
    """Rescan shared and environment model folders for new subdirectories."""
    config = load_config(ctx.obj["config_path"])
    manager = EnvManager(config)
    manager.ensure_shared_models_if_safe()
    result = manager.sync_shared_model_subdirs(force_regen=force)
    if result["skipped"]:
        console.print(f"[yellow]Rescan skipped: {result['reason']}[/yellow]")
        return
    if result["added"]:
        console.print(
            f"[green]Found {len(result['added'])} new subdir(s):[/green] "
            f"{', '.join(result['added'])}"
        )
    else:
        console.print("[dim]No new subdirs discovered.[/dim]")
    if result["synced_envs"]:
        console.print(f"[green]Regenerated yaml for {result['synced_envs']} environment(s).[/green]")


# --- snapshot group ---

@cli.group()
@click.pass_context
def snapshot(ctx):
    """Manage environment snapshots."""
    pass


@snapshot.command("create")
@click.argument("env_name")
@click.option("--reason", default="manual", help="Reason for snapshot.")
@click.pass_context
def snapshot_create(ctx, env_name, reason):
    """Create a snapshot of an environment."""
    config = load_config(ctx.obj["config_path"])
    mgr = SnapshotManager(config)
    try:
        snap = mgr.create_snapshot(env_name, trigger=reason)
        console.print(f"[green]Snapshot '{snap.id}' created for '{env_name}'.[/green]")
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@snapshot.command("list")
@click.argument("env_name")
@click.pass_context
def snapshot_list(ctx, env_name):
    """List snapshots for an environment."""
    config = load_config(ctx.obj["config_path"])
    mgr = SnapshotManager(config)
    snaps = mgr.list_snapshots(env_name)
    if not snaps:
        console.print(f"No snapshots for '{env_name}'.")
        return
    from rich.table import Table
    table = Table(title=f"Snapshots for '{env_name}'")
    table.add_column("ID", style="cyan")
    table.add_column("Trigger")
    table.add_column("Commit")
    table.add_column("Created")
    for s in snaps:
        table.add_row(s.id, s.trigger, s.comfyui_commit[:7], s.created_at[:19])
    console.print(table)


@snapshot.command("restore")
@click.argument("env_name")
@click.argument("snapshot_id")
@click.pass_context
def snapshot_restore(ctx, env_name, snapshot_id):
    """Restore an environment from a snapshot."""
    config = load_config(ctx.obj["config_path"])
    mgr = SnapshotManager(config)
    click.confirm(f"Restore '{env_name}' from '{snapshot_id}'?", abort=True)
    try:
        mgr.restore_snapshot(env_name, snapshot_id)
        console.print(f"[green]Environment '{env_name}' restored from '{snapshot_id}'.[/green]")
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


# --- version group ---

@cli.group()
@click.pass_context
def version(ctx):
    """Manage ComfyUI versions."""
    pass


@version.command("list-commits")
@click.argument("env_name")
@click.option("--count", default=20, help="Number of commits to show.")
@click.pass_context
def version_list_commits(ctx, env_name, count):
    """List recent commits."""
    config = load_config(ctx.obj["config_path"])
    vc = VersionController(config)
    try:
        commits = vc.list_commits(env_name, count=count)
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    if not commits:
        console.print(f"No commits found for '{env_name}'.")
        return
    from rich.table import Table
    table = Table(title=f"Commits for '{env_name}'")
    table.add_column("Hash", style="cyan")
    table.add_column("Message")
    table.add_column("Author")
    table.add_column("Date")
    for c in commits:
        table.add_row(c["hash"][:7], c["message"][:60], c["author"], c["date"][:10])
    console.print(table)


@version.command("switch")
@click.argument("env_name")
@click.argument("ref")
@click.pass_context
def version_switch(ctx, env_name, ref):
    """Switch to a specific version."""
    config = load_config(ctx.obj["config_path"])
    vc = VersionController(config)
    try:
        console.print(f"[bold]Switching '{env_name}' to '{ref}'...[/bold]")
        vc.switch_version(env_name, ref)
        console.print(f"[green]Switched '{env_name}' to '{ref}'.[/green]")
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Failed to switch version: {e}[/red]")
        raise SystemExit(1)


@version.command("list-tags")
@click.option("--url", default=None, help="Custom repo URL (default: config comfyui_repo_url)")
@click.pass_context
def list_tags(ctx, url):
    """List available tags from remote ComfyUI repository."""
    config = load_config(ctx.obj["config_path"])
    controller = VersionController(config)
    try:
        versions = controller.list_remote_versions(repo_url=url)
        from rich.table import Table
        table = Table(title="Available Tags")
        table.add_column("Tag", style="cyan")
        table.add_column("Hash", style="dim")
        for tag in versions["tags"]:
            table.add_row(tag["name"], tag["hash"])
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


@version.command("list-branches")
@click.option("--url", default=None, help="Custom repo URL (default: config comfyui_repo_url)")
@click.pass_context
def list_branches_cmd(ctx, url):
    """List available branches from remote ComfyUI repository."""
    config = load_config(ctx.obj["config_path"])
    controller = VersionController(config)
    try:
        versions = controller.list_remote_versions(repo_url=url)
        from rich.table import Table
        table = Table(title="Available Branches")
        table.add_column("Branch", style="cyan")
        for branch in versions["branches"]:
            table.add_row(branch)
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


@version.command("update")
@click.argument("env_name")
@click.pass_context
def version_update(ctx, env_name):
    """Update to latest version."""
    config = load_config(ctx.obj["config_path"])
    vc = VersionController(config)
    try:
        console.print(f"[bold]Updating '{env_name}' to latest...[/bold]")
        vc.update_comfyui(env_name)
        console.print(f"[green]'{env_name}' updated to latest.[/green]")
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Failed to update: {e}[/red]")
        raise SystemExit(1)


# --- launch group ---

@cli.group()
@click.pass_context
def launch(ctx):
    """Launch and manage ComfyUI instances."""
    pass


@launch.command("start")
@click.argument("env_name")
@click.option("--port", default=8188, help="Port number.")
@click.pass_context
def launch_start(ctx, env_name, port):
    """Start ComfyUI in an environment."""
    config = load_config(ctx.obj["config_path"])
    launcher = ComfyUILauncher(config)
    try:
        result = launcher.start(env_name, port=port)
        console.print(f"[green]ComfyUI started in '{env_name}'.[/green]")
        console.print(f"  PID:  {result['pid']}")
        console.print(f"  Port: {result['port']}")
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Failed to start ComfyUI: {e}[/red]")
        raise SystemExit(1)


@launch.command("stop")
@click.argument("env_name")
@click.pass_context
def launch_stop(ctx, env_name):
    """Stop a running ComfyUI instance."""
    config = load_config(ctx.obj["config_path"])
    launcher = ComfyUILauncher(config)
    try:
        launcher.stop(env_name)
        console.print(f"[green]ComfyUI stopped in '{env_name}'.[/green]")
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@launch.command("status")
@click.pass_context
def launch_status(ctx):
    """Show running ComfyUI instances."""
    config = load_config(ctx.obj["config_path"])
    launcher = ComfyUILauncher(config)
    instances = launcher.list_running()
    if not instances:
        console.print("No running ComfyUI instances.")
        return
    from rich.table import Table
    table = Table(title="Running ComfyUI Instances")
    table.add_column("Environment", style="cyan")
    table.add_column("PID")
    table.add_column("Port")
    for inst in instances:
        table.add_row(inst["env_name"], str(inst["pid"]), str(inst["port"]))
    console.print(table)


if __name__ == "__main__":
    cli()
