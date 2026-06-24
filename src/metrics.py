from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

# Counters
request_counter = Counter('mcp_requests_total', 'Total MCP requests', ['method', 'path', 'status'])
auth_failures = Counter('mcp_auth_failures_total', 'Auth failures')
rate_limit_hits = Counter('mcp_rate_limit_hits_total', 'Rate limit hits')
proxy_errors = Counter('mcp_proxy_errors_total', 'Proxy errors')

# Histograms / gauges (optional)
request_latency = Histogram('mcp_request_latency_seconds', 'Request latency (seconds)')


def metrics_response():
    """Return a FastAPI Response containing Prometheus metrics."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
