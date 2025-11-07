import json
import time
from kafka import KafkaConsumer
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.metrics import Observation

# Setup OTEL exporter
resource = Resource(attributes={
    "service.name": "kafka-consumer",
    "service.version": "1.0.0"
})

exporter = OTLPMetricExporter(
    endpoint="http://localhost:4317",
    insecure=True,
    timeout=30  # Increase timeout to 30 seconds
)

reader = PeriodicExportingMetricReader(
    exporter, 
    export_interval_millis=2000  # Export every 2 seconds
)
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = provider.get_meter("kafka-consumer")

# Store latest metric values (updated by Kafka messages)
metrics_state = {}

# Register metric instruments ONCE at startup
registered_gauges = {}

def register_metric(metric_name, description="Auto-generated metric"):
    """Register a metric instrument once"""
    if metric_name not in registered_gauges:
        gauge = meter.create_observable_gauge(
            name=metric_name,
            callbacks=[lambda options: get_observations(metric_name)],
            description=description,
            unit="1"
        )
        registered_gauges[metric_name] = gauge
        print(f"Registered metric: {metric_name}")

def get_observations(metric_name):
    """Callback to provide current metric value"""
    value = metrics_state.get(metric_name, 0)
    return [Observation(value, {"source": "kafka"})]

# Create Kafka consumer
consumer = KafkaConsumer(
    'test-topic',
    bootstrap_servers=['10.48.17.159:9092'],
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='my-group',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

print("Kafka consumer started, waiting for messages...")

def is_otel_format(data):
    """Check if message is already in OTEL format"""
    return 'resource_metrics' in data or 'scope_metrics' in data

def process_otel_message(data):
    """Handle OTEL formatted messages"""
    print("Detected OTEL format - extracting metrics")
    
    if 'resource_metrics' in data:
        for rm in data['resource_metrics']:
            if 'scope_metrics' in rm:
                for sm in rm['scope_metrics']:
                    if 'metrics' in sm:
                        for metric in sm['metrics']:
                            metric_name = metric.get('name', 'unknown')
                            
                            # Register metric if not already registered
                            register_metric(
                                metric_name,
                                metric.get('description', '')
                            )
                            
                            # Extract value from gauge
                            if 'gauge' in metric and 'data_points' in metric['gauge']:
                                for dp in metric['gauge']['data_points']:
                                    value = dp.get('as_double') or dp.get('as_int') or 0
                                    
                                    # Update state (will be read by callback)
                                    metrics_state[metric_name] = value
                                    print(f"  Updated: {metric_name} = {value}")

def process_generic_json(data):
    """Transform generic JSON to OTEL metrics"""
    print("Detected generic JSON - transforming to metrics")
    
    for key, value in data.items():
        if isinstance(value, (int, float)):
            metric_name = f"kafka.{key.replace(' ', '_').lower()}"
            
            # Register metric if not already registered
            register_metric(metric_name, f"Value from Kafka field: {key}")
            
            # Update state
            metrics_state[metric_name] = float(value)
            print(f"  Updated: {metric_name} = {value}")
            
        elif isinstance(value, str):
            try:
                num_value = float(value)
                metric_name = f"kafka.{key.replace(' ', '_').lower()}"
                register_metric(metric_name, f"Value from Kafka field: {key}")
                metrics_state[metric_name] = num_value
                print(f"  Updated: {metric_name} = {num_value} (parsed from string)")
            except ValueError:
                print(f"  Attribute: {key} = {value}")
        else:
            print(f"  Skipping {key} (complex type)")

# Main consumption loop
try:
    for msg in consumer:
        print(f"\n--- Received message (offset: {msg.offset}) ---")
        
        try:
            data = msg.value
            
            if is_otel_format(data):
                process_otel_message(data)
            else:
                process_generic_json(data)
                
        except Exception as e:
            print(f"Error processing message: {e}")
            import traceback
            traceback.print_exc()
            
except KeyboardInterrupt:
    print("\nShutting down consumer...")
finally:
    consumer.close()
    provider.shutdown()
    print("Consumer stopped")
