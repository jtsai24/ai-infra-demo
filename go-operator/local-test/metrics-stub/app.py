from flask import Flask, request, jsonify

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

@app.route("/set", methods=["POST"])
def set_metrics():
    """
    Update the fake metric values at runtime.

    Accepts either a JSON body or query params, using short keys:
      curl -X POST localhost:8080/set -H "Content-Type: application/json" \
           -d '{"kv": 0.85, "requests": 5}'
      curl -X POST "localhost:8080/set?kv=0.85&requests=5"
    """
    data = request.get_json(silent=True) or request.args

    if "kv" in data:
        state["kv_cache_usage_perc"] = float(data["kv"])
    if "requests" in data:
        state["num_requests_waiting"] = int(data["requests"])

    return jsonify(state), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)