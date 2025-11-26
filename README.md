# Kafka OTEL Consumer

This repository now focuses exclusively on the Python-based Kafka consumer that pushes metrics to an OpenTelemetry (OTEL) Collector using OTLP/GRPC. Use the steps below to install dependencies, run the consumer, and understand how incoming Kafka messages become OTEL metrics.

## Prerequisites
- Python 3.10+ with `pip`
- Access to a Kafka broker (adjust host/port as needed)
- An OTEL Collector listening for OTLP/GRPC metrics on `localhost:4317` (or configure `consumer.py` accordingly)
- OpenSearch Data Prepper (for processing and routing metrics to OpenSearch)
- OpenSearch instance (for storing metrics data)

## Project Layout
- `consumer.py`: Main script that consumes Kafka messages and exports metrics via the OTEL SDK
- `otel-config.yaml`: OTEL Collector configuration that routes metrics to Data Prepper
- `pipelines/opensearch-metrics.yaml`: Data Prepper pipeline configuration for processing and storing metrics in OpenSearch
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

<img width="3348" height="1948" alt="image" src="https://github.com/user-attachments/assets/e44a0a0c-34bc-4999-b70d-78843c3c1925" />

## OpenSearch Data Prepper Setup

This section explains how to configure and run OpenSearch Data Prepper to receive metrics from the OTEL Collector and store them in OpenSearch.

### 1. Install OpenSearch Data Prepper

Download and install OpenSearch Data Prepper:

```bash
# Download Data Prepper (adjust version as needed)
wget https://github.com/opensearch-project/data-prepper/releases/download/2.x.x/data-prepper-2.x.x-linux-x64.tar.gz
tar -xzf data-prepper-2.x.x-linux-x64.tar.gz
cd data-prepper-2.x.x
```

Or use Docker:

```bash
docker pull opensearchproject/data-prepper:latest
```

### 2. Configure Data Prepper Pipeline

The pipeline configuration file is located at `pipelines/opensearch-metrics.yaml`. This file defines:

- **Source**: OTLP metrics receiver on port `21890` (must match the OTEL Collector exporter endpoint)
- **Processors**: OTEL metrics processor to convert metrics to OpenSearch format
- **Sink**: OpenSearch sink that writes to the `otel-metrics` index

Key configuration points in `pipelines/opensearch-metrics.yaml`:
- `port: 21890` - Must match the endpoint in `otel-config.yaml` (`9.40.206.98:21890`)
- `hosts: ["https://localhost:9200"]` - Update to your OpenSearch cluster endpoint
- `index: "otel-metrics"` - Target index name in OpenSearch
- `insecure: true` - Set to `false` in production with proper TLS certificates

### 3. Start OpenSearch

Start your OpenSearch instance. If running locally:

```bash
# Using Docker
docker run -d -p 9200:9200 -p 9600:9600 \
  -e "discovery.type=single-node" \
  -e "OPENSEARCH_INITIAL_ADMIN_PASSWORD=Admin@123" \
  opensearchproject/opensearch:latest

# Or download and run OpenSearch directly
# https://opensearch.org/docs/latest/install-and-configure/install-opensearch/index/
```

### 4. Start Data Prepper

Run Data Prepper with the pipeline configuration. The pipeline YAML file should be placed inside the `pipelines` folder:

**Using the binary:**
```bash
./bin/data-prepper pipelines/opensearch-metrics.yaml
```

**Using Docker:**
```bash
docker run -d \
  -p 21890:21890 \
  -v $(pwd)/pipelines:/usr/share/data-prepper/pipelines \
  opensearchproject/data-prepper:latest \
  pipelines/opensearch-metrics.yaml
```

## Troubleshooting
- Ensure the OTEL Collector is running and reachable at the configured endpoint; otherwise the exporter will log connection errors.
- Verify your Kafka topic contains JSON payloads; non-JSON messages will raise deserialization errors.
- Adjust logging or add additional transformations within `process_generic_json` to map complex payloads to metrics.

## Next Steps
- Add automated tests to validate the transformations in `process_generic_json`.
- Extend the script to emit traces or logs in addition to metrics.
- Containerize the consumer for easier deployment alongside Kafka.

