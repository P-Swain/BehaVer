#!/usr/bin/env python3
# File: main.py

import xml.etree.ElementTree as ET
import subprocess
import sys
import os
import argparse
import tempfile
import shutil

# Import our custom modules
from graph_builder import GraphBuilder
from dot_generator import generate_all_dots

def create_viewer_html(output_dir, top_module_arch_svg_basename, module_views):
    """Creates a dynamic viewer.html file with a module selector."""
    
    options_html = ""
    for module in module_views:
        options_html += f'          <option value="{module["file_base"]}.svg">{module["name"]}</option>\n'

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interactive Verilog Graph Viewer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{
            font-family: 'Inter', sans-serif;
        }}
        #viewer-frame {{
            border: 1px solid #e2e8f0;
            border-radius: 0.5rem;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        }}
    </style>
</head>
<body class="bg-slate-50 text-slate-800 flex flex-col h-screen p-4 md:p-6">

    <header class="mb-4">
        <h1 class="text-2xl font-bold text-slate-900">Verilog Design Explorer</h1>
        <p class="text-slate-600">Click on a component in the architectural view to drill down into its detailed implementation.</p>
    </header>

    <div id="navigation-bar" class="flex items-center flex-wrap gap-4 bg-white p-3 rounded-lg shadow-sm mb-4 border border-slate-200">
        <button id="home-button" class="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-md transition-colors duration-200">
            Home (Top Module)
        </button>

        <div class="flex items-center gap-2">
            <label for="module-selector" class="font-semibold text-slate-700">Select Module:</label>
            <select id="module-selector" class="bg-white border border-slate-300 rounded-md py-2 px-3 focus:outline-none focus:ring-2 focus:ring-blue-500">
{options_html}
            </select>
        </div>

        <div class="flex items-center gap-2 ml-auto">
            <span class="font-semibold text-slate-700">Current View:</span>
            <span id="current-view-label" class="bg-slate-100 text-slate-800 font-mono text-sm px-3 py-1 rounded-md"></span>
        </div>
    </div>

    <main class="flex-1 bg-white rounded-lg overflow-hidden">
        <iframe id="viewer-frame" class="w-full h-full" src=""></iframe>
    </main>

    <script>
        const viewerFrame = document.getElementById('viewer-frame');
        const currentViewLabel = document.getElementById('current-view-label');
        const homeButton = document.getElementById('home-button');
        const moduleSelector = document.getElementById('module-selector');
        
        const architecturalViewSrc = '{top_module_arch_svg_basename}.svg';

        function setView(src) {{
            if (src) {{
                viewerFrame.src = src;
                currentViewLabel.textContent = src;
                if (moduleSelector.value !== src) {{
                    moduleSelector.value = src;
                }}
            }} else {{
                 viewerFrame.src = 'about:blank';
                 currentViewLabel.textContent = 'No SVG loaded. Please generate graphs first.';
            }}
        }}

        document.addEventListener('DOMContentLoaded', () => {{
            setView(architecturalViewSrc);
        }});

        homeButton.addEventListener('click', () => {{
            setView(architecturalViewSrc);
        }});

        moduleSelector.addEventListener('change', (event) => {{
            setView(event.target.value);
        }});
    </script>
</body>
</html>
"""
    viewer_path = os.path.join(output_dir, 'viewer.html')
    with open(viewer_path, 'w') as f:
        f.write(html_content)
    print(f"✅ Wrote Viewer -> {viewer_path}")

def main():
    p = argparse.ArgumentParser(description="Generate linked, multi-level CFG/DFG from Verilog")
    p.add_argument('verilog_files', nargs='+', help="Verilog source files (one or more)")
    p.add_argument('-t', '--top', dest='top_module', help="Top-level module name for the main viewer.")
    p.add_argument('-o', '--output', dest='output_dir', help="Output directory for generated files.")
    p.add_argument('--format', choices=['svg', 'png', 'dot', 'pdf'], default='svg', help="Output format. Use svg for interactive links.")
    p.add_argument('--layout-engine', choices=['dot', 'fdp', 'neato', 'circo', 'twopi'], default='dot', help="Graphviz layout engine")
    p.add_argument('--no-inter-cluster-dfg', action='store_true', help="Hide DFG edges across procedural boundaries")
    args = p.parse_args()

    base_name = os.path.splitext(os.path.basename(args.verilog_files[0]))[0]
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = os.path.join('results', f"{base_name}_graphs")
        print(f"Warning: No output directory specified. Defaulting to '{output_dir}'")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    verilog_lines = []
    include_dirs = set()
    
    for v_file in args.verilog_files:
        abs_path = os.path.abspath(v_file)
        include_dirs.add(os.path.dirname(abs_path))
        try:
            with open(v_file, 'r') as f:
                verilog_lines.extend(f.readlines())
        except FileNotFoundError:
            sys.exit(f"Error: Cannot open Verilog file '{v_file}'")

    include_flags = [f"-I{d}" for d in include_dirs]

    # Debug mode: fix path to inspect XML
    ast_path = "debug_ast.xml"
    
    cmd = ['verilator', '--xml-only'] + include_flags + args.verilog_files + ['--xml-output', ast_path, '-Wno-fatal']
    
    print(f"Invoking Verilator on {len(args.verilog_files)} files...")
    
    try:
        subprocess.run(cmd, check=True, text=True, capture_output=True)
    except FileNotFoundError:
        sys.exit("Error: 'verilator' not found. Please install Verilator.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"Verilator error:\n{e.stderr}\n{e.stdout}")

    print("Parsing AST and building graph hierarchy for all modules...")
    tree = ET.parse(ast_path)
    
    builder = GraphBuilder(verilog_code_lines=verilog_lines)
    hierarchies = builder.build_from_xml_root(tree.getroot())
    
    if not hierarchies:
        sys.exit("Error: No modules found in the Verilog files.")

    print("Generating all DOT files...")
    all_dot_files = {}
    for hierarchy in hierarchies:
        module_output_basename = f"{base_name}_{hierarchy.name}"
        # CHANGED: Passed 'base_name' as link_prefix
        dot_files = generate_all_dots(hierarchy, module_output_basename, base_name, args)
        all_dot_files.update(dot_files)

    for dot_filename, dot_content in all_dot_files.items():
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
            
    if args.format == 'svg':
        top_module_name = ""
        if args.top_module and any(h.name == args.top_module for h in hierarchies):
            top_module_name = args.top_module
        else:
            if args.top_module:
                print(f"Warning: Top module '{args.top_module}' not found. Defaulting to first module.")
            top_module_name = hierarchies[0].name
        
        top_module_arch_svg_basename = f"{base_name}_{top_module_name}_arch"

        module_views = []
        for h in hierarchies:
            module_views.append({
                'name': h.name,
                'file_base': f"{base_name}_{h.name}_arch"
            })

        create_viewer_html(output_dir, top_module_arch_svg_basename, module_views)

    print(f"\n✨ Process complete! Open this file in your browser: {os.path.join(output_dir, 'viewer.html')}")


if __name__ == '__main__':
    main()