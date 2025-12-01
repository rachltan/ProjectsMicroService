import requests
from flask import current_app

def _base():
    return current_app.config["PROJECTS_SERVICE_BASE"].rstrip("/")

def _timeout():
    return current_app.config.get("PROJECTS_SERVICE_TIMEOUT", 5)

def list_projects():
    resp = requests.get(f"{_base()}/projects", timeout=_timeout())
    resp.raise_for_status()
    return resp.json().get("projects", [])

def create_project(payload: dict):
    resp = requests.post(f"{_base()}/projects", json=payload, timeout=_timeout())
    resp.raise_for_status()
    return resp.json().get("project")
