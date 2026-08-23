"""Run the native backend under Uvicorn."""

import uvicorn


def main() -> None:
    """Start the ASGI server with environment-backed configuration."""
    uvicorn.run(
        "homelab_backend.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8099,
        proxy_headers=True,
    )


if __name__ == "__main__":
    main()
