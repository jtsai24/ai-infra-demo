from flask import Flask

app = Flask(__name__)

# In-memory state — this is the "fake but live" part.
# Hardcoded for now; we'll make it changeable via /set in the next step.
state = {
    "kv_cache_usage_perc": 0.45,
    "num_requests_waiting": 0,
}


@app.route("/metrics", methods=["GET"])
def metrics():
    body = (
        f"vllm_kv_cache_usage_perc {state['kv_cache_usage_perc']}\n"
        f"vllm_num_requests_waiting {state['num_requests_waiting']}\n"
    )
    return body, 200, {"Content-Type": "text/plain; version=0.0.4"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)