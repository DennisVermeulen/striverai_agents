import json
import sys
import time

import httpx
import typer

app = typer.Typer(name="local-agent", help="CLI for the Local Agent browser automation tool.")

BASE_URL = "http://localhost:8000"


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=30)


@app.command()
def task(
    instruction: str = typer.Argument(..., help="What the agent should do"),
    url: str | None = typer.Option(None, "--url", "-u", help="Navigate to URL first"),
    max_steps: int | None = typer.Option(None, "--max-steps", "-n", help="Max agent steps"),
    follow: bool = typer.Option(True, "--follow/--no-follow", help="Follow progress"),
):
    """Submit a task for the agent to execute."""
    with _client() as client:
        body = {"instruction": instruction}
        if url:
            body["url"] = url
        if max_steps:
            body["max_steps"] = max_steps

        resp = client.post("/task", json=body)
        if resp.status_code == 409:
            typer.echo("Error: A task is already running.", err=True)
            raise typer.Exit(1)
        resp.raise_for_status()

        data = resp.json()
        task_id = data["task_id"]
        typer.echo(f"Task {task_id} created: {data['instruction']}")

        if follow:
            _follow_task(client, task_id)


@app.command()
def status(task_id: str = typer.Argument(..., help="Task ID to check")):
    """Check the status of a task."""
    with _client() as client:
        resp = client.get(f"/task/{task_id}")
        resp.raise_for_status()
        data = resp.json()
        _print_status(data)


@app.command()
def cancel(task_id: str = typer.Argument(..., help="Task ID to cancel")):
    """Cancel a running task."""
    with _client() as client:
        resp = client.post(f"/task/{task_id}/cancel")
        resp.raise_for_status()
        typer.echo(f"Task {task_id} cancelled.")


@app.command()
def screenshot(output: str = typer.Option("screenshot.png", "--output", "-o", help="Output file")):
    """Save a screenshot of the current browser state."""
    with _client() as client:
        resp = client.get("/screenshot")
        resp.raise_for_status()
        with open(output, "wb") as f:
            f.write(resp.content)
        typer.echo(f"Screenshot saved to {output}")


@app.command()
def navigate(url: str = typer.Argument(..., help="URL to navigate to")):
    """Navigate the browser to a URL."""
    with _client() as client:
        resp = client.post("/navigate", json={"url": url})
        resp.raise_for_status()
        typer.echo(f"Navigated to {url}")


@app.command(name="save-session")
def save_session():
    """Save the current browser session (cookies/localStorage)."""
    with _client() as client:
        resp = client.post("/session/save")
        resp.raise_for_status()
        typer.echo(f"Session saved: {resp.json()['path']}")


def _follow_task(client: httpx.Client, task_id: str) -> None:
    """Poll task status until completion."""
    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    idx = 0

    while True:
        resp = client.get(f"/task/{task_id}")
        resp.raise_for_status()
        data = resp.json()

        s = data["status"]
        action = data.get("current_action", "")
        steps = data.get("steps_completed", 0)

        sys.stdout.write(f"\r{spinner[idx % len(spinner)]} [{s}] Step {steps}")
        if action:
            sys.stdout.write(f" — {action}")
        sys.stdout.write("    ")
        sys.stdout.flush()
        idx += 1

        if s in ("completed", "failed", "cancelled"):
            sys.stdout.write("\n")
            _print_status(data)
            break

        time.sleep(1)


def _print_status(data: dict) -> None:
    s = data["status"]
    typer.echo(f"Status: {s}")
    typer.echo(f"Steps:  {data.get('steps_completed', 0)}")
    if data.get("result"):
        typer.echo(f"Result: {data['result']}")
    if data.get("error"):
        typer.echo(f"Error:  {data['error']}", err=True)


if __name__ == "__main__":
    app()
