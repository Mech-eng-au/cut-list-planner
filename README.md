# Cut List Planner

A **woodworking and material optimization tool** for planning and optimizing cut lists. Minimize waste, save costs, and streamline your workflow for projects like furniture, frames, and custom builds.

---

## Features

- **Optimization Algorithms**: Uses branch-and-bound and greedy algorithms to optimize material usage.
- **Parameter Sweeping**: Evaluate trade-offs (e.g., cost vs. material) with Pareto analysis.
- **Project Management**: Load, save, and manage projects with `.toml` configurations.
- **User-Friendly UI**: Intuitive interface for adding parts, variables, and visualizing results.

---

## Project Structure

```text
cut-list-planner/
├── engine/               # Core logic for optimization and expressions
├── projects/             # Predefined project configurations (e.g., braced_frame.toml)
├── state/                # Data models and serialization
├── ui/                   # User interface components
│   ├── formatters/       # Result formatters (e.g., cut sequences, comparisons)
│   ├── screens/          # UI screens (e.g., project browser, add part)
│   ├── tabs/             # UI tabs (e.g., project, results, sweep)
│   └── widgets/          # Reusable UI widgets (e.g., diagrams, fields)
├── __main__.py           # Entry point
└── log.py                # Logging utilities
```

---

### Prerequisites

- Python 3.8+
- pip

## Usage

1. **Load a Project**: Open a predefined project (e.g., `braced_frame.toml`) or create a new one.
2. **Add Parts**: Define parts and their dimensions in the **Add Part** screen.
3. **Set Variables**: Configure variables (e.g., material thickness, cost) in the **Add Variable** screen.
4. **Run Optimization**: Use the **Results** tab to optimize the cut list.
5. **Analyze Sweeps**: Use the **Sweep** tab to evaluate parameter trade-offs.

---

## Example Projects

- `braced_frame.toml`: A simple braced frame project.
- `shelf_unit.toml`: A shelf unit with multiple parts.
- `woodworking_table.toml`: A custom woodworking table.

---

## Contributing

Contributions are welcome! Open an issue or submit a pull request.

---

## License

This project is licensed under the [MIT License](LICENSE).