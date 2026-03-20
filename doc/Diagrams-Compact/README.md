# Sally SCADA - Compact Thesis Diagrams

Simplified, greyscale Mermaid diagrams optimized for academic thesis documentation.

## Diagrams

| # | File | Description |
|---|------|-------------|
| 1 | [01-SystemArchitecture.mmd](01-SystemArchitecture.mmd) | High-level system architecture overview |
| 2 | [02-HDF5Simulation.mmd](02-HDF5Simulation.mmd) | HDF5 simulation component |
| 3 | [03-TimescaleDB-ER.mmd](03-TimescaleDB-ER.mmd) | Database entity-relationship diagram |
| 4 | [04-EventDataFlow.mmd](04-EventDataFlow.mmd) | Event lifecycle from source to output |
| 5 | [05-TTStack.mmd](05-TTStack.mmd) | Observability stack (OTEL + Grafana) |
| 6 | [06-SequenceSimStep.mmd](06-SequenceSimStep.mmd) | Simulation step sequence diagram |
| 7 | [07-LayerArchitecture.mmd](07-LayerArchitecture.mmd) | Clean architecture layers |
| 8 | [08-DomainModel.mmd](08-DomainModel.mmd) | Domain model class diagram |
| 9 | [09-Deployment.mmd](09-Deployment.mmd) | Deployment architecture |
| 10 | [10-EventBus.mmd](10-EventBus.mmd) | EventBus internal architecture |

## Design Choices

- **Greyscale palette**: Professional academic appearance
- **Compact layout**: Reduced complexity for readability
- **Essential information only**: Removed implementation details

## Color Scheme

| Element | Color | Hex |
|---------|-------|-----|
| Default fill | Light grey | `#f5f5f5` |
| Highlight fill | Medium grey | `#d4d4d4` |
| Core component | Dark grey | `#e5e5e5` |
| Borders | Charcoal | `#525252` |
| Text | Near black | `#171717` |

## Rendering

```bash
# Using mermaid-cli
mmdc -i diagram.mmd -o diagram.png -b white -t neutral
```

## Thesis Chapter Mapping

| Chapter | Diagrams |
|---------|----------|
| System Architecture | 01, 07, 09 |
| Simulation Engine | 02, 06 |
| Event-Driven Design | 04, 10 |
| Data Management | 03 |
| Observability | 05 |
| Domain Model | 08 |
