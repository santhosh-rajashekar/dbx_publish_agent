import json
import subprocess
import time
from pathlib import Path

import requests

SUB = "513f4932-c0e8-4757-9669-8259a90cab92"
RG = "rg-mslearn-dbricks-2026"
APP = "dbx-genie"
ZIP_PATH = Path(r"c:\Users\srajashekar\git\dbx_publish_agent\azure_bot_app.zip")
AZ_CMD = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return p.stdout


def main():
    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"Zip not found: {ZIP_PATH}")

    profiles_raw = run([
        AZ_CMD,
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
    profile = next((p for p in profiles if p.get("publishMethod") == "ZipDeploy"), None)
    if not profile:
        profile = next((p for p in profiles if p.get("publishMethod") == "MSDeploy"), None)
    if not profile:
        raise RuntimeError("No publishing profile found")

    user = profile["userName"]
    pwd = profile["userPWD"]
    host = profile["publishUrl"].split(":")[0]

    deploy_url = f"https://{host}/api/zipdeploy?isAsync=true"
    with ZIP_PATH.open("rb") as f:
        resp = requests.post(deploy_url, auth=(user, pwd), data=f, timeout=120)
    print("zipdeploy_status", resp.status_code)
    if resp.status_code not in (200, 202):
        print(resp.text[:500])
        return

    poll_url = resp.headers.get("Location") or resp.headers.get("location")
    if not poll_url:
        print("no_poll_url")
        return

    for i in range(1, 61):
        p = requests.get(poll_url, auth=(user, pwd), timeout=30)
        if p.status_code != 200:
            print("poll_http", p.status_code)
            time.sleep(3)
            continue
        body = p.json()
        status = body.get("status")
        complete = body.get("complete")
        print("poll", i, "status", status, "complete", complete)
        if complete:
            print("final_status", status)
            print("message", (body.get("status_text") or body.get("progress") or "")[:300])
            return
        time.sleep(3)

    print("deployment_timeout")


if __name__ == "__main__":
    main()
