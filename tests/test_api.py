from fastapi.testclient import TestClient

from api.index import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_summary():
    r = client.get("/api/summary")
    assert r.status_code == 200
    body = r.json()
    for key in ("metrics", "capital", "backtest", "positions", "explanation", "stress", "distribution"):
        assert key in body
    assert body["capital"]["total"] > 0


def test_what_if_option():
    trade = {"type": "option", "factor": "BRENT", "option": "put", "quantity": 300000,
             "strike_pct": 0.95, "vol": 0.35, "expiry_years": 0.25}
    r = client.post("/api/what-if", json={"trades": [trade]})
    assert r.status_code == 200
    body = r.json()
    assert len(body["new_positions"]) == 1
    assert body["delta"]["capital"] == body["after"]["capital"]["total"] - body["before"]["capital"]["total"]
    assert body["explanation"] and isinstance(body["explanation"][0], str)


def test_what_if_rejects_bad_input():
    assert client.post("/api/what-if", json={"trades": []}).status_code == 422
    bad_factor = {"type": "linear", "factor": "BTC", "notional": 1e6}
    assert client.post("/api/what-if", json={"trades": [bad_factor]}).status_code == 422
    too_many = [{"type": "linear", "factor": "EUR", "notional": 1e6}] * 6
    assert client.post("/api/what-if", json={"trades": too_many}).status_code == 422
    zero = {"type": "linear", "factor": "EUR", "notional": 0}
    r = client.post("/api/what-if", json={"trades": [zero]})
    assert r.status_code == 422 and "non-zero" in r.json()["detail"]
