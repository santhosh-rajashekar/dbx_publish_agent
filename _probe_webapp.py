import requests

URLS = [
    "https://dbx-genie-e8ekeqh7eae9htet.francecentral-01.azurewebsites.net/",
    "https://dbx-genie-e8ekeqh7eae9htet.francecentral-01.azurewebsites.net/api/messages",
]

for u in URLS:
    try:
        r = requests.get(u, timeout=20)
        print(u, r.status_code, r.text[:160])
    except Exception as exc:
        print(u, type(exc).__name__)
