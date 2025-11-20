# Kafka OTEL Consumer

This repository now focuses exclusively on the Python-based Kafka consumer that pushes metrics to an OpenTelemetry (OTEL) Collector using OTLP/GRPC. Use the steps below to install dependencies, run the consumer, and understand how incoming Kafka messages become OTEL metrics.

## Prerequisites
- Python 3.10+ with `pip`
- Access to a Kafka broker (adjust host/port as needed)
- An OTEL Collector listening for OTLP/GRPC metrics on `localhost:4317` (or configure `consumer.py` accordingly)

## Project Layout
- `consumer.py`: Main script that consumes Kafka messages and exports metrics via the OTEL SDK
- `README.md`: You are here

## Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install kafka-python opentelemetry-sdk opentelemetry-exporter-otlp opentelemetry-sdk-metrics
```

## Configure and Run the Consumer

Update the Kafka connection details near the bottom of `consumer.py` if your broker differs from the default `10.48.17.159:9092` or if you want to subscribe to another topic.

Start the consumer:

```bash
python consumer.py
```

When running, the script logs whenever it registers a new metric or updates metric values so you can track what is being exported.

## How `consumer.py` Works
- **Metric provider setup**: Configures a `MeterProvider` with an OTLP exporter sending to `http://localhost:4317` every two seconds.
- **Dynamic gauges**: Maintains a registry of observable gauges, registering each new metric name once and reusing it for subsequent updates.
- **Kafka ingestion**: Uses `kafka-python` to read JSON messages from the configured topic.
- **Format detection**: If a message already matches the OTEL metric proto schema (`resource_metrics` / `scope_metrics`), it surfaces the contained gauge data points directly; otherwise, it treats numeric fields in the JSON payload as metrics named `kafka.<field>`.
- **Metric export loop**: The observable gauge callbacks read the latest values from in-memory state; the OTEL SDK handles exporting them on the configured interval.

## Prometheus Setup (for local visualization)
- **Add a Prometheus exporter in your OTEL Collector config (otel-config.yaml)**:
```bash
exporters:
  prometheus:
    endpoint: "0.0.0.0:8888"
```
- **Configure Prometheus to scrape the OTEL Collector metrics endpoint by adding to your prometheus.yml**:
```bash
scrape_configs:
  - job_name: "otel-collector"
    static_configs:
      - targets: ["localhost:8888"]
```

<img width="1396" height="981" alt="Screenshot 2025-11-20 at 1 55 37 PM" src="https://github.com/user-attachments/assets/572c32ca-4b7f-4217-af4f-5fe188872c16" />

## Troubleshooting
- Ensure the OTEL Collector is running and reachable at the configured endpoint; otherwise the exporter will log connection errors.
- Verify your Kafka topic contains JSON payloads; non-JSON messages will raise deserialization errors.
- Adjust logging or add additional transformations within `process_generic_json` to map complex payloads to metrics.

## Next Steps
- Add automated tests to validate the transformations in `process_generic_json`.
- Extend the script to emit traces or logs in addition to metrics.
- Containerize the consumer for easier deployment alongside Kafka.

