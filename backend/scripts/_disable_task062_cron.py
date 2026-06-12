#!/usr/bin/env python3
"""Disable TASK-062 cron job."""
import json
path = "/Volumes/NAUBER/HomeOffload/hermes/cron/jobs.json"
with open(path) as f:
    data = json.load(f)
for job in data["jobs"]:
    if job["id"] == "56645f1426f6":
        job["enabled"] = False
        job["state"] = "completed"
        job["repeat"]["completed"] = 1
        print(f"Disabled: {job.get('name','unknown')}")
        break
else:
    print("Job not found")
with open(path, "w") as f:
    json.dump(data, f, indent=2)
