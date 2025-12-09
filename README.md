# BehaVer: Automated Behavioral & Structural Visualization for Verilog Designs

BehaVer is a tool designed to bridge the gap between raw Verilog code and high-level system understanding. It parses multi-file Verilog projects and automatically generates interactive, hierarchical visualizations of both the structural architecture (RTL) and behavioral logic (FSMs, Control Flow).

By leveraging **Verilator** for AST generation and **Graphviz** for rendering, BehaVer creates an "X-ray" view of hardware designs, allowing engineers to verify connectivity and logic flow efficiently.

---

## Key Features

- **Multi-File AST Parsing**  
  Automatically resolves cross-module references and handles include paths using Verilator.

- **Optimization Handling**  
  Processes synthesis optimizations (e.g., pre-calculating constant assignments) to reflect actual synthesized logic.

- **Structural Analysis (RTL View)**  
  Visualizes module instances, inputs, outputs, and infers signal flow directionality.

- **Bus Aggregation**  
  Groups individual wires into thick bus connections to reduce visual clutter.

- **Behavioral Analysis**  
  Extracts control flow from blocks like `always`, `initial`, and `assign`, labeling nodes with the actual logic equations.

- **Interactive Web Dashboard**  
  A browser-based viewer (`viewer.html`) allowing users to drill down from top-level modules into specific sub-modules and logic blocks.

---

## System Architecture

- **Input:** Verilog source files (`*.v`)
- **Preprocessing:** Invokes Verilator to generate a standard XML Abstract Syntax Tree (AST)
- **Parsing:** A Python engine (`GraphBuilder`) traverses the AST to build an object-oriented memory model of the design
- **Rendering:** Converts the model into DOT syntax, applying stylistic attributes
- **Output:** Generates interactive SVG images wrapped in a comprehensive HTML dashboard

---

## Prerequisites

To run BehaVer, you need the following dependencies installed on your system:

- Python 3.x  
- Verilator  
- Graphviz  
