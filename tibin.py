#!/usr/bin/env python3
"""
Tibin Full-Stack Agent Runtime Unified CLI

This is the single entry point for all runtime actions.
"""

import sys
import argparse
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

def main():
    parser = argparse.ArgumentParser(
        description="Tibin Full-Stack Agent Runtime",
        usage="tibin.py <command> [options]",
        epilog="Use 'tibin.py <command> --help' for more information on a specific command."
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # server command
    server_parser = subparsers.add_parser("server", help="Start the dashboard server")
    server_parser.add_argument("--stop", action="store_true", help="Stop dashboard, watcher, and port 5000 listeners")
    server_parser.add_argument("--status", action="store_true", help="Show process registry")

    # gui command
    gui_parser = subparsers.add_parser("gui", help="Open the desktop launcher GUI")
    gui_parser.add_argument("--no-gui", action="store_true", help="Start dashboard without GUI")
    gui_parser.add_argument("--stop", action="store_true", help="Stop all processes")
    gui_parser.add_argument("--status", action="store_true", help="Show status")

    # daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Run the background watcher daemon")
    
    # cli command (passes remaining args to runtime.py)
    cli_parser = subparsers.add_parser("cli", help="Run the core CLI agent (formerly runtime.py)")

    args, unknown = parser.parse_known_args()

    if args.command == "server":
        from commands.run_server import main as server_main
        sys.argv = [sys.argv[0]] + unknown
        if args.stop:
            sys.argv.append("--stop")
        if args.status:
            sys.argv.append("--status")
        server_main()
        
    elif args.command == "gui":
        from commands.launcher import main as gui_main
        sys.argv = [sys.argv[0]] + unknown
        if args.no_gui:
            sys.argv.append("--no-gui")
        if args.stop:
            sys.argv.append("--stop")
        if args.status:
            sys.argv.append("--status")
        gui_main()
        
    elif args.command == "daemon":
        from commands.agent_daemon import AgentDaemon
        daemon = AgentDaemon()
        daemon.run()
        
    elif args.command == "cli":
        from runtime import main as cli_main
        # Override sys.argv so argparse in runtime.py works seamlessly
        sys.argv = [sys.argv[0]] + unknown
        cli_main()
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
