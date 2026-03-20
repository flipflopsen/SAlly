import random
import time
from typing import Dict, Any, List
from sally.domain.grid_entities import EntityType
from sally.core.logger import get_logger

logger = get_logger(__name__)


class RandomDataProvider:
    """
    Data provider that generates random simulation data for testing and development.
    """

    def __init__(self, num_entities: int = 10, num_timesteps: int = 1000, base_voltage: float = 132.0):
        self.num_entities = num_entities
        self.num_timesteps = num_timesteps
        self.base_voltage = base_voltage
        self.entity_types = [
            EntityType.PYPOWER_NODE, EntityType.CSV_PV, EntityType.WIND_TURBINE,
            EntityType.HOUSEHOLD_SIM, EntityType.LOAD_BUS, EntityType.BATTERY_ESS
        ]

    def generate_timeseries_data(self) -> Dict[str, Dict[str, List[float]]]:
        """Generate random timeseries data for entities"""
        timeseries_data = {}

        for i in range(self.num_entities):
            entity_name = f"Entity_{i+1}"
            entity_type = random.choice(self.entity_types)

            # Generate data based on entity type
            if entity_type == EntityType.PYPOWER_NODE:
                timeseries_data[entity_name] = {
                    'P_MW': [random.uniform(-50, 100) for _ in range(self.num_timesteps)],
                    'Q_MVAR': [random.uniform(-20, 50) for _ in range(self.num_timesteps)],
                    'VM': [random.uniform(0.95, 1.05) for _ in range(self.num_timesteps)],
                    'VA': [random.uniform(-0.2, 0.2) for _ in range(self.num_timesteps)]
                }
            elif entity_type == EntityType.CSV_PV:
                timeseries_data[entity_name] = {
                    'P_MW_out': [max(0, random.uniform(0, 30) * (1 + 0.3 * random.random())) for _ in range(self.num_timesteps)]
                }
            elif entity_type == EntityType.WIND_TURBINE:
                timeseries_data[entity_name] = {
                    'P_MW_out': [max(0, random.uniform(0, 20) * (0.5 + 0.5 * random.random())) for _ in range(self.num_timesteps)],
                    'Q_MVAR': [random.uniform(-5, 5) for _ in range(self.num_timesteps)]
                }
            elif entity_type == EntityType.HOUSEHOLD_SIM:
                timeseries_data[entity_name] = {
                    'P_MW_out': [random.uniform(1, 5) for _ in range(self.num_timesteps)]
                }
            elif entity_type == EntityType.LOAD_BUS:
                timeseries_data[entity_name] = {
                    'P_MW': [random.uniform(10, 50) for _ in range(self.num_timesteps)],
                    'Q_MVAR': [random.uniform(2, 15) for _ in range(self.num_timesteps)]
                }
            elif entity_type == EntityType.BATTERY_ESS:
                timeseries_data[entity_name] = {
                    'P_MW_out': [random.uniform(-10, 10) for _ in range(self.num_timesteps)],
                    'Q_MVAR': [random.uniform(-5, 5) for _ in range(self.num_timesteps)]
                }

        logger.info(f"Generated timeseries data for {len(timeseries_data)} entities")
        return timeseries_data

    def generate_relational_data(self) -> Dict[str, List[List[float]]]:
        """Generate random relational data (connections between entities)"""
        relational_data = {}

        # Create some connection matrices
        for i in range(min(5, self.num_entities)):
            relation_name = f"Connection_Matrix_{i+1}"
            matrix_size = random.randint(3, 10)
            relational_data[relation_name] = [
                [random.random() for _ in range(matrix_size)]
                for _ in range(matrix_size)
            ]

        logger.info(f"Generated relational data with {len(relational_data)} matrices")
        return relational_data


class SinusoidalDataProvider:
    """
    Data provider that generates sinusoidal data patterns for more realistic testing.
    """

    def __init__(self, num_entities: int = 10, num_timesteps: int = 1000, frequency: float = 0.1):
        self.num_entities = num_entities
        self.num_timesteps = num_timesteps
        self.frequency = frequency
        self.time_points = [t * 0.01 for t in range(num_timesteps)]  # Time in seconds

    def generate_timeseries_data(self) -> Dict[str, Dict[str, List[float]]]:
        """Generate sinusoidal timeseries data"""
        timeseries_data = {}

        for i in range(self.num_entities):
            entity_name = f"SinusoidEntity_{i+1}"
            amplitude = random.uniform(10, 50)
            phase = random.uniform(0, 2 * 3.14159)

            timeseries_data[entity_name] = {
                'P_MW': [amplitude * (1 + 0.5 * (1 + random.random())) * (0.5 + 0.5 * abs(t * self.frequency + phase)) for t in self.time_points],
                'Q_MVAR': [amplitude * 0.3 * (1 + 0.5 * (1 + random.random())) * (0.5 + 0.5 * abs(t * self.frequency + phase)) for t in self.time_points],
                'VM': [0.95 + 0.1 * (0.5 + 0.5 * abs(t * self.frequency + phase)) for t in self.time_points]
            }

        logger.info(f"Generated sinusoidal data for {len(timeseries_data)} entities")
        return timeseries_data

    def generate_relational_data(self) -> Dict[str, List[List[float]]]:
        """Generate simple relational data"""
        return {
            "Adjacency_Matrix": [
                [random.random() if random.random() > 0.7 else 0 for _ in range(self.num_entities)]
                for _ in range(self.num_entities)
            ]
        }