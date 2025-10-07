#!/usr/bin/env python3
# File: main.py

import xml.etree.ElementTree as ET
import subprocess
import sys
import os
import argparse
import tempfile

# Import our custom modules
from graph_builder import GraphBuilder
from dot_generator import generate_dot

def main():
    p = argparse.ArgumentParser(description="Generate linked CFG/DFG from Verilog via Verilator")
    p.add_argument('verilog_file', help="Verilog source file")
    p.add_argument('-t', '--top', dest='top_module', help="Top-level module name")
    p.add_argument('-o', '--output', dest='output_file', help="Output name (e.g. mygraph.svg). Extension decides format.")
    p.add_argument('--format', choices=['svg', 'png', 'dot', 'pdf'], help="Override output format. Use svg for tooltips.")
    p.add_argument('--layout-engine', choices=['dot', 'fdp', 'neato', 'circo', 'twopi'], default='fdp', help="Graphviz layout engine")
    p.add_argument('--no-inter-cluster-dfg', action='store_true', help="Hide DFG edges across procedural boundaries")
    args = p.parse_args()

    # Determine output file name and format
    if not args.output_file:
        base = os.path.splitext(os.path.basename(args.verilog_file))[0]
        args.output_file = f"{base}_cfg.svg"
        print(f"Warning: No output file specified. Defaulting to {args.output_file}")
    
    fmt = args.format or os.path.splitext(args.output_file)[1][1:].lower()
    if not fmt:
        fmt = 'svg'
        args.output_file += '.svg'
    args.format = fmt

    # 1. Read Verilog source for tooltips
    try:
        with open(args.verilog_file, 'r') as f:
            verilog_lines = f.readlines()
    except FileNotFoundError:
        sys.exit(f"Error: Cannot open Verilog file '{args.verilog_file}'")

    # 2. Run Verilator to generate XML AST
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as tmp:
        ast_path = tmp.name
    cmd = ['verilator', '--xml-only', '--xml-output', ast_path, '-Wno-fatal']
    if args.top_module:
        cmd += ['--top-module', args.top_module]
    cmd.append(args.verilog_file)
    print("Invoking Verilator...")
    try:
        subprocess.run(cmd, check=True, text=True, capture_output=True)
    except FileNotFoundError:
        sys.exit("Error: 'verilator' not found in your PATH. Please install Verilator.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"Verilator error:\n{e.stderr}\n{e.stdout}")

    # 3. Parse XML and build the graph model
    print("Parsing AST and building graph...")
    tree = ET.parse(ast_path)
    os.remove(ast_path)
    
    builder = GraphBuilder(verilog_code_lines=verilog_lines)
    graph = builder.build_from_xml_root(tree.getroot())

    # 4. Generate DOT string from the graph model
    print("Generating DOT file content...")
    dot_content = generate_dot(graph, 'CFG', args)

    # 5. Output DOT file or render image with Graphviz
    if args.format == 'dot':
        with open(args.output_file, 'w') as f:
            f.write(dot_content)
        print(f"✅ Wrote DOT -> {args.output_file}")
    else:
        print(f"Rendering {args.format.upper()} via Graphviz (engine={args.layout_engine})...")
        try:
            cmd_dot = ['dot', f'-K{args.layout_engine}', f'-T{args.format}', '-o', args.output_file]
            res = subprocess.run(cmd_dot, input=dot_content, text=True, check=True, capture_output=True)
            if res.stderr:
                print(f"Graphviz warnings:\n{res.stderr}")
            print(f"✅ Output -> {args.output_file}")
        except FileNotFoundError:
            sys.exit("Error: 'dot' (Graphviz) not found. Please install Graphviz.")
        except subprocess.CalledProcessError as e:
            sys.exit(f"Graphviz error:\n{e.stderr}\n{e.stdout}")

if __name__ == '__main__':
    main()