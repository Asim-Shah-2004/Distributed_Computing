#!/usr/bin/env python3
import sys
import os
import argparse
from election_algorithms import analyze_logs, ElectionAlgorithm

def main():
    parser = argparse.ArgumentParser(description='Analyze distributed election algorithm logs')
    parser.add_argument('algorithm', type=str, default='bully', nargs='?',
                        help='Election algorithm used (default: bully)')
    parser.add_argument('--nodes', type=int, default=6,
                        help='Number of nodes in the network (default: 6)')
    parser.add_argument('--logs-dir', type=str, default='/logs',
                        help='Directory containing log files (default: /logs)')
    
    args = parser.parse_args()
    
    # Parse the algorithm
    algorithm = ElectionAlgorithm(args.algorithm)
    
    # Analyze logs
    results = analyze_logs(args.logs_dir, algorithm, args.nodes)
    
    # Print report to console
    print('\n' + '='*60)
    print(f'ELECTION REPORT - {algorithm.value.upper()} ALGORITHM')
    print('='*60)
    print(f'Number of nodes: {args.nodes}')
    print(f'Coordinator elected: Node {results.get("coordinator")}')
    print(f'Total messages sent: {results["message_count"]}')
    
    # Handle the case where election_duration might be None
    duration = results.get("election_duration")
    if duration is not None:
        print(f'Election duration: {duration:.2f} seconds')
    else:
        print('Election duration: Not available')
    print('\nMessage types:')
    
    for msg_type, count in results["message_types"].items():
        print(f'  - {msg_type}: {count}')
        
    print('\nMessages per node:')
    
    for node_id, count in results["per_node_messages"].items():
        print(f'  - Node {node_id}: {count}')
        
    print('='*60)
    
    # Save report to file
    report_file = f'{args.logs_dir}/report_{algorithm.value}.txt'
    with open(report_file, 'w') as f:
        f.write(f'ELECTION REPORT - {algorithm.value.upper()} ALGORITHM\n')
        f.write(f'Number of nodes: {args.nodes}\n')
        f.write(f'Coordinator elected: Node {results.get("coordinator")}\n')
        f.write(f'Total messages sent: {results["message_count"]}\n')
        
        # Handle the case where election_duration might be None
        duration = results.get("election_duration")
        if duration is not None:
            f.write(f'Election duration: {duration:.2f} seconds\n\n')
        else:
            f.write('Election duration: Not available\n\n')
        f.write('Message types:\n')
        for msg_type, count in results["message_types"].items():
            f.write(f'  - {msg_type}: {count}\n')
        f.write('\nMessages per node:\n')
        for node_id, count in results["per_node_messages"].items():
            f.write(f'  - Node {node_id}: {count}\n')
    
    print(f'\nReport saved to {report_file}')

if __name__ == '__main__':
    main()