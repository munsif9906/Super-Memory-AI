"""End-to-end test: full Kumar story through the real API (fake models)."""
import time
from fastapi.testclient import TestClient
from app.api import app
from app import jobs
from app.models import SessionLocal, MemoryRow
from sqlalchemy import select
from datetime import datetime, timedelta, timezone

from app.config import settings
settings.search_threshold = 0.1  # fake embedder scores lower than real models
settings.link_threshold = 0.3
H = {"x-api-key": "dev-key-change-me"}
c = TestClient(app)

assert c.get("/health").json()["status"] == "ok"
assert c.get("/search?container_tag=k&q=x").status_code == 401, "auth must block"

# Day 1 - note the phone number: redaction must catch it
r = c.post("/memories", headers=H, json={
    "container_tag": "patient_kumar_001",
    "text": "I'm Kumar, phone 0771234567. My doctor put me on metformin 500mg. "
            "I'm traveling to Kandy next week so I might miss my check-in."})
assert r.status_code == 202
time.sleep(0.3)

# idempotency: same message again must store 0 new facts
before = len(list(SessionLocal().execute(select(MemoryRow)).scalars()))
c.post("/memories", headers=H, json={
    "container_tag": "patient_kumar_001",
    "text": "I'm Kumar, phone 0771234567. My doctor put me on metformin 500mg. "
            "I'm traveling to Kandy next week so I might miss my check-in."})
time.sleep(0.3)
after = len(list(SessionLocal().execute(select(MemoryRow)).scalars()))
assert before == after, "idempotency failed"
print(f"PASS idempotency ({before} rows, no duplicates)")

# Day 14 - contradiction
c.post("/memories", headers=H, json={
    "container_tag": "patient_kumar_001",
    "text": "My doctor increased my metformin to 1000mg."})
time.sleep(0.3)

# tenant isolation: another patient must see nothing
r = c.get("/search", headers=H, params={
    "container_tag": "patient_other", "q": "metformin dose"})
assert r.json()["facts"] == [], "tenant isolation failed"
print("PASS tenant isolation")

# redaction check
with SessionLocal() as s:
    rows = s.execute(select(MemoryRow)).scalars().all()
    assert not any("0771234567" in r.fact for r in rows), "PHI leaked!"
    print("PASS redaction (phone number never stored)")
    # force-expire the Kandy fact for the demo
    for r in rows:
        if r.expires_at:
            r.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    s.commit()

# nightly job
print("forget job:", jobs.forget_and_decay())
print("profiles rebuilt:", jobs.rebuild_profiles())

# recall: must return 1000mg, never 500mg
r = c.get("/search", headers=H, params={
    "container_tag": "patient_kumar_001", "q": "current metformin dose"})
facts = r.json()["facts"]
print("recall ->", facts)
assert any("1000" in f for f in facts), "should return new dose"
assert not any("500" in f for f in facts), "old dose must be hidden"
print("PASS contradiction handling")

# profile + ask
print("profile ->", c.get("/profile", headers=H,
      params={"container_tag": "patient_kumar_001"}).json())
print("ask ->", c.post("/ask", headers=H, json={
    "container_tag": "patient_kumar_001",
    "question": "Can I take ibuprofen with my medication?"}).json())
print("\nALL TESTS PASSED")
