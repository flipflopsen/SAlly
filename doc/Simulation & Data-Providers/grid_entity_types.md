# Supported Entity Types

## Grid Entities

This document lists all supported grid entity types, their measurement characteristics, and their mapping to visualization assets and simulation classes.

### Entity Types & Measurements

| Entity Type | Description | Measurements / Attributes |
|---|---|---|
| **PANDAPOWER_BUS** | Busbar / Node | `vm_pu` (Voltage Magnitude p.u.), `va_degree` (Voltage Angle), `p_mw` (Active Power), `q_mvar` (Reactive Power) |
| **PANDAPOWER_LOAD** | Load / Consumer | `p_mw`, `q_mvar`, `sn_mva` |
| **PANDAPOWER_SGEN** | Static Generator (PV, Wind, etc.) | `p_mw`, `q_mvar`, `min_p_mw`, `max_p_mw` |
| **PANDAPOWER_TRAFO** | Transformer | `loading_percent` |
| **PANDAPOWER_LINE** | Transmission Line | `loading_percent`, `max_i_ka` |
| **PANDAPOWER_SWITCH** | Switch / Breaker | `in_service`, `closed` |
| **PANDAPOWER_EXT_GRID**| External Grid connection | (Reference bus attributes) |
| **PYPOWER_NODE** | Busbar (PyPower) | `p`, `q`, `va`, `vl`, `vm` |
| **PYPOWER_BRANCH** | Branch (Line) | `p_from`, `p_to`, `q_from` |
| **PYPOWER_TRANSFORMER**| Transformer (PyPower) | `p_from`, `p_to`, `q_from` |
| **HOUSEHOLD_SIM** | Simulated Household | `p_out` |
| **CSV_PV** | PV System (from CSV) | `p` |
| **WIND_TURBINE** | Wind Turbine | `p`, `q` |
| **BATTERY_ESS** | Battery Storage | `p`, `q` |
| **LOAD_BUS** | Generic Load Bus | `p`, `q` |

### Visualization & Implementation Mapping

| Entity Name | Asset Image | Implementation Class |
|---|---|---|
| CSV_PV | `photovoltaik.png` | `sally.application.simulation.mosaik_simulators.pv.PVSim` |
| WIND_TURBINE | `wind_turbine.png` | `sally.application.simulation.mosaik_simulators.generator.GeneratorSim` |
| HOUSEHOLD_SIM | `house.png` | `sally.application.simulation.mosaik_simulators.load.LoadSim` |
| BATTERY_ESS | `industry.png` | `sally.application.simulation.mosaik_simulators.battery.BatterySim` |
| PANDAPOWER_BUS | `bus.png` | `pandapower.create.create_bus` |
| PANDAPOWER_LOAD | `load.png` | `pandapower.create.create_load` |
| PANDAPOWER_SGEN | `generator.png` | `pandapower.create.create_sgen` |
| PANDAPOWER_TRAFO | `trafo.png` | `pandapower.create.create_transformer` |
| PANDAPOWER_EXT_GRID | `ext_grid.png` | `pandapower.create.create_ext_grid` |
| PANDAPOWER_SWITCH | `switch.png` | `pandapower.create.create_switch` |
