# src/formix/cli/main.py
import asyncio
import json
import signal
import sys
from datetime import UTC, datetime, timedelta
from typing import Annotated

import aiosqlite
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from ..core.node import NodeManager, HeavyNode, LightNode
from ..db.database import NetworkDatabase, NodeDatabase
from ..utils.config import FORMIX_HOME, setup_logging
from ..utils.helpers import generate_uid

# Initialize console
console = Console()

# Setup logging
setup_logging()


def get_or_create_event_loop():
    """Get the current event loop or create a new one."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


async def create_new_node(node_type: str | None = None, background: bool = True):
    """Create a new node in the network."""
    console.print(Panel("[bold cyan]Create New Node[/bold cyan]"))

    # Prompt for node type if not provided
    if node_type is None:
        node_type = Prompt.ask(
            "Node type",
            choices=["heavy", "light"],
            default="light"
        )
    elif node_type not in ["heavy", "light"]:
        console.print(f"[red]Invalid node type: {node_type}. Must be 'heavy' or 'light'[/red]")
        return

    # Generate UID
    uid = generate_uid()

    db = NetworkDatabase()
    await db.initialize()

    # Get next available port
    port = await db.get_next_available_port()

    # Add node to network database
    success = await db.add_node(uid, node_type, port)
    if not success:
        console.print("[red]Failed to create node. UID or port might be in use.[/red]")
        return

    # Initialize node database
    node_db = NodeDatabase(uid)
    if node_type == "heavy":
        await node_db.initialize_heavy_node()
    else:
        await node_db.initialize_light_node()

    console.print(f"[green]✓[/green] Created {node_type} node: [bold]{uid}[/bold] on port [cyan]{port}[/cyan]")

    if background:
        # Start the node in background (existing behavior)
        manager = NodeManager()
        await manager.start_node(uid, node_type, port)
    else:
        # Run the node in foreground with cleanup
        await run_node_with_cleanup(uid, node_type, port)


async def run_node_with_cleanup(uid: str, node_type: str, port: int):
    """Run a node in the foreground with proper cleanup on exit."""
    node = None
    shutdown_event = asyncio.Event()
    
    async def cleanup():
        """Clean up node resources."""
        console.print(f"\n[yellow]Shutting down node {uid}...[/yellow]")
        
        # Remove from network database
        db = NetworkDatabase()
        await db.remove_node(uid)
        
        # Clean up node directory
        node_db = NodeDatabase(uid)
        node_db.cleanup()
        
        console.print(f"[green]✓[/green] Cleaned up node {uid}")
        shutdown_event.set()
    
    def signal_handler(sig, frame):
        """Handle interrupt signals."""
        asyncio.create_task(cleanup())
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Create and start the node
        if node_type == "heavy":
            node = HeavyNode(uid, port)
        else:
            node = LightNode(uid, port)
        
        console.print(f"[cyan]Node {uid} running on port {port}. Press Ctrl+C to stop.[/cyan]")
        
        # Run the node
        node_task = asyncio.create_task(node.start())
        shutdown_task = asyncio.create_task(shutdown_event.wait())
        
        # Wait for either the node to crash or shutdown signal
        done, pending = await asyncio.wait(
            [node_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
    except Exception as e:
        console.print(f"[red]Error running node: {e}[/red]")
    finally:
        # Ensure cleanup happens even on error
        if not shutdown_event.is_set():
            await cleanup()


async def stop_existing_node(uid: str):
    """Stop a node and clean up its resources."""
    db = NetworkDatabase()

    # Check if node exists
    node = await db.get_node(uid)
    if not node:
        console.print(f"[red]Node {uid} not found[/red]")
        return

    # Confirm action
    if not Confirm.ask(f"Are you sure you want to stop node [bold]{uid}[/bold]?"):
        console.print("Cancelled")
        return

    # Stop the node process
    manager = NodeManager()
    await manager.stop_node(uid)

    # Remove from network database
    await db.remove_node(uid)

    # Clean up node directory
    node_db = NodeDatabase(uid)
    node_db.cleanup()

    console.print(f"[green]✓[/green] Stopped node [bold]{uid}[/bold] and cleaned up resources")


async def stop_all_nodes():
    """Stop all nodes in the network."""
    console.print(Panel("[bold red]Stop All Nodes[/bold red]"))
    
    db = NetworkDatabase()
    await db.initialize()
    
    # Get all active nodes
    nodes = await db.get_all_nodes()
    
    if not nodes:
        console.print("[yellow]No nodes found in the network[/yellow]")
        return
    
    # Confirm action
    console.print(f"Found [bold]{len(nodes)}[/bold] nodes in the network:")
    for node in nodes:
        console.print(f"  • {node['uid']} ({node['node_type']}) on port {node['port']}")
    
    if not Confirm.ask(f"\nAre you sure you want to stop [bold red]ALL {len(nodes)} nodes[/bold red]?"):
        console.print("Cancelled")
        return
    
    # Stop all nodes
    manager = NodeManager()
    stopped_count = 0
    failed_count = 0
    
    console.print("\n[bold]Stopping nodes...[/bold]")
    
    for node in nodes:
        uid = node['uid']
        try:
            # Stop the node process
            await manager.stop_node(uid)
            
            # Remove from network database
            await db.remove_node(uid)
            
            # Clean up node directory
            node_db = NodeDatabase(uid)
            node_db.cleanup()
            
            console.print(f"[green]✓[/green] Stopped node [bold]{uid}[/bold]")
            stopped_count += 1
            
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to stop node [bold]{uid}[/bold]: {e}")
            failed_count += 1
    
    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Stopped: [green]{stopped_count}[/green]")
    if failed_count > 0:
        console.print(f"  Failed: [red]{failed_count}[/red]")
    
    if stopped_count > 0:
        console.print(f"\n[green]✓[/green] Successfully stopped [bold]{stopped_count}[/bold] nodes and cleaned up resources")


async def view_network_status():
    """Display all nodes in the network."""
    db = NetworkDatabase()
    await db.initialize()

    nodes = await db.get_all_nodes()

    if not nodes:
        console.print("[yellow]No nodes in the network[/yellow]")
        return

    # Create table
    table = Table(title="Formix Network Status", show_header=True, header_style="bold cyan")
    table.add_column("UID", style="dim")
    table.add_column("Node Type", style="cyan")
    table.add_column("Port")
    table.add_column("Status", style="green")
    table.add_column("Created At")

    for node in nodes:
        table.add_row(
            node['uid'],
            node['node_type'],
            str(node['port']),
            node['status'],
            node['created_at']
        )

    console.print(table)

    # Show summary
    heavy_count = sum(1 for n in nodes if n['node_type'] == 'heavy')
    light_count = sum(1 for n in nodes if n['node_type'] == 'light')
    console.print(f"\nTotal nodes: [bold]{len(nodes)}[/bold] "
                 f"(Heavy: [cyan]{heavy_count}[/cyan], Light: [cyan]{light_count}[/cyan])")


async def create_new_computation():
    """Create a new computation in the network."""
    console.print(Panel("[bold cyan]Create New Computation[/bold cyan]"))

    db = NetworkDatabase()
    await db.initialize()

    # Get all nodes
    all_nodes = await db.get_all_nodes()
    if not all_nodes:
        console.print("[red]No nodes available in the network[/red]")
        return

    # Show available nodes
    console.print("\n[bold]Available Nodes:[/bold]")
    for node in all_nodes:
        console.print(f"  {node['uid']} ({node['node_type']})")

    # Get proposing node
    proposer_uid = Prompt.ask("\nProposing node UID")
    proposer = await db.get_node(proposer_uid)
    if not proposer:
        console.print(f"[red]Node {proposer_uid} not found[/red]")
        return

    # Get heavy nodes
    heavy_nodes = await db.get_nodes_by_type("heavy")
    if len(heavy_nodes) < 3:
        console.print(f"[red]Need at least 3 heavy nodes, found {len(heavy_nodes)}[/red]")
        return

    console.print("\n[bold]Available Heavy Nodes:[/bold]")
    for node in heavy_nodes:
        console.print(f"  {node['uid']}")

    heavy_uids = []
    for i in range(3):
        uid = Prompt.ask(f"Heavy node {i+1} UID")
        if uid not in [n['uid'] for n in heavy_nodes]:
            console.print(f"[red]{uid} is not a heavy node[/red]")
            return
        heavy_uids.append(uid)

    # Get computation details
    computation_prompt = Prompt.ask("\nComputation prompt")

    # For PoC, restrict to single number schema
    console.print("\n[yellow]Note: For this PoC, response schema must be a single number[/yellow]")
    response_schema = Prompt.ask(
        "Response schema (JSON)",
        default='{"type": "number"}'
    )

    # Validate schema
    try:
        schema = json.loads(response_schema)
        assert schema.get("type") == "number", "Schema must be for a single number"
    except (json.JSONDecodeError, AssertionError) as e:
        console.print(f"[red]Invalid schema: {e}[/red]")
        return

    # Get deadline
    deadline_seconds = IntPrompt.ask(
        "Deadline (seconds from now)",
        default=60,
        show_default=True
    )
    deadline = datetime.now(UTC) + timedelta(seconds=deadline_seconds)

    # Get minimum participants
    min_participants = IntPrompt.ask(
        "Minimum number of participants",
        default=1,
        show_default=True
    )

    # Create computation
    comp_id = f"COMP-{generate_uid()}"
    computation = {
        'comp_id': comp_id,
        'proposer_uid': proposer_uid,
        'heavy_node_1': heavy_uids[0],
        'heavy_node_2': heavy_uids[1],
        'heavy_node_3': heavy_uids[2],
        'computation_prompt': computation_prompt,
        'response_schema': response_schema,
        'deadline': deadline.isoformat(),
        'min_participants': min_participants
    }

    success = await db.add_computation(computation)
    if success:
        console.print(f"\n[green]✓[/green] Computation [bold]{comp_id}[/bold] created successfully!")

        # Trigger computation broadcast
        manager = NodeManager()
        await manager.broadcast_computation(computation)
    else:
        console.print("[red]Failed to create computation[/red]")


async def show_computation_status(comp_id: str | None = None):
    """Show status of computations."""
    db = NetworkDatabase()
    await db.initialize()

    if comp_id:
        # Show specific computation
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM computations WHERE comp_id = ?", (comp_id,)
            )
            comp = await cursor.fetchone()

            if not comp:
                console.print(f"[red]Computation {comp_id} not found[/red]")
                return

            # Display computation details
            console.print(Panel(f"[bold]Computation {comp_id}[/bold]"))
            console.print(f"Status: {comp['status']}")
            console.print(f"Proposer: {comp['proposer_uid']}")
            console.print(f"Prompt: {comp['computation_prompt']}")
            console.print(f"Deadline: {comp['deadline']}")
            console.print(f"Min Participants: {comp['min_participants']}")

            if comp['status'] == 'completed':
                console.print(f"[green]Result: {comp['result']}[/green]")
                console.print(f"Participants: {comp['participants_count']}")
    else:
        # Show all computations
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM computations ORDER BY created_at DESC LIMIT 10"
            )
            comps = await cursor.fetchall()

            if not comps:
                console.print("[yellow]No computations found[/yellow]")
                return

            table = Table(title="Recent Computations", show_header=True)
            table.add_column("ID", style="dim")
            table.add_column("Status")
            table.add_column("Proposer")
            table.add_column("Result")
            table.add_column("Participants")

            for comp in comps:
                status_style = "green" if comp['status'] == 'completed' else "yellow"
                table.add_row(
                    comp['comp_id'],
                    f"[{status_style}]{comp['status']}[/{status_style}]",
                    comp['proposer_uid'],
                    str(comp['result']) if comp['result'] else "-",
                    str(comp['participants_count']) if comp['participants_count'] else "-"
                )

            console.print(table)


def main(
    new_node: Annotated[bool, typer.Option("--new-node", "-nn", help="Create a new node")] = False,
    node_type: Annotated[str | None, typer.Option("--type", "-t", help="Node type (heavy/light)")] = None,
    foreground: Annotated[bool, typer.Option("--foreground", "-f", help="Run node in foreground (blocks terminal)")] = False,
    stop_node: Annotated[str | None, typer.Option("--stop-node", "-sn", help="Stop a node by UID")] = None,
    stop_all: Annotated[bool, typer.Option("--stop-all", "-sa", help="Stop all nodes in the network")] = False,
    view: Annotated[bool, typer.Option("--view", "-v", help="View network status")] = False,
    comp: Annotated[bool, typer.Option("--comp", "-c", help="Create a computation")] = False,
    status: Annotated[str | None, typer.Option("--status", "-s", help="Show computation status (optional: comp_id)")] = None,
):
    """
    Formix - Private Map Secure Reduce Network
    
    A privacy-preserving distributed computation network using secure multi-party computation.
    """
    # Ensure FORMIX_HOME exists
    FORMIX_HOME.mkdir(parents=True, exist_ok=True)

    loop = get_or_create_event_loop()

    # Handle actions based on flags
    if new_node:
        loop.run_until_complete(create_new_node(node_type, background=not foreground))
    elif stop_node:
        loop.run_until_complete(stop_existing_node(stop_node))
    elif stop_all:
        loop.run_until_complete(stop_all_nodes())
    elif view:
        loop.run_until_complete(view_network_status())
    elif comp:
        loop.run_until_complete(create_new_computation())
    elif status is not None:
        # If --status is provided with no value, it will be an empty string
        comp_id = status if status else None
        loop.run_until_complete(show_computation_status(comp_id))
    else:
        # No action specified, show help
        console.print("No action specified. Use --help to see available options.")


def cli():
    """Entry point for the CLI."""
    typer.run(main)


if __name__ == "__main__":
    cli()
