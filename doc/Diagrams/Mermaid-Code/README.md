# Sally SCADA System - Architecture Diagrams

This directory contains comprehensive Mermaid diagrams documenting the Sally SCADA System architecture for thesis documentation.

## Rendering Instructions

### Light Theme Configuration
All diagrams use a **light theme (white background)** with the following Mermaid initialization:

```javascript
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#4A90D9', 'background': '#ffffff', ... }}}%%
```

### Rendering Options

1. **VS Code**: Install "Mermaid Preview" or "Markdown Preview Mermaid Support" extension
2. **Online**: Use [Mermaid Live Editor](https://mermaid.live/)
3. **CLI**: Use `mmdc` (mermaid-cli) for PNG/SVG export:
   ```bash
   npm install -g @mermaid-js/mermaid-cli
   mmdc -i diagram.mmd -o diagram.png -b white
   ```

4. **LaTeX Conversion**: For TikZ conversion, consider:
   - Export to SVG → Use `svg2tikz` or `Inkscape`
   - Manual conversion using TikZ libraries

---

## Diagram Index

### 1. Component Diagrams

| File | Description | Use Case |
|------|-------------|----------|
| [01-HDF5-Simulation-Component.mmd](01-HDF5-Simulation-Component.mmd) | HDF5-based SmartGridSimulation internal architecture | Thesis section on simulation architecture |
| [02-Mosaik-Simulation-Component.mmd](02-Mosaik-Simulation-Component.mmd) | Mosaik co-simulation integration architecture | Thesis section on co-simulation |

### 2. Data Diagrams

| File | Description | Use Case |
|------|-------------|----------|
| [03-TimescaleDB-ER-Diagram.mmd](03-TimescaleDB-ER-Diagram.mmd) | Entity-Relationship diagram for TimescaleDB schema | Database design documentation |
| [10-Class-Diagram-Domain.mmd](10-Class-Diagram-Domain.mmd) | Domain model class diagram (Events, Entities, State) | Domain-Driven Design section |

### 3. Architecture Diagrams

| File | Description | Use Case |
|------|-------------|----------|
| [04-Orchestration-Block-Diagram.mmd](04-Orchestration-Block-Diagram.mmd) | System orchestration with all major components | High-level architecture overview |
| [11-C4-Context-Diagram.mmd](11-C4-Context-Diagram.mmd) | C4 Context diagram showing external actors/systems | System context documentation |
| [13-Deployment-Diagram.mmd](13-Deployment-Diagram.mmd) | Physical/container deployment architecture | Infrastructure documentation |
| [17-Layer-Architecture.mmd](17-Layer-Architecture.mmd) | Clean Architecture layer diagram | Software architecture section |

### 4. Data Flow Diagrams

| File | Description | Use Case |
|------|-------------|----------|
| [05-DataFlow-RuleTriggered-Event.mmd](05-DataFlow-RuleTriggered-Event.mmd) | Complete event lifecycle from HDF5 → Rule Trigger → GUI | Event-driven architecture explanation |
| [14-EventBus-Architecture.mmd](14-EventBus-Architecture.mmd) | High-performance EventBus internal architecture | Performance optimization section |
| [16-RuleChain-Evaluation-Flow.mmd](16-RuleChain-Evaluation-Flow.mmd) | Rule evaluation with chaining logic (AND/OR) | Rule engine documentation |

### 5. Sequence Diagrams

| File | Description | Use Case |
|------|-------------|----------|
| [07-Sequence-SimulationStep.mmd](07-Sequence-SimulationStep.mmd) | Single simulation step execution flow | Simulation execution section |
| [08-Sequence-SetpointChange.mmd](08-Sequence-SetpointChange.mmd) | Setpoint change from GUI to simulation | Control interface documentation |
| [09-Sequence-SystemStartup.mmd](09-Sequence-SystemStartup.mmd) | Complete system initialization sequence | System startup documentation |
| [15-Sequence-MQTTBridge.mmd](15-Sequence-MQTTBridge.mmd) | MQTT bridge communication with web frontend | Web integration section |
| [18-Sequence-DatabasePersistence.mmd](18-Sequence-DatabasePersistence.mmd) | Database persistence and query flow | Data persistence section |

### 6. State Diagrams

| File | Description | Use Case |
|------|-------------|----------|
| [12-State-Diagram-Simulation.mmd](12-State-Diagram-Simulation.mmd) | Simulation lifecycle state machine | State management documentation |

### 7. Infrastructure Diagrams

| File | Description | Use Case |
|------|-------------|----------|
| [06-TT-Stack-Telemetry-Architecture.mmd](06-TT-Stack-Telemetry-Architecture.mmd) | Complete TT-Stack with Grafana, Prometheus, Loki, Tempo, OTEL | Observability infrastructure section |

---

## Diagram Categories by Thesis Section

### Chapter: System Architecture
- [11-C4-Context-Diagram.mmd](11-C4-Context-Diagram.mmd) - System context
- [04-Orchestration-Block-Diagram.mmd](04-Orchestration-Block-Diagram.mmd) - Component orchestration
- [17-Layer-Architecture.mmd](17-Layer-Architecture.mmd) - Clean architecture layers
- [13-Deployment-Diagram.mmd](13-Deployment-Diagram.mmd) - Deployment topology

### Chapter: Simulation Engine
- [01-HDF5-Simulation-Component.mmd](01-HDF5-Simulation-Component.mmd) - HDF5 simulation
- [02-Mosaik-Simulation-Component.mmd](02-Mosaik-Simulation-Component.mmd) - Mosaik co-simulation
- [12-State-Diagram-Simulation.mmd](12-State-Diagram-Simulation.mmd) - Simulation states
- [07-Sequence-SimulationStep.mmd](07-Sequence-SimulationStep.mmd) - Step execution

### Chapter: Event-Driven Architecture
- [14-EventBus-Architecture.mmd](14-EventBus-Architecture.mmd) - EventBus internals
- [10-Class-Diagram-Domain.mmd](10-Class-Diagram-Domain.mmd) - Event class hierarchy
- [05-DataFlow-RuleTriggered-Event.mmd](05-DataFlow-RuleTriggered-Event.mmd) - Event lifecycle

### Chapter: Rule Management
- [16-RuleChain-Evaluation-Flow.mmd](16-RuleChain-Evaluation-Flow.mmd) - Rule evaluation

### Chapter: Data Management
- [03-TimescaleDB-ER-Diagram.mmd](03-TimescaleDB-ER-Diagram.mmd) - Database schema
- [18-Sequence-DatabasePersistence.mmd](18-Sequence-DatabasePersistence.mmd) - Persistence flow

### Chapter: User Interface
- [08-Sequence-SetpointChange.mmd](08-Sequence-SetpointChange.mmd) - GUI interaction
- [15-Sequence-MQTTBridge.mmd](15-Sequence-MQTTBridge.mmd) - Web interface

### Chapter: Observability
- [06-TT-Stack-Telemetry-Architecture.mmd](06-TT-Stack-Telemetry-Architecture.mmd) - Complete stack
- [09-Sequence-SystemStartup.mmd](09-Sequence-SystemStartup.mmd) - Telemetry initialization

---

## Color Coding Convention

All diagrams use consistent color coding:

| Color | Hex | Meaning |
|-------|-----|---------|
| Blue | `#dbeafe` | Data sources, external systems |
| Green | `#dcfce7` | Core services, simulation components |
| Yellow | `#fef3c7` | Application layer, rules, configuration |
| Pink | `#fce7f3` | Orchestration, events |
| Purple | `#ede9fe` | Telemetry, observability |
| Indigo | `#e0e7ff` | Infrastructure services |
| Light Green | `#f0fdf4` | Presentation layer, GUI |
| Gray | `#f3f4f6` | External dependencies |

---

## LaTeX TikZ Conversion Notes

For conversion to LaTeX TikZ:

1. **Flowcharts**: Use `tikz` with `shapes`, `arrows`, `positioning` libraries
2. **Sequence Diagrams**: Use `pgf-umlsd` package
3. **ER Diagrams**: Use `tikz-er2` or `tikz` with custom nodes
4. **Class Diagrams**: Use `tikz-uml` package
5. **State Diagrams**: Use `automata` library

Example TikZ preamble:
```latex
\\usepackage{tikz}
\\usetikzlibrary{shapes, arrows, positioning, fit, backgrounds, calc}
\\usepackage{pgf-umlsd}
\\usepackage{tikz-uml}
```

---

## Modification Guidelines

When modifying diagrams:

1. **Keep theme consistent**: Always include the `%%{init: ...}%%` directive
2. **Use semantic class names**: Apply styling via `classDef` and `class` statements
3. **Document changes**: Update this README when adding new diagrams
4. **Test rendering**: Verify diagrams render correctly before committing

---

*Generated for Sally SCADA System Thesis Documentation*
*Last Updated: February 2026*
