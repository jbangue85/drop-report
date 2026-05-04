from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Bypass auth for testing
app.dependency_overrides = {}
from app.auth import get_current_user
app.dependency_overrides[get_current_user] = lambda: {"username": "admin"}

with open("Mercatelia-Campañas-1-a-r-2026---4-may-2026 (1).csv", "rb") as f:
    response = client.post("/api/upload", files={"file": ("Mercatelia-Campañas-1-a-r-2026---4-may-2026 (1).csv", f, "text/csv")})
    
print(response.status_code)
print(response.json())
