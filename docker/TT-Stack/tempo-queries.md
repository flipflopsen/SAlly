# Tempo TraceQL Query Examples

This document contains TraceQL query examples for exploring traces in the Sally system using Grafana Tempo.

## Basic Queries

### Find All Traces by Service

```traceql
{ resource.service.name = "SAlly.Orchestrator" }
```

```traceql
{ resource.service.name = "SAlly.EventBus" }
```

```traceql
{ resource.service.name = "SAlly.Rules" }
```

```traceql
{ resource.service.name = "SAlly.Setpoints" }
```

```traceql
{ resource.service.name = "SAlly.GridData" }
```

### Find Traces by Span Name

```traceql
{ name = "eventbus.publish" }
```

```traceql
{ name = "scada.run_step" }
```

```traceql
{ name = "rules.evaluate" }
```

```traceql
{ name = "setpoint.apply" }
```

## Event Bus Traces

### Find Published Events by Type

```traceql
{ span.event_type = "GridMeasurementEvent" }
```

```traceql
{ span.event_type = "RuleTriggeredEvent" }
```

```traceql
{ span.event_type = "SetpointAppliedEvent" }
```

### Find Dropped Events

```traceql
{ span.dropped = true }
```

### Find Slow Event Processing (> 10ms)

```traceql
{ name = "eventbus.worker.batch" && duration > 10ms }
```

### Find Large Batches

```traceql
{ span.batch_size > 100 }
```

## SCADA & Simulation Traces

### Find Simulation Steps by Timestep

```traceql
{ name = "scada.run_step" && span.timestep > 1000 }
```

### Find Failed Simulation Steps

```traceql
{ name = "scada.run_step" && span.success = false }
```

### Find Slow Simulation Steps (> 100ms)

```traceql
{ name = "scada.run_step" && duration > 100ms }
```

### Find Command Processing by Type

```traceql
{ name = "scada.process_command" && span.command_type = "SetSetpoint" }
```

```traceql
{ name = "scada.process_command" && span.command_type = "EmergencyStop" }
```

## Rule Evaluation Traces

### Find Rule Evaluations

```traceql
{ name = "rules.evaluate" }
```

### Find Triggered Rules

```traceql
{ span.rule_triggered = true }
```

### Find Specific Rule Evaluations

```traceql
{ span.rule_id = "voltage_high_rule" }
```

### Find Slow Rule Evaluations (> 5ms)

```traceql
{ name = "rules.evaluate" && duration > 5ms }
```

### Find Chain Evaluations with Multiple Rules

```traceql
{ name = "rules.evaluate_chain" && span.chain_length > 3 }
```

## Setpoint Traces

### Find Setpoint Applications

```traceql
{ name = "setpoint.apply" }
```

### Find Setpoints for Specific Entity

```traceql
{ span.entity_id = "transformer_1" }
```

### Find Setpoints by Attribute

```traceql
{ span.attribute = "voltage_setpoint" }
```

### Find Failed Setpoint Applications

```traceql
{ name = "setpoint.apply" && status = error }
```

## Grid Data Collection Traces

### Find Data Collection Spans

```traceql
{ name = "grid_data.collect" }
```

### Find Batch Flush Operations

```traceql
{ name = "grid_data.flush_batch" }
```

### Find Collection by Entity Type

```traceql
{ span.entity_type = "Transformer" }
```

```traceql
{ span.entity_type = "Bus" }
```

## Cross-Service Traces

### Find Complete Flow: Event → Rule → Setpoint

Use this to trace the complete flow from an event through rule evaluation to setpoint application:

```traceql
{ resource.service.name =~ "SAlly.*" && duration > 50ms }
```

### Find All Traces with Errors

```traceql
{ status = error }
```

### Find Traces with Specific Correlation ID

```traceql
{ span.correlation_id = "your-correlation-id-here" }
```

## Performance Analysis

### Find Slowest Operations (> 100ms)

```traceql
{ duration > 100ms }
```

### Find P99 Latency Candidates

```traceql
{ duration > 50ms } | rate()
```

### Compare Service Latencies

```traceql
{ resource.service.name =~ "SAlly.*" } | quantile_over_time(duration, 0.99)
```

## Aggregation Queries

### Count Events by Type

```traceql
{ name = "eventbus.publish" } | count() by (span.event_type)
```

### Average Duration by Service

```traceql
{ resource.service.name =~ "SAlly.*" } | avg(duration) by (resource.service.name)
```

### Error Rate by Service

```traceql
{ resource.service.name =~ "SAlly.*" && status = error } | rate() by (resource.service.name)
```

## Grafana Explore Tips

1. **Service Graph**: Use the Service Graph view to visualize dependencies between Sally services.

2. **Trace to Metrics**: Click on any trace to see correlated metrics in Prometheus.

3. **Trace to Logs**: Enable trace-to-logs correlation to jump from traces to Loki logs.

4. **Span Attributes**: Expand spans to see all custom attributes like `entity_id`, `rule_id`, `event_type`, etc.

5. **Compare Traces**: Select multiple traces to compare their structures and timings.

## Common Debugging Scenarios

### Debug Slow Simulation Step

1. Find the slow step:
   ```traceql
   { name = "scada.run_step" && duration > 200ms }
   ```

2. Look at child spans to identify bottleneck (rules, setpoints, data collection)

### Debug Missing Events

1. Check if events are being published:
   ```traceql
   { name = "eventbus.publish" && span.event_type = "YourEventType" }
   ```

2. Check if events are being dropped:
   ```traceql
   { span.dropped = true && span.event_type = "YourEventType" }
   ```

### Debug Rule Not Triggering

1. Find rule evaluation:
   ```traceql
   { name = "rules.evaluate" && span.rule_id = "your_rule_id" }
   ```

2. Check evaluation result in span attributes

### Debug Setpoint Not Applied

1. Find setpoint application:
   ```traceql
   { name = "setpoint.apply" && span.entity_id = "your_entity" }
   ```

2. Check for errors in span status
