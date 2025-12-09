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

def create_viewer_html(output_dir, top_module_arch_svg_basename, module_views, graphs_subdir):
    """Creates a dynamic viewer.html file with a module selector."""
    
    options_html = ""
    for module in module_views:
        # Point to the file inside the graphs subdirectory
        file_path = f"{graphs_subdir}/{module['file_base']}.svg"
        options_html += f'          <option value="{file_path}">{module["name"]}</option>\n'

    # Default view also needs the subdir prefix
    default_view = f"{graphs_subdir}/{top_module_arch_svg_basename}.svg"

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BehaVer Design Explorer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    fontFamily: {{
                        sans: ['Inter', 'sans-serif'],
                        mono: ['JetBrains Mono', 'monospace'],
                    }},
                    colors: {{
                        brand: {{
                            50: '#eff6ff',
                            100: '#dbeafe',
                            500: '#3b82f6',
                            600: '#2563eb',
                            700: '#1d4ed8',
                            900: '#1e3a8a',
                        }}
                    }}
                }}
            }}
        }}
    </script>
    <style>
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: #f1f5f9; }}
        ::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #94a3b8; }}
        .glass-panel {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(226, 232, 240, 0.8);
        }}
    </style>
</head>
<body class="bg-slate-100 text-slate-800 flex flex-col h-screen overflow-hidden">

    <nav class="glass-panel shadow-sm z-10 relative">
        <div class="max-w-8xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16 items-center">
                <div class="flex items-center gap-3">
                    <div class="bg-gradient-to-br from-brand-500 to-brand-700 text-white p-2 rounded-lg shadow-lg shadow-brand-500/30">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                        </svg>
                    </div>
                    <div>
                        <h1 class="text-xl font-extrabold tracking-tight text-slate-900 leading-tight">BehaVer</h1>
                        <p class="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Design Explorer</p>
                    </div>
                </div>

                <div class="flex items-center gap-3">
                    <button id="home-button" class="group flex items-center gap-2 bg-white border border-slate-200 hover:border-brand-500 hover:text-brand-600 text-slate-600 px-4 py-2 rounded-lg transition-all duration-200 shadow-sm font-semibold text-sm">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 group-hover:scale-110 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                        </svg>
                        Top Module
                    </button>

                    <div class="relative group">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <svg class="h-4 w-4 text-slate-400 group-focus-within:text-brand-500 transition-colors" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7" />
                            </svg>
                        </div>
                        <select id="module-selector" class="appearance-none bg-white border border-slate-200 text-slate-700 text-sm rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 block w-64 pl-10 p-2.5 shadow-sm font-medium transition-all cursor-pointer hover:border-slate-300">
{options_html}
                        </select>
                        <div class="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                             <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </nav>

    <main class="flex-1 flex flex-col p-4 sm:p-6 overflow-hidden">
        <div class="flex-1 bg-white rounded-xl shadow-xl shadow-slate-200/60 border border-slate-200 flex flex-col overflow-hidden relative group">
            <div class="h-10 border-b border-slate-100 flex items-center justify-between px-4 bg-slate-50/50 backdrop-blur-sm">
                <div class="flex items-center gap-2">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Viewing:</span>
                    <span id="current-view-label" class="bg-white border border-slate-200 text-brand-700 font-mono text-[11px] px-2 py-0.5 rounded shadow-sm">...</span>
                </div>
                <div class="flex gap-1.5 opacity-60">
                    <div class="w-2.5 h-2.5 rounded-full bg-slate-300"></div>
                    <div class="w-2.5 h-2.5 rounded-full bg-slate-300"></div>
                    <div class="w-2.5 h-2.5 rounded-full bg-slate-300"></div>
                </div>
            </div>
            <div class="flex-1 relative bg-slate-50/30 w-full h-full">
                <iframe id="viewer-frame" class="absolute inset-0 w-full h-full" src=""></iframe>
            </div>
        </div>
    </main>

    <script>
        const viewerFrame = document.getElementById('viewer-frame');
        const currentViewLabel = document.getElementById('current-view-label');
        const homeButton = document.getElementById('home-button');
        const moduleSelector = document.getElementById('module-selector');
        
        const architecturalViewSrc = '{default_view}';

        function setView(src) {{
            if (!src) return;
            viewerFrame.src = src;
            currentViewLabel.textContent = src;
            if (moduleSelector.value !== src) {{
                moduleSelector.value = src;
            }}
            const newUrl = new URL(window.location);
            newUrl.searchParams.set('file', src);
            window.history.replaceState(null, '', newUrl);
        }}

        document.addEventListener('DOMContentLoaded', () => {{
            const urlParams = new URLSearchParams(window.location.search);
            const fileParam = urlParams.get('file');
            if (fileParam) {{
                setView(fileParam);
            }} else {{
                setView(architecturalViewSrc);
            }}
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
    print(f"Wrote Viewer -> {viewer_path}")

def main():
    p = argparse.ArgumentParser(description="Generate linked, multi-level CFG/DFG from Verilog")
    p.add_argument('verilog_files', nargs='+', help="Verilog source files (one or more)")
    p.add_argument('-t', '--top', dest='top_module', help="Top-level module name for the main viewer.")
    p.add_argument('-o', '--output', dest='output_dir', help="Output directory for generated files.")
    p.add_argument('--format', choices=['svg', 'png', 'dot', 'pdf'], default='svg', help="Output format. Use svg for interactive links.")
    p.add_argument('--layout-engine', choices=['dot', 'fdp', 'neato', 'circo', 'twopi'], default='dot', help="Graphviz layout engine")
    p.add_argument('--no-inter-cluster-dfg', action='store_true', help="Hide DFG edges across procedural boundaries")
    p.add_argument('--save-dot', action='store_true', help="Save intermediate DOT files even if generating other formats.")

    args = p.parse_args()

    base_name = os.path.splitext(os.path.basename(args.verilog_files[0]))[0]
    
    # 1. Setup Directory Structure
    if args.output_dir:
        root_output_dir = args.output_dir
    else:
        # Places the project folder inside a 'results' parent directory
        root_output_dir = os.path.join("results", f"{base_name}_results")
    
    graphs_subdir = f"{base_name}_graphs"
    dot_subdir = f"{base_name}_dot"
    
    full_graphs_path = os.path.join(root_output_dir, graphs_subdir)
    full_dot_path = os.path.join(root_output_dir, dot_subdir)

    if not os.path.exists(root_output_dir):
        os.makedirs(root_output_dir)
        
    if not os.path.exists(full_graphs_path):
        os.makedirs(full_graphs_path)
        
    if args.save_dot and not os.path.exists(full_dot_path):
        os.makedirs(full_dot_path)

    print(f"Output Directory: {root_output_dir}")
    print(f"Graphs Directory: {full_graphs_path}")
    if args.save_dot:
        print(f"DOT Directory:    {full_dot_path}")

    # 2. Config args for correct linking in nested folders
    # If the viewer is in root and SVGs are in graphs/, the link from an SVG back to viewer is '../viewer.html'
    args.viewer_rel_path = "../viewer.html" 
    # The 'file' param in URL needs to point to 'graphs_subdir/file.svg'
    args.graphs_rel_path = f"{graphs_subdir}/"

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
        dot_files = generate_all_dots(hierarchy, module_output_basename, base_name, args)
        all_dot_files.update(dot_files)

    for dot_filename, dot_content in all_dot_files.items():
        base_dot_name = os.path.splitext(dot_filename)[0]
        
        # Save DOT if requested (into the dot subdir)
        if args.format == 'dot' or args.save_dot:
            path = os.path.join(full_dot_path, dot_filename)
            with open(path, 'w') as f:
                f.write(dot_content)
            if args.format == 'dot':
                print(f"Wrote DOT -> {path}")
                continue

        # Render SVG/PNG (into the graphs subdir)
        output_filepath = os.path.join(full_graphs_path, f"{base_dot_name}.{args.format}")
        print(f"Rendering {output_filepath}...")
        try:
            cmd_dot = ['dot', f'-K{args.layout_engine}', f'-T{args.format}', '-o', output_filepath]
            res = subprocess.run(cmd_dot, input=dot_content, text=True, check=True, capture_output=True)
            if res.stderr:
                print(f"Graphviz warnings:\n{res.stderr}")
            print(f"Wrote Output -> {output_filepath}")
        except FileNotFoundError:
            sys.exit("Error: 'dot' (Graphviz) not found. Please install Graphviz.")
        except subprocess.CalledProcessError as e:
            sys.exit(f"Graphviz error:\n{e.stderr}\n{e.stdout}")
            
    if args.format == 'svg':
        top_module_name = ""
        found_top = False
        if args.top_module:
            for h in hierarchies:
                if h.name == args.top_module:
                    top_module_name = h.name
                    found_top = True
                    break
                if h.name.startswith(args.top_module + "__"):
                    top_module_name = h.name
                    found_top = True
                    break

        if not found_top:
            if args.top_module:
                print(f"Warning: Top module '{args.top_module}' not found (or renamed by Verilator). Defaulting to first module: {hierarchies[0].name}")
            top_module_name = hierarchies[0].name
        
        top_module_arch_svg_basename = f"{base_name}_{top_module_name}_arch"

        module_views = []
        for h in hierarchies:
            module_views.append({
                'name': h.name,
                'file_base': f"{base_name}_{h.name}_arch"
            })

        # Generate viewer.html in the root output dir, pointing to graphs subdir
        create_viewer_html(root_output_dir, top_module_arch_svg_basename, module_views, graphs_subdir)

    print(f"\nProcess complete! Open this file in your browser: {os.path.join(root_output_dir, 'viewer.html')}")


if __name__ == '__main__':
    main()