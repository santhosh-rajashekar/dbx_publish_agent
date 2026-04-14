import json
import subprocess
import time

AZ_CMD = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
APP = "dbx-genie"
RG = "rg-mslearn-dbricks-2026"


def get_latest() -> dict:
    proc = subprocess.run(
        [AZ_CMD, "webapp", "log", "deployment", "list", "--name", APP, "--resource-group", RG, "--output", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    arr = json.loads(proc.stdout)
    return arr[0] if arr else {}


def main() -> int:
    for i in range(1, 31):
        latest = get_latest()
        dep_id = latest.get("id")
        status = latest.get("status")
        complete = latest.get("complete")
        progress = latest.get("progress")
        print(f"poll {i}: id={dep_id} status={status} complete={complete} progress={progress}")

        if status == 4 and complete:
            print("DEPLOYMENT_SUCCEEDED")
            return 0
        if status == 3:
            print("DEPLOYMENT_FAILED")
            return 1

        time.sleep(10)

    print("DEPLOYMENT_TIMEOUT")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())