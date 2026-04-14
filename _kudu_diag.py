import json
import subprocess
from urllib.parse import urljoin

import requests

SUB = "513f4932-c0e8-4757-9669-8259a90cab92"
RG = "rg-mslearn-dbricks-2026"
APP = "dbx-genie"


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return p.stdout


def main():
    profiles_raw = run([
        "az",
        "webapp",
        "deployment",
        "list-publishing-profiles",
        "--name",
        APP,
        "--resource-group",
        RG,
        "--subscription",
        SUB,
        "--output",
        "json",
    ])
    profiles = json.loads(profiles_raw)
    msdeploy = next((p for p in profiles if p.get("publishMethod") == "MSDeploy"), None)
    if not msdeploy:
        raise RuntimeError("No MSDeploy profile found")

    user = msdeploy["userName"]
    pwd = msdeploy["userPWD"]
    publish_url = msdeploy["publishUrl"].split(":")[0]
    base = f"https://{publish_url}/"

    s = requests.Session()
    s.auth = (user, pwd)
    s.timeout = 30

    def list_dir(path):
        url = urljoin(base, f"api/vfs/{path}")
        r = s.get(url)
        print(f"{path} -> {r.status_code}")
        if r.status_code != 200:
            print(r.text[:200])
            return
        data = r.json()
        names = [x.get("name", "") for x in data][:25]
        for n in names:
            print(f"  - {n}")

    list_dir("site/wwwroot/")
    list_dir("LogFiles/")
    list_dir("LogFiles/Application/")
    list_dir("LogFiles/kudu/trace/")


if __name__ == "__main__":
    main()
