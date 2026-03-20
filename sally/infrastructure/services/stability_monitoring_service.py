import asyncio
import numpy as np
from typing import List, Dict, Any, Optional
import time
from sally.core.event_bus import EventHandler, Event, EventBus
from sally.infrastructure.data_management.timescale.timescaledb_connection import TimescaleDBConnection
from sally.domain.events import GridDataEvent, GridAlarmEvent, StabilityEvent
from sally.domain.grid_entities import GridMeasurement, EntityType
from sally.core.logger import get_logger

logger = get_logger(__name__)


class StabilityMonitoringService(EventHandler):
    """Real-time grid stability monitoring and fault detection service"""

    def __init__(self, db: TimescaleDBConnection, event_bus: EventBus):
        self.db = db
        self.event_bus = event_bus
        self.voltage_measurements = {}  # Entity -> recent voltage data
        self.frequency_measurements = []  # System frequency data
        self.angle_measurements = {}  # Entity -> voltage angle data
        self.running = False

        # Stability thresholds based on grid codes
        self.voltage_thresholds = {
            'nominal': 1.0,
            'warning_high': 1.05,
            'critical_high': 1.1,
            'warning_low': 0.95,
            'critical_low': 0.9
        }

        self.frequency_thresholds = {
            'nominal': 50.0,  # Hz
            'warning_high': 50.2,
            'critical_high': 50.5,
            'warning_low': 49.8,
            'critical_low': 49.5
        }

        self.angle_threshold = 30.0  # degrees - critical stability limit

        # Keep recent measurements for analysis
        self.max_history_points = 300  # 5 minutes at 1Hz

    @property
    def event_types(self) -> List[str]:
        return ["grid_data_update"]

    async def handle(self, event: Event) -> None:
        """Monitor grid measurements for stability issues"""
        if isinstance(event, GridDataEvent):
            measurement = event.measurement

            # Collect voltage measurements from nodes
            if (measurement.entity_type in [EntityType.PYPOWER_NODE, EntityType.PYPOWER_TR_PRI,
                                            EntityType.PYPOWER_TR_SEC] and
                    measurement.vm is not None):

                if measurement.entity not in self.voltage_measurements:
                    self.voltage_measurements[measurement.entity] = []

                self.voltage_measurements[measurement.entity].append({
                    'timestamp': measurement.timestamp,
                    'vm': measurement.vm,
                    'va': measurement.va
                })

                # Keep recent history
                cutoff_time = measurement.timestamp - 300  # 5 minutes
                self.voltage_measurements[measurement.entity] = [
                    point for point in self.voltage_measurements[measurement.entity]
                    if point['timestamp'] > cutoff_time
                ][-self.max_history_points:]

                # Check voltage stability
                await self._check_voltage_stability(measurement)

            # Monitor voltage angles for stability
            if measurement.va is not None:
                await self._check_angle_stability(measurement)

            # Estimate system frequency from PMU data
            if (measurement.entity_type == EntityType.PYPOWER_NODE and
                    measurement.va is not None):
                await self._estimate_frequency(measurement)

    async def _check_voltage_stability(self, measurement) -> None:
        """Check voltage levels against stability criteria"""
        vm = measurement.vm
        entity = measurement.entity

        # Determine severity based on voltage magnitude
        severity = None
        alarm_type = None

        if vm >= self.voltage_thresholds['critical_high']:
            severity = 'CRITICAL'
            alarm_type = 'voltage_high_critical'
        elif vm >= self.voltage_thresholds['warning_high']:
            severity = 'WARNING'
            alarm_type = 'voltage_high_warning'
        elif vm <= self.voltage_thresholds['critical_low']:
            severity = 'CRITICAL'
            alarm_type = 'voltage_low_critical'
        elif vm <= self.voltage_thresholds['warning_low']:
            severity = 'WARNING'
            alarm_type = 'voltage_low_warning'

        if severity:
            # Check if this is a persistent issue (not just a spike)
            if await self._is_persistent_voltage_issue(entity, vm, alarm_type):
                alarm_event = GridAlarmEvent(
                    timestamp=measurement.timestamp,
                    entity=entity,
                    entity_type=measurement.entity_type.value,
                    alarm_type=alarm_type,
                    severity=severity,
                    message=f"Voltage magnitude {vm:.3f} p.u. exceeds {'high' if 'high' in alarm_type else 'low'} threshold",
                    threshold_value=self.voltage_thresholds['warning_high' if 'high' in alarm_type else 'warning_low'],
                    measured_value=vm,
                    correlation_id=f"voltage_alarm_{entity}_{int(measurement.timestamp)}"
                )

                await self.event_bus.publish(alarm_event)
                await self._store_alarm(alarm_event)

    async def _is_persistent_voltage_issue(self, entity: str, current_vm: float,
                                           alarm_type: str) -> bool:
        """Check if voltage issue persists over multiple measurements"""
        if entity not in self.voltage_measurements:
            return True  # First measurement, treat as persistent

        recent_measurements = self.voltage_measurements[entity][-10:]  # Last 10 measurements

        if len(recent_measurements) < 5:
            return True

        # Check if majority of recent measurements exceed threshold
        threshold = (self.voltage_thresholds['warning_high'] if 'high' in alarm_type
                     else self.voltage_thresholds['warning_low'])

        exceeding_count = sum(1 for m in recent_measurements
                              if (m['vm'] > threshold if 'high' in alarm_type
                                  else m['vm'] < threshold))

        return exceeding_count >= len(recent_measurements) * 0.6  # 60% threshold

    async def _check_angle_stability(self, measurement) -> None:
        """Monitor voltage angle differences for transient stability"""
        if measurement.entity not in self.angle_measurements:
            self.angle_measurements[measurement.entity] = []

        self.angle_measurements[measurement.entity].append({
            'timestamp': measurement.timestamp,
            'va': measurement.va
        })

        # Keep recent history
        cutoff_time = measurement.timestamp - 60  # 1 minute
        self.angle_measurements[measurement.entity] = [
            point for point in self.angle_measurements[measurement.entity]
            if point['timestamp'] > cutoff_time
        ][-60:]  # Last 60 measurements

        # Check for large angle separations between buses
        await self._analyze_angle_separations(measurement.timestamp)

    async def _analyze_angle_separations(self, current_time: float) -> None:
        """Analyze voltage angle separations between buses"""
        # Get current angles from all buses
        current_angles = {}
        for entity, measurements in self.angle_measurements.items():
            if measurements:
                current_angles[entity] = measurements[-1]['va']  # Most recent angle

        if len(current_angles) < 2:
            return

        # Find maximum angle separation
        angles = list(current_angles.values())
        max_separation = np.max(angles) - np.min(angles)
        max_separation_deg = np.degrees(max_separation)

        # Check critical angle stability limit
        if max_separation_deg > self.angle_threshold:
            # Find the buses with maximum separation
            max_angle = max(angles)
            min_angle = min(angles)

            max_entity = next(entity for entity, angle in current_angles.items()
                              if angle == max_angle)
            min_entity = next(entity for entity, angle in current_angles.items()
                              if angle == min_angle)

            stability_event = StabilityEvent(
                timestamp=current_time,
                affected_entities=[max_entity, min_entity],
                stability_metric='phase_angle',
                deviation_magnitude=max_separation_deg,
                risk_level='CRITICAL',
                recommended_action='Increase transmission capacity or load shedding',
                correlation_id=f"angle_stability_{int(current_time)}"
            )

            await self.event_bus.publish(stability_event)

            # Also create alarm
            alarm_event = GridAlarmEvent(
                timestamp=current_time,
                entity=f"{max_entity}-{min_entity}",
                entity_type="transmission_path",
                alarm_type="transient_stability_limit",
                severity="CRITICAL",
                message=f"Critical angle separation {max_separation_deg:.1f}° between {max_entity} and {min_entity}",
                threshold_value=self.angle_threshold,
                measured_value=max_separation_deg
            )

            await self.event_bus.publish(alarm_event)
            await self._store_alarm(alarm_event)

    async def _estimate_frequency(self, measurement) -> None:
        """Estimate system frequency from voltage angle measurements"""
        # Simple frequency estimation from rate of change of voltage angle
        entity = measurement.entity

        if entity in self.angle_measurements and len(self.angle_measurements[entity]) >= 2:
            recent_angles = self.angle_measurements[entity][-2:]

            if len(recent_angles) == 2:
                dt = recent_angles[1]['timestamp'] - recent_angles[0]['timestamp']
                dangle = recent_angles[1]['va'] - recent_angles[0]['va']

                if dt > 0:
                    # Frequency = nominal + (dangle/dt) / (2*pi)
                    freq_deviation = (dangle / dt) / (2 * np.pi)
                    estimated_freq = 50.0 + freq_deviation

                    self.frequency_measurements.append({
                        'timestamp': measurement.timestamp,
                        'frequency': estimated_freq,
                        'entity': entity
                    })

                    # Keep recent frequency measurements
                    cutoff_time = measurement.timestamp - 300
                    self.frequency_measurements = [
                        point for point in self.frequency_measurements
                        if point['timestamp'] > cutoff_time
                    ]

                    # Check frequency stability
                    await self._check_frequency_stability(estimated_freq, measurement.timestamp)

    async def _check_frequency_stability(self, frequency: float, timestamp: float) -> None:
        """Check system frequency against stability limits"""
        severity = None
        alarm_type = None

        if frequency >= self.frequency_thresholds['critical_high']:
            severity = 'CRITICAL'
            alarm_type = 'frequency_high_critical'
        elif frequency >= self.frequency_thresholds['warning_high']:
            severity = 'WARNING'
            alarm_type = 'frequency_high_warning'
        elif frequency <= self.frequency_thresholds['critical_low']:
            severity = 'CRITICAL'
            alarm_type = 'frequency_low_critical'
        elif frequency <= self.frequency_thresholds['warning_low']:
            severity = 'WARNING'
            alarm_type = 'frequency_low_warning'

        if severity:
            stability_event = StabilityEvent(
                timestamp=timestamp,
                affected_entities=['SYSTEM'],
                stability_metric='frequency',
                deviation_magnitude=abs(frequency - 50.0),
                risk_level='CRITICAL' if severity == 'CRITICAL' else 'HIGH',
                recommended_action='Activate frequency response reserves' if frequency < 50.0 else 'Reduce generation',
                correlation_id=f"freq_stability_{int(timestamp)}"
            )

            await self.event_bus.publish(stability_event)

            alarm_event = GridAlarmEvent(
                timestamp=timestamp,
                entity='SYSTEM',
                entity_type='system',
                alarm_type=alarm_type,
                severity=severity,
                message=f"System frequency {frequency:.3f} Hz exceeds {'high' if 'high' in alarm_type else 'low'} threshold",
                threshold_value=50.0,
                measured_value=frequency
            )

            await self.event_bus.publish(alarm_event)
            await self._store_alarm(alarm_event)

    async def _store_alarm(self, alarm_event: GridAlarmEvent) -> None:
        """Store alarm in database"""
        try:
            event_data = {
                'time': alarm_event.timestamp,
                'entity': alarm_event.entity,
                'entity_type': alarm_event.entity_type,
                'event_type': alarm_event.alarm_type,
                'severity': alarm_event.severity,
                'message': alarm_event.message,
                'metadata': {
                    'threshold_value': alarm_event.threshold_value,
                    'measured_value': alarm_event.measured_value
                }
            }

            await self.db.insert_grid_event(event_data)

        except Exception as e:
            logger.error("Error storing alarm",
                         alarm_type=alarm_event.alarm_type, error=str(e))

    async def start_monitoring(self) -> None:
        """Start continuous stability monitoring"""
        self.running = True
        logger.info("Grid stability monitoring started")

        while self.running:
            try:
                # Periodic comprehensive stability assessment
                await self._comprehensive_stability_check()
                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error("Error in stability monitoring", error=str(e))
                await asyncio.sleep(10)

    async def _comprehensive_stability_check(self) -> None:
        """Perform comprehensive grid stability assessment"""
        current_time = time.time()

        # Voltage stability assessment
        voltage_violations = 0
        total_buses = 0

        for entity, measurements in self.voltage_measurements.items():
            if measurements:
                total_buses += 1
                latest_vm = measurements[-1]['vm']

                if (latest_vm < self.voltage_thresholds['warning_low'] or
                        latest_vm > self.voltage_thresholds['warning_high']):
                    voltage_violations += 1

        # Overall system stability assessment
        if total_buses > 0:
            voltage_violation_rate = voltage_violations / total_buses

            if voltage_violation_rate > 0.2:  # More than 20% of buses have voltage issues
                stability_event = StabilityEvent(
                    timestamp=current_time,
                    affected_entities=list(self.voltage_measurements.keys())[:10],  # First 10 for brevity
                    stability_metric='voltage',
                    deviation_magnitude=voltage_violation_rate * 100,
                    risk_level='HIGH' if voltage_violation_rate > 0.5 else 'MEDIUM',
                    recommended_action='Check transformer tap positions and reactive power dispatch',
                    correlation_id=f"system_stability_{int(current_time)}"
                )

                await self.event_bus.publish(stability_event)

        logger.debug("Stability check completed",
                     voltage_violations=voltage_violations,
                     total_buses=total_buses,
                     recent_frequency_measurements=len(self.frequency_measurements))

    async def stop(self) -> None:
        """Stop stability monitoring"""
        self.running = False
        logger.info("Grid stability monitoring stopped")
