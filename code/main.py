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
from dot_generator import generate_all_dots # Updated import

def main():
    p = argparse.ArgumentParser(description="Generate linked, multi-level CFG/DFG from Verilog")
    p.add_argument('verilog_file', help="Verilog source file")
    p.add_argument('-t', '--top', dest='top_module', help="Top-level module name")
    p.add_argument('-o', '--output', dest='output_file', help="Base output name (e.g. mygraph.svg).")
    p.add_argument('--format', choices=['svg', 'png', 'dot', 'pdf'], default='svg', help="Output format. Use svg for interactive links.")
    p.add_argument('--layout-engine', choices=['dot', 'fdp', 'neato', 'circo', 'twopi'], default='dot', help="Graphviz layout engine")
    p.add_argument('--no-inter-cluster-dfg', action='store_true', help="Hide DFG edges across procedural boundaries")
    args = p.parse_args()

    # --- Setup Output ---
    if not args.output_file:
        base = os.path.splitext(os.path.basename(args.verilog_file))[0]
        # The main architectural file will be named based on this
        args.output_file = f"{base}_arch.{args.format}"
        print(f"Warning: No output file specified. Defaulting base name to '{base}'")

    output_basename = os.path.splitext(os.path.basename(args.output_file))[0].replace('_arch', '')
    output_dir = os.path.dirname(args.output_file) or '.'

    # --- Run Verilator ---
    try:
        with open(args.verilog_file, 'r') as f:
            verilog_lines = f.readlines()
    except FileNotFoundError:
        sys.exit(f"Error: Cannot open Verilog file '{args.verilog_file}'")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as tmp:
        ast_path = tmp.name
    cmd = ['verilator', '--xml-only', '--xml-output', ast_path, '-Wno-fatal', args.verilog_file]
    if args.top_module:
        cmd += ['--top-module', args.top_module]
    print("Invoking Verilator...")
    try:
        subprocess.run(cmd, check=True, text=True, capture_output=True)
    except FileNotFoundError:
        sys.exit("Error: 'verilator' not found. Please install Verilator.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"Verilator error:\n{e.stderr}\n{e.stdout}")

    # --- Build Graph Hierarchy ---
    print("Parsing AST and building graph hierarchy...")
    tree = ET.parse(ast_path)
    os.remove(ast_path)
    
    builder = GraphBuilder(verilog_code_lines=verilog_lines)
    hierarchy = builder.build_from_xml_root(tree.getroot())

    # --- Generate All DOT Files ---
    print("Generating all DOT files...")
    dot_files = generate_all_dots(hierarchy, output_basename, args)

    # --- Save and Render All Graphs ---
    for dot_filename, dot_content in dot_files.items():
        base_dot_name = os.path.splitext(dot_filename)[0]
        
        dot_filepath = os.path.join(output_dir, dot_filename)
        if args.format == 'dot':
            with open(dot_filepath, 'w') as f:
                f.write(dot_content)
            print(f"✅ Wrote DOT -> {dot_filepath}")
            continue

        output_filepath = os.path.join(output_dir, f"{base_dot_name}.{args.format}")
        print(f"Rendering {output_filepath} via Graphviz (engine={args.layout_engine})...")
        try:
            cmd_dot = ['dot', f'-K{args.layout_engine}', f'-T{args.format}', '-o', output_filepath]
            res = subprocess.run(cmd_dot, input=dot_content, text=True, check=True, capture_output=True)
            if res.stderr:
                print(f"Graphviz warnings:\n{res.stderr}")
            print(f"✅ Wrote Output -> {output_filepath}")
        except FileNotFoundError:
            sys.exit("Error: 'dot' (Graphviz) not found. Please install Graphviz.")
        except subprocess.CalledProcessError as e:
            sys.exit(f"Graphviz error:\n{e.stderr}\n{e.stdout}")

    print(f"\n✨ Process complete! Start by opening the main architectural view: {output_basename}_arch.{args.format}")


if __name__ == '__main__':
    main()
