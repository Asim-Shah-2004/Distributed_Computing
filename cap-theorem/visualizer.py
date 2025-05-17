import time
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TaskProgressColumn
from rich import box
from rich.layout import Layout
from rich.text import Text
from rich.markdown import Markdown
from rich.columns import Columns
from rich.pretty import Pretty
from rich.tree import Tree
from rich.traceback import install
from rich.align import Align
from typing import Dict, List, Optional
import json
import os
import shutil


# Install rich traceback handler
install(show_locals=True)


console = Console()


class SystemVisualizer:
    def __init__(self):
        self.console = Console()
        self.node_states = {}
        self.operation_history = []
        self.cap_state = {
            'consistency': True,
            'availability': True,
            'partition_tolerance': True
        }
        self.term_width, self.term_height = self._get_terminal_size()
        self.layout = Layout()
        self.setup_layout()
        self.start_time = time.time()
        self.node_health = {}
        self.performance_metrics = {
            "response_times": [],
            "throughput": 0,
            "success_rate": 100.0
        }
        self.network_topology = {}  # Store network connections between nodes


    def _get_terminal_size(self):
        """Get the terminal size and adjust if too small"""
        terminal_width, terminal_height = shutil.get_terminal_size()
        # Ensure minimum size
        return max(terminal_width, 80), max(terminal_height, 24)


    def setup_layout(self):
        """Set up a layout that works better with different terminal sizes"""
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main")
        )
       
        # Determine the best layout based on terminal width
        if self.term_width < 100:
            # For narrow terminals, use a vertical stack
            self.layout["main"].split(
                Layout(name="cap_theorem", size=8),
                Layout(name="nodes", ratio=2),
                Layout(name="bottom", ratio=1)
            )
            self.layout["bottom"].split(
                Layout(name="network_diagram", size=6),
                Layout(name="stats", size=6),
                Layout(name="operations", ratio=1)
            )
        else:
            # For wider terminals, use a side-by-side layout
            self.layout["main"].split_row(
                Layout(name="left", ratio=1),
                Layout(name="right", ratio=2)
            )
            self.layout["left"].split(
                Layout(name="cap_theorem", size=12),
                Layout(name="network_diagram", size=10),
                Layout(name="stats", size=8)
            )
            self.layout["right"].split(
                Layout(name="nodes", ratio=1),
                Layout(name="operations", ratio=1)
            )


    def update_node_state(self, node_id: str, data: Dict):
        self.node_states[node_id] = data
        # Update node health
        self.node_health[node_id] = {
            "last_seen": time.time(),
            "status": "active" if not data.get('failed', False) else "failed"
        }
       
        # Add to operation history
        self.operation_history.append({
            'timestamp': time.time(),
            'node': node_id,
            'data': data,
            'type': data.get('type', 'state_update'),
            'details': data.get('details', 'Node state updated')
        })
       
        # Keep history manageable
        if len(self.operation_history) > 50:
            self.operation_history = self.operation_history[-50:]
           
        # Update performance metrics if available
        if 'response_time' in data:
            self.performance_metrics["response_times"].append(data['response_time'])
            if len(self.performance_metrics["response_times"]) > 100:
                self.performance_metrics["response_times"] = self.performance_metrics["response_times"][-100:]
               
        if 'success' in data:
            # Calculate rolling success rate
            success_count = sum(1 for op in self.operation_history[-20:] if op.get('data', {}).get('success', True))
            self.performance_metrics["success_rate"] = (success_count / min(20, len(self.operation_history))) * 100
           
        # Calculate throughput (ops in last 10 seconds)
        recent_ops = sum(1 for op in self.operation_history if time.time() - op['timestamp'] < 10)
        self.performance_metrics["throughput"] = recent_ops / 10.0


    def update_cap_state(self, consistency: bool = None, availability: bool = None, partition_tolerance: bool = None):
        if consistency is not None:
            self.cap_state['consistency'] = consistency
        if availability is not None:
            self.cap_state['availability'] = availability
        if partition_tolerance is not None:
            self.cap_state['partition_tolerance'] = partition_tolerance


    def update_network_topology(self, node_id: str, connections: List[str]):
        """Update the network topology with node connections"""
        self.network_topology[node_id] = connections


    def render_network_diagram(self):
        """Render a simplified network diagram to fit in narrow terminals"""
        if not self.network_topology:
            return Panel("No network topology data available", title="Network Diagram")


        # Create a simplified network representation
        nodes = list(self.network_topology.keys())
       
        # Very compact representation for all terminals
        node_list = []
        node_list.append("Each computer in our distributed system:")
       
        for node in nodes:
            status = "🟢 Online" if not self.node_states.get(node, {}).get('failed', False) else "🔴 Offline"
           
            # Determine how to show connections based on terminal width
            if self.term_width < 100:
                # For very narrow terminals, just show node status
                node_list.append(f"{status}: {node}")
            else:
                # For wider terminals, show first connection and consistency model
                model = self.node_states.get(node, {}).get('consistency_model', 'Unknown')
                node_list.append(f"{status}: {node} ({model} consistency)")
       
        return Panel(
            "\n".join(node_list),
            title="Connected Computers",
            border_style="blue",
            box=box.ROUNDED
        )


    def render_cap_panel(self):
        """Render a simplified CAP theorem panel that fits in any terminal width"""
        # Use a simple text representation with explanations
        cap_status = []
       
        # Simple CAP theorem representation with explanations
        cap_status.append("📊 CAP Theorem - Choose 2 of 3:")
        cap_status.append(f"{'✅' if self.cap_state['consistency'] else '❌'} Consistency: All users see the same data")
        cap_status.append(f"{'✅' if self.cap_state['availability'] else '❌'} Availability: System always responds")
        cap_status.append(f"{'✅' if self.cap_state['partition_tolerance'] else '❌'} Partition Tolerance: Works despite network issues")
       
        # Add mode with explanation
        cap_mode = self._get_cap_mode()
        cap_status.append(f"\nCurrent Priority: {cap_mode}")
        cap_status.append(self._get_cap_mode_explanation())
       
        return Panel(
            "\n".join(cap_status),
            title="Database Trade-offs",
            border_style="blue",
            box=box.ROUNDED
        )


    def _get_cap_mode_explanation(self):
        """Get an explanation of what the current CAP mode means"""
        if self.cap_state['consistency'] and self.cap_state['availability']:
            return "⚠️ Warning: This works only when network is perfect"
        elif self.cap_state['consistency'] and self.cap_state['partition_tolerance']:
            return "💡 May refuse requests to maintain correctness"
        elif self.cap_state['availability'] and self.cap_state['partition_tolerance']:
            return "💡 Always responds but data may be outdated"
        else:
            return "⚠️ System not functioning properly!"


    def _get_cap_mode(self):
        """Determine which CAP mode the system is in"""
        if self.cap_state['consistency'] and self.cap_state['availability']:
            return "CA - Consistency & Availability"
        elif self.cap_state['consistency'] and self.cap_state['partition_tolerance']:
            return "CP - Consistency & Partition Tolerance"
        elif self.cap_state['availability'] and self.cap_state['partition_tolerance']:
            return "AP - Availability & Partition Tolerance"
        else:
            return "Undetermined"


    def render_node_table(self):
        """Render the node states in a styled table that adapts to terminal width"""
        # Determine how many columns we can show based on terminal width
        if self.term_width < 100:
            # Very narrow terminal - just show essential info
            table = Table(
                title="Database Computers",
                box=box.ROUNDED,
                highlight=True,
                show_header=True,
                header_style="bold magenta",
                expand=False
            )
           
            table.add_column("Computer", style="cyan", width=10)
            table.add_column("Status", justify="center", width=8)
            table.add_column("Data Value", justify="left", width=15)
           
            for node_id, state in self.node_states.items():
                status = "✅" if not state.get('failed', False) else "❌"
                status_style = "green" if not state.get('failed', False) else "red"
               
                # Get actual data value to display
                data_value = self._get_display_data_value(state)
                data_style = "yellow"
               
                table.add_row(
                    node_id[:10],
                    Text(status, style=status_style),
                    Text(data_value, style=data_style)
                )
        else:
            # Wider terminal - show more details
            table = Table(
                title="Database Computers",
                box=box.ROUNDED,
                highlight=True,
                show_header=True,
                header_style="bold magenta",
                expand=True
            )
           
            # Adjust columns based on width
            if self.term_width < 140:
                table.add_column("Computer", style="cyan", width=12)
                table.add_column("Consistency Type", style="magenta", width=15)
                table.add_column("Status", justify="center", width=8)
                table.add_column("Current Data", justify="left", width=20)
            else:
                table.add_column("Computer", style="cyan", width=12)
                table.add_column("Consistency Type", style="magenta", width=15)
                table.add_column("Status", justify="center", width=8)
                table.add_column("Current Data", style="yellow", width=20)
                table.add_column("Version Numbers", style="blue", width=15)
           
            for node_id, state in self.node_states.items():
                status = "✅ Working" if not state.get('failed', False) else "❌ Not working"
                status_style = "green" if not state.get('failed', False) else "red"
               
                # Get actual data value to display
                data_value = self._get_display_data_value(state)
                data_style = "yellow"
                               
                # Format vector clock in simpler terms
                vector_clock = state.get('vector_clock', {})
                vector_clock_str = ", ".join([f"{k}:{v}" for k, v in vector_clock.items()]) if vector_clock else "Empty"
               
                model_name = self._get_simplified_model_name(state.get('consistency_model', 'Unknown'))
               
                if self.term_width < 140:
                    table.add_row(
                        node_id,
                        model_name,
                        Text(status, style=status_style),
                        Text(data_value, style=data_style)
                    )
                else:
                    table.add_row(
                        node_id,
                        model_name,
                        Text(status, style=status_style),
                        Text(data_value, style=data_style),
                        vector_clock_str
                    )
       
        return Panel(table, border_style="blue", box=box.ROUNDED)


    def _get_display_data_value(self, state):
        """Extract a readable data value from node state for display"""
        data = state.get('data', {})
        if not data:
            return "No data available"
           
        # If there's a single 'value' field, use that directly
        if 'value' in data:
            value = data['value']
            # If the value indicates inconsistency, highlight it
            if 'different_data_' in str(value):
                return f"⚠️ {value[:15]}..."
            elif 'inconsistent' in str(value):
                return f"⚠️ {value[:15]}..."
            else:
                return f"{value}"
               
        # Otherwise, show the first item in a readable format
        if len(data) > 0:
            k = list(data.keys())[0]
            v = data[k]
            return f"{k}: {v}"
       
        return "No data available"


    def _get_simplified_model_name(self, model):
        """Convert technical consistency model names to more user-friendly terms"""
        model_explanations = {
            "Strong": "Strong (always accurate)",
            "Eventual": "Eventual (may be delayed)",
            "Causal": "Causal (preserves order)",
            "Read-your-writes": "Read-your-writes (sees own updates)"
        }
        return model_explanations.get(model, model)


    def render_history_table(self):
        """Render the operation history in a styled table that adapts to terminal width"""
        table = Table(
            title="Recent Events",
            box=box.ROUNDED,
            highlight=True,
            show_header=True,
            header_style="bold cyan",
            expand=True
        )
       
        # Calculate available height for operations
        available_height = max(5, min(10, self.term_height // 5))
       
        # Determine number of operations to show and how detailed based on terminal width
        if self.term_width < 100:
            # Very narrow terminal - simplified view
            table.add_column("Time", style="cyan", justify="center", width=6)
            table.add_column("Computer", style="magenta", width=8)
            table.add_column("Result", justify="center", width=4)
           
            # Display only a few operations
            display_count = min(3, len(self.operation_history))
           
            for op in reversed(self.operation_history[-display_count:]):
                time_str = time.strftime('%H:%M', time.localtime(op['timestamp']))
               
                # Determine operation status
                data = op.get('data', {})
                success = data.get('success', True)
                status = "✅" if success else "❌"
                status_style = "green" if success else "red"
               
                table.add_row(
                    time_str,
                    op['node'][:8],
                    Text(status, style=status_style)
                )
        else:
            # Wider terminal - more detailed view
            if self.term_width < 140:
                table.add_column("Time", style="cyan", justify="center", width=8)
                table.add_column("Computer", style="magenta", width=10)
                table.add_column("Event Type", style="green", width=15)
                table.add_column("Result", justify="center", width=5)
            else:
                table.add_column("Time", style="cyan", justify="center", width=8)
                table.add_column("Computer", style="magenta", width=12)
                table.add_column("Event Type", style="green", width=15)
                table.add_column("Details", style="yellow", width=25)
                table.add_column("Result", justify="center", width=5)
           
            # Display more operations for wider terminals
            display_count = min(available_height, len(self.operation_history))
           
            for op in reversed(self.operation_history[-display_count:]):
                time_str = time.strftime('%H:%M:%S', time.localtime(op['timestamp']))
               
                # Extract operation type and details
                data = op.get('data', {})
                op_type = op.get('type', data.get('type', 'Unknown'))
                details = op.get('details', data.get('details', 'No details'))
               
                # Make operation type more user-friendly
                op_type = self._get_simplified_operation_type(op_type)
               
                # Determine operation status
                success = data.get('success', True)
                status = "✅" if success else "❌"
                status_style = "green" if success else "red"
               
                if self.term_width < 140:
                    table.add_row(
                        time_str,
                        op['node'][:10],
                        op_type[:15],
                        Text(status, style=status_style)
                    )
                else:
                    table.add_row(
                        time_str,
                        op['node'],
                        op_type[:15],
                        details[:25],
                        Text(status, style=status_style)
                    )


        return Panel(table, title="System Activity", border_style="green", box=box.ROUNDED)


    def _get_simplified_operation_type(self, op_type):
        """Convert technical operation types to more user-friendly terms"""
        op_explanations = {
            "Network Partition": "Network Problem",
            "Network Partition Resolved": "Network Fixed",
            "Consistency Violation": "Data Mismatch",
            "Consistency Restored": "Data Fixed",
            "Availability Issue": "Not Responding",
            "Availability Restored": "Responding Again",
            "Data Reconciliation Complete": "Data Synchronized",
            "state_update": "Update"
        }
        return op_explanations.get(op_type, op_type)


    def render_stats_panel(self):
        """Render system statistics that adapts to terminal width"""
        # Calculate active and failed nodes
        active_nodes = sum(1 for _, state in self.node_states.items() if not state.get('failed', False))
        failed_nodes = sum(1 for _, state in self.node_states.items() if state.get('failed', False))
       
        # Simplified stats for all terminals
        stats_text = [
            f"Total Computers: {len(self.node_states)}",
            f"Working: {active_nodes} | Not Working: {failed_nodes}",
            f"Total Events: {len(self.operation_history)}",
            f"System Running for: {self._format_uptime()}"
        ]
       
        return Panel(
            "\n".join(stats_text),
            title="System Summary",
            border_style="green",
            box=box.ROUNDED,
            padding=(1, 1)
        )
   
    def _format_uptime(self):
        """Format uptime for display"""
        uptime_seconds = time.time() - self.start_time
       
        if uptime_seconds < 60:
            return f"{uptime_seconds:.1f} seconds"
        elif uptime_seconds < 3600:
            return f"{uptime_seconds/60:.1f} minutes"
        else:
            return f"{uptime_seconds/3600:.1f} hours"


    def render_data_view_panel(self):
        """Render a panel showing visual data view across nodes"""
        # Create a table showing current values across all nodes
        table = Table(
            show_header=True,
            header_style="bold green",
            box=box.ROUNDED,
            expand=True
        )
       
        # Add columns for each key
        table.add_column("Data Item", style="bold yellow", width=10)
       
        # Get unique data keys across all nodes
        all_data_keys = set()
        for node_id, state in self.node_states.items():
            data = state.get('data', {})
            all_data_keys.update(data.keys())
       
        # Add a column for each node
        node_ids = list(self.node_states.keys())
        for node_id in node_ids:
            # Limit node name to 10 chars
            table.add_column(node_id[:10], style="cyan", width=12)


        # First collect all values to determine consistency
        # and find the most common value for each key
        all_values = {}
        most_common_values = {}
       
        for key in sorted(all_data_keys):
            all_values[key] = []
            value_counts = {}
           
            for node_id in node_ids:
                state = self.node_states[node_id]
                if state.get('failed', False):
                    all_values[key].append("OFFLINE")
                else:
                    data = state.get('data', {})
                    value = str(data.get(key, "—"))
                    all_values[key].append(value)
                   
                    # Count occurrences of each value
                    if value != "OFFLINE" and value != "—":
                        value_counts[value] = value_counts.get(value, 0) + 1
           
            # Find the most common value (if any)
            if value_counts:
                most_common_value = max(value_counts.items(), key=lambda x: x[1])[0]
                most_common_values[key] = most_common_value
       
        # Add rows for each data key
        for key in sorted(all_data_keys):
            row_values = [key]
           
            # Only mark values as inconsistent if they differ from the most common value
            # and are present in the demonstration nodes
            inconsistent_nodes = []
           
            # Check if we're in a consistency demonstration
            in_consistency_demo = False
            for op in self.operation_history[-3:]:
                if op.get('type') == 'Consistency Violation':
                    in_consistency_demo = True
                    break
           
            # Get the nodes currently under demonstration
            demonstration_nodes = []
            if in_consistency_demo:
                for op in self.operation_history[-3:]:
                    if 'data' in op and 'affected_nodes' in op['data']:
                        demonstration_nodes.extend(op['data']['affected_nodes'])
           
            # Get value from each node
            for i, node_id in enumerate(node_ids):
                state = self.node_states[node_id]
                data = state.get('data', {})
                value = data.get(key, "—")
               
                # For failed nodes, show "OFFLINE"
                if state.get('failed', False):
                    row_values.append(Text("OFFLINE", style="dim red"))
                else:
                    if key in most_common_values:
                        most_common = most_common_values[key]
                       
                        # Only mark as inconsistent if:
                        # 1. The value differs from the most common AND
                        # 2. The node is part of the current demonstration
                        is_inconsistent = (str(value) != most_common and
                                          (node_id in demonstration_nodes))
                                         
                        style = "red bold" if is_inconsistent else "white"
                    else:
                        style = "white"
                       
                    row_values.append(Text(str(value)[:10], style=style))
           
            table.add_row(*row_values)
       
        return Panel(
            table,
            title="Visual Data Comparison",
            subtitle="(Red values indicate inconsistencies)",
            border_style="green",
            box=box.ROUNDED
        )


    def display_system_state(self):
        """Display the complete system state with the enhanced layout"""
        # Get current terminal size in case it has changed
        new_width, new_height = self._get_terminal_size()
        if new_width != self.term_width or new_height != self.term_height:
            self.term_width, self.term_height = new_width, new_height
            self.setup_layout()  # Reinitialize layout if terminal size changed
           
        # Create the title with appropriate width
        title_width = min(self.term_width - 4, 60)  # Limit title width
        title = "Distributed Database Systems Visualization"
        if len(title) > title_width:
            title = title[:title_width-3] + "..."
           
        # Populate the layout sections
        self.layout["header"].update(
            Panel(
                Align.center(
                    Text(title, style="bold white on blue"),
                ),
                style="bold cyan",
                box=box.HEAVY_EDGE
            )
        )
       
        # Update panels based on layout
        cap_panel = self.render_cap_panel()
        network_panel = self.render_network_diagram()
        stats_panel = self.render_stats_panel()
        nodes_panel = self.render_node_table()
        operations_panel = self.render_history_table()
        data_view_panel = self.render_data_view_panel()
       
        if self.term_width < 100:
            # Vertical layout updates
            self.layout["cap_theorem"].update(cap_panel)
            self.layout["nodes"].update(nodes_panel)
            self.layout["network_diagram"].update(network_panel)
            self.layout["stats"].update(stats_panel)
            self.layout["operations"].update(data_view_panel)  # Replace operations with data view
        else:
            # Side-by-side layout updates
            self.layout["cap_theorem"].update(cap_panel)
            self.layout["network_diagram"].update(network_panel)
            self.layout["stats"].update(stats_panel)
            self.layout["nodes"].update(nodes_panel)
            self.layout["operations"].update(data_view_panel)  # Replace operations with data view
       
        # Clear console and display the layout
        self.console.clear()
        self.console.print(self.layout)


    def create_progress_group(self, title="Operation in Progress"):
        """Create a standardized progress group with multiple indicators"""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console
        )
        return progress, title


    def show_network_partition(self, nodes: List[str], duration: int):
        """Display network partition simulation with live updates"""
        self.update_cap_state(partition_tolerance=False)
       
        # Update network topology to show partition
        for node in nodes:
            if node in self.network_topology:
                # Remove connections to other nodes in the partition
                self.network_topology[node] = [n for n in self.network_topology[node] if n not in nodes]
       
        # Use enhanced progress display
        progress, title = self.create_progress_group("Network Problem Simulation")
        with progress:
            task = progress.add_task(f"[red]Network issue affecting {', '.join(nodes)}...", total=duration)
           
            for step in range(duration):
                time.sleep(1)
                progress.update(task, advance=1)
               
                # Add to operation history
                self.operation_history.append({
                    'timestamp': time.time(),
                    'node': 'SYSTEM',
                    'type': 'Network Partition',
                    'details': f"Network connection lost between computers",
                    'data': {
                        'type': 'Network Partition',
                        'details': f"Affected computers: {', '.join(nodes)}",
                        'step': step+1,
                        'total_steps': duration
                    }
                })
               
                self.display_system_state()
       
        # Reset partition tolerance and restore connections
        self.update_cap_state(partition_tolerance=True)
        for node in nodes:
            if node in self.network_topology:
                # Restore all connections
                self.network_topology[node] = list(self.node_states.keys())
       
        # Add completion record
        self.operation_history.append({
            'timestamp': time.time(),
            'node': 'SYSTEM',
            'type': 'Network Partition Resolved',
            'details': f"Network connection restored",
            'data': {
                'type': 'Network Partition Resolved',
                'details': f"Network connection restored",
                'affected_nodes': nodes
            }
        })
       
        self.display_system_state()


    def show_consistency_violation(self, nodes: List[str], duration: int):
        """Display consistency violation with live updates"""
        self.update_cap_state(consistency=False)
       
        # First set all nodes to the same initial value for contrast
        for node_id in self.node_states:
            self.node_states[node_id]['data'] = {
                'Balance': '₹100',
                'Price': '₹10'
            }
           
        # Now update target nodes to show inconsistency with different values
        for node in nodes:
            if node in self.node_states:
                # Give each node a different value to clearly show the inconsistency
                node_num = int(node[-1])
                self.node_states[node]['data'] = {
                    'Balance': f"₹{50 + node_num * 10}",  # Different balance per node
                    'Price': f"₹{node_num * 10}"  # Price varies based on node number
                }
       
        # Use enhanced progress display
        progress, title = self.create_progress_group("Data Inconsistency Simulation")
        with progress:
            task = progress.add_task(f"[yellow]Data inconsistency affecting {', '.join(nodes)}...", total=duration)
           
            for step in range(duration):
                time.sleep(1)
                progress.update(task, advance=1)
               
                # Occasionally update data to show it changing while inconsistent
                if step == 2:
                    for node in nodes:
                        if node in self.node_states:
                            # Change the price on one node to make inconsistency more obvious
                            node_num = int(node[-1])
                            self.node_states[node]['data']['Price'] = f"₹{25 + node_num * 5}"
               
                # Add to operation history
                self.operation_history.append({
                    'timestamp': time.time(),
                    'node': 'SYSTEM',
                    'type': 'Consistency Violation',
                    'details': f"Different data on different computers",
                    'data': {
                        'type': 'Consistency Violation',
                        'details': f"Data inconsistency detected",
                        'step': step+1,
                        'total_steps': duration,
                        'affected_nodes': nodes
                    }
                })
               
                self.display_system_state()
       
        # Reset consistency and restore node states
        self.update_cap_state(consistency=True)
        # Reset all nodes to the same consistent data
        for node_id in self.node_states:
            self.node_states[node_id]['data'] = {
                'Balance': '₹100',
                'Price': '₹10'
            }
       
        # Add completion record
        self.operation_history.append({
            'timestamp': time.time(),
            'node': 'SYSTEM',
            'type': 'Consistency Restored',
            'details': f"All computers now have the same data",
            'data': {
                'type': 'Data Reconciliation Complete',
                'details': f"System data is now consistent",
                'affected_nodes': nodes
            }
        })
       
        self.display_system_state()


    def show_availability_issue(self, nodes: List[str], duration: int):
        """Display availability issue with live updates"""
        self.update_cap_state(availability=False)
       
        # Mark nodes as failed
        for node in nodes:
            if node in self.node_states:
                self.node_states[node]['failed'] = True
       
        # Use enhanced progress display
        progress, title = self.create_progress_group("Computer Failure Simulation")
        with progress:
            task = progress.add_task(f"[blue]Computer failures affecting {', '.join(nodes)}...", total=duration)
           
            for step in range(duration):
                time.sleep(1)
                progress.update(task, advance=1)
               
                # Add to operation history with more details
                self.operation_history.append({
                    'timestamp': time.time(),
                    'node': 'SYSTEM',
                    'type': 'Availability Issue',
                    'details': f"Computers not responding to requests",
                    'data': {
                        'type': 'Availability Issue',
                        'details': f"Computers not responding",
                        'step': step+1,
                        'total_steps': duration,
                        'affected_nodes': nodes,
                        'success': False
                    }
                })
               
                self.display_system_state()
       
        # Reset availability and restore nodes
        self.update_cap_state(availability=True)
        for node in nodes:
            if node in self.node_states:
                self.node_states[node]['failed'] = False
       
        # Add completion record
        self.operation_history.append({
            'timestamp': time.time(),
            'node': 'SYSTEM',
            'type': 'Availability Restored',
            'details': f"All computers are working again",
            'data': {
                'type': 'Availability Restored',
                'details': f"System is fully available",
                'affected_nodes': nodes,
                'success': True
            }
        })
       
        self.display_system_state()


def main():
    """Main entry point for the visualizer"""
    visualizer = SystemVisualizer()
   
    # Set up initial node states with consistency models
    nodes = [
        {'id': 'computer-1', 'model': 'Strong'},
        {'id': 'computer-2', 'model': 'Eventual'},
        {'id': 'computer-3', 'model': 'Causal'},
        {'id': 'computer-4', 'model': 'Read-your-writes'}
    ]
   
    # Initialize nodes with states
    for node in nodes:
        visualizer.update_node_state(node['id'], {
            'consistency_model': node['model'],
            'data': {
                'Balance': '₹100',
                'Price': '₹10'
            },
            'vector_clock': {node['id']: 1},
            'failed': False
        })
   
    # Initialize network topology
    for node in nodes:
        visualizer.update_network_topology(node['id'], [n['id'] for n in nodes if n['id'] != node['id']])
   
    # Initial state
    visualizer.display_system_state()
    input("\nPress Enter to start demonstrations...")
   
    try:
        # Demonstrate network partition
        print("\nDemonstrating Network Problems - what happens when computers can't talk to each other...")
        visualizer.show_network_partition(['computer-1', 'computer-2'], 5)
        input("\nPress Enter to continue...")
       
        # Demonstrate consistency violation
        print("\nDemonstrating Data Inconsistency - what happens when data is different on different computers...")
        print("Look at the 'Visual Data Comparison' panel to see the real data differences!")
        visualizer.show_consistency_violation(['computer-3', 'computer-4'], 5)
        input("\nPress Enter to continue...")
       
        # Demonstrate availability issue
        print("\nDemonstrating Computer Failures - what happens when some computers stop working...")
        print("Notice how the data becomes unavailable (OFFLINE) for failed computers!")
        visualizer.show_availability_issue(['computer-1', 'computer-3'], 5)
        input("\nPress Enter to continue...")
       
        # Final state
        visualizer.display_system_state()
        print("\nDemonstration complete!")
    except KeyboardInterrupt:
        print("\nDemonstration interrupted by user.")
    finally:
        # Ensure terminal is in a good state
        print("\nExiting visualization...")


if __name__ == "__main__":
    main()