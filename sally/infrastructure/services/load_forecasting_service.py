import asyncio
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import time
from sklearn.preprocessing import MinMaxScaler
from sally.core.event_bus import EventHandler, Event, EventBus
from sally.infrastructure.data_management.timescale.timescaledb_connection import TimescaleDBConnection
from sally.domain.events import GridDataEvent, LoadForecastEvent
from sally.domain.grid_entities import GridMeasurement, EntityType

from sally.core.logger import get_logger

logger = get_logger(__name__)


class LoadForecastingService(EventHandler):
    """Advanced load forecasting service using machine learning models"""

    def __init__(self, db: TimescaleDBConnection, event_bus: EventBus):
        self.db = db
        self.event_bus = event_bus
        self.load_entities = set()
        self.historical_data = {}  # Entity -> time series data
        self.scalers = {}  # Entity -> scaler for normalization
        self.forecast_horizons = [15, 30, 60, 120]  # minutes
        self.min_history_points = 100
        self.running = False

        # Simple AR model parameters (in practice, use more sophisticated models)
        self.ar_order = 24  # Autoregressive order
        self.seasonal_period = 96  # 15-minute intervals in 24 hours

    @property
    def event_types(self) -> List[str]:
        return ["grid_data_update"]

    async def handle(self, event: Event) -> None:
        """Process grid data for load forecasting"""
        if isinstance(event, GridDataEvent):
            measurement = event.measurement

            # Track load entities (those consuming power)
            if (measurement.entity_type in [EntityType.LOAD_BUS, EntityType.HOUSEHOLD_SIM] or
                    "LOAD" in measurement.entity or "HOUSE" in measurement.entity):

                self.load_entities.add(measurement.entity)

                # Store historical data for forecasting
                if measurement.entity not in self.historical_data:
                    self.historical_data[measurement.entity] = []

                # Use p_out for households, p for load buses
                load_value = measurement.p_out if measurement.p_out is not None else measurement.p
                if load_value is not None:
                    self.historical_data[measurement.entity].append({
                        'timestamp': measurement.timestamp,
                        'load': abs(load_value)  # Load is positive
                    })

                    # Keep only recent history (last 24 hours)
                    cutoff_time = measurement.timestamp - 86400
                    self.historical_data[measurement.entity] = [
                        point for point in self.historical_data[measurement.entity]
                        if point['timestamp'] > cutoff_time
                    ]

    async def start_forecasting(self) -> None:
        """Start periodic load forecasting"""
        self.running = True
        logger.info("Load forecasting service started")

        while self.running:
            try:
                await self._generate_forecasts()
                await asyncio.sleep(300)  # Generate forecasts every 5 minutes

            except Exception as e:
                logger.error("Error in forecasting loop", error=str(e))
                await asyncio.sleep(60)

    async def _generate_forecasts(self) -> None:
        """Generate load forecasts for all entities"""
        current_time = time.time()

        for entity in self.load_entities:
            if entity in self.historical_data:
                history = self.historical_data[entity]

                if len(history) >= self.min_history_points:
                    try:
                        # Generate forecasts for different horizons
                        for horizon in self.forecast_horizons:
                            forecast_result = await self._forecast_entity_load(
                                entity, history, horizon, current_time
                            )

                            if forecast_result:
                                forecast_event = LoadForecastEvent(
                                    timestamp=current_time,
                                    entity=entity,
                                    horizon_minutes=horizon,
                                    predicted_load=forecast_result['prediction'],
                                    confidence_interval=forecast_result.get('confidence'),
                                    model_accuracy=forecast_result.get('accuracy'),
                                    correlation_id=f"forecast_{entity}_{horizon}_{int(current_time)}"
                                )

                                await self.event_bus.publish(forecast_event)

                                # Store forecast in database
                                await self._store_forecast(forecast_event)

                    except Exception as e:
                        logger.error("Error forecasting for entity",
                                     entity=entity, error=str(e))

    async def _forecast_entity_load(self, entity: str, history: List[Dict],
                                    horizon_minutes: int, forecast_time: float) -> Optional[Dict]:
        """Generate load forecast for a specific entity and horizon"""
        try:
            # Prepare time series data
            timestamps = [point['timestamp'] for point in history]
            loads = [point['load'] for point in history]

            if len(loads) < self.ar_order:
                return None

            # Ensure data is sorted by time
            sorted_data = sorted(zip(timestamps, loads))
            timestamps, loads = zip(*sorted_data)

            # Normalize data
            if entity not in self.scalers:
                self.scalers[entity] = MinMaxScaler()
                normalized_loads = self.scalers[entity].fit_transform(
                    np.array(loads).reshape(-1, 1)
                ).flatten()
            else:
                normalized_loads = self.scalers[entity].transform(
                    np.array(loads).reshape(-1, 1)
                ).flatten()

            # Simple autoregressive forecast
            prediction = self._ar_forecast(normalized_loads, horizon_minutes)

            # Denormalize prediction
            prediction_scaled = self.scalers[entity].inverse_transform(
                [[prediction]]
            )[0][0]

            # Calculate confidence interval (simplified)
            recent_variance = np.var(loads[-24:]) if len(loads) >= 24 else np.var(loads)
            confidence_width = 2 * np.sqrt(recent_variance)  # ~95% confidence

            # Calculate model accuracy based on recent predictions vs actuals
            accuracy = await self._calculate_forecast_accuracy(entity, horizon_minutes)

            return {
                'prediction': max(0, prediction_scaled),  # Load cannot be negative
                'confidence': (
                    max(0, prediction_scaled - confidence_width / 2),
                    prediction_scaled + confidence_width / 2
                ),
                'accuracy': accuracy
            }

        except Exception as e:
            logger.error("Error in forecast calculation",
                         entity=entity, horizon=horizon_minutes, error=str(e))
            return None

    def _ar_forecast(self, data: np.ndarray, horizon_minutes: int) -> float:
        """Simple autoregressive forecasting model"""
        if len(data) < self.ar_order:
            return np.mean(data)

        # Use last AR_ORDER points for prediction
        recent_data = data[-self.ar_order:]

        # Simple AR(p) model - in practice, use more sophisticated models
        # like ARIMA, LSTM, or seasonal decomposition

        # Seasonal component (daily pattern)
        seasonal_index = (len(data) % self.seasonal_period)
        target_seasonal_index = (seasonal_index + horizon_minutes // 15) % self.seasonal_period

        if len(data) > self.seasonal_period:
            seasonal_data = []
            for i in range(target_seasonal_index, len(data), self.seasonal_period):
                if i < len(data):
                    seasonal_data.append(data[i])
            seasonal_component = np.mean(seasonal_data) if seasonal_data else 0
        else:
            seasonal_component = 0

        # Trend component
        if len(recent_data) >= 5:
            trend = np.polyfit(range(len(recent_data)), recent_data, 1)[0]
        else:
            trend = 0

        # AR component (weighted average of recent values)
        weights = np.exp(np.arange(len(recent_data)) / 5)  # Exponential weighting
        weights = weights / np.sum(weights)
        ar_component = np.sum(recent_data * weights)

        # Combine components
        prediction = 0.6 * ar_component + 0.3 * seasonal_component + 0.1 * trend

        return prediction

    async def _calculate_forecast_accuracy(self, entity: str, horizon_minutes: int) -> Optional[float]:
        """Calculate historical forecast accuracy for this entity and horizon"""
        try:
            # Query recent forecast vs actual performance
            query = """
                    SELECT predicted_load, actual_load
                    FROM load_forecasts
                    WHERE entity = $1 \
                      AND horizon_minutes = $2
                      AND actual_load IS NOT NULL
                      AND time >= NOW() - INTERVAL '7 days'
                    ORDER BY time DESC
                        LIMIT 100 \
                    """

            results = await self.db.execute_query(query, entity, horizon_minutes)

            if len(results) < 5:
                return None

            # Calculate Mean Absolute Percentage Error (MAPE)
            mape_values = []
            for row in results:
                predicted = float(row['predicted_load'])
                actual = float(row['actual_load'])
                if actual > 0:  # Avoid division by zero
                    mape = abs((actual - predicted) / actual) * 100
                    mape_values.append(mape)

            if mape_values:
                avg_mape = np.mean(mape_values)
                accuracy = max(0, 100 - avg_mape)  # Convert MAPE to accuracy percentage
                return accuracy

            return None

        except Exception as e:
            logger.error("Error calculating forecast accuracy",
                         entity=entity, horizon=horizon_minutes, error=str(e))
            return None

    async def _store_forecast(self, forecast_event: LoadForecastEvent) -> None:
        """Store forecast in database"""
        try:
            query = """
                    INSERT INTO load_forecasts (time, forecast_time, entity, horizon_minutes,
                                                predicted_load, confidence_lower, confidence_upper,
                                                model_version)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8) \
                    """

            from datetime import datetime, timezone, timedelta

            forecast_time = datetime.fromtimestamp(forecast_event.timestamp, tz=timezone.utc)
            target_time = forecast_time + timedelta(minutes=forecast_event.horizon_minutes)

            confidence_lower, confidence_upper = forecast_event.confidence_interval or (None, None)

            async with self.db.acquire() as conn:
                await conn.execute(
                    query,
                    target_time,
                    forecast_time,
                    forecast_event.entity,
                    forecast_event.horizon_minutes,
                    forecast_event.predicted_load,
                    confidence_lower,
                    confidence_upper,
                    "ar_v1.0"
                )

        except Exception as e:
            logger.error("Error storing forecast",
                         entity=forecast_event.entity, error=str(e))

    async def stop(self) -> None:
        """Stop forecasting service"""
        self.running = False
        logger.info("Load forecasting service stopped")
