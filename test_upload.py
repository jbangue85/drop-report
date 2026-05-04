import requests

r1 = requests.post("http://localhost:8080/api/auth/login", json={"username": "admin", "password": "admin123"})
if "token" not in r1.json():
    print("Login failed:", r1.json())
else:
    token = r1.json()["token"]
    with open("Mercatelia-Campañas-1-a-r-2026---4-may-2026 (1).csv", "rb") as f:
        files = {"file": f}
        r2 = requests.post("http://localhost:8080/api/upload", headers={"Authorization": f"Bearer {token}"}, files=files)
        print("Upload result:", r2.status_code, r2.json())
