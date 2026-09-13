import requests

url = "http://localhost:8001/api/v1/auth/login"
res = requests.post(url, json={"email": "admin@newspulse.com", "password": "admin"})
token = res.json().get("access_token")
print("Token:", token)

headers = {"Authorization": f"Bearer {token}"}
print("Latency:", requests.get("http://localhost:8001/api/v1/admin/metrics/latency", headers=headers).json())
print("Clickbait:", requests.get("http://localhost:8001/api/v1/admin/metrics/clickbait", headers=headers).json())
print("Users:", requests.get("http://localhost:8001/api/v1/admin/metrics/users", headers=headers).json())
