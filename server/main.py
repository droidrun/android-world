import uvicorn
import os


def main():
    uvicorn.run(
        "server.android_server:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=os.getenv("PORT", 5000),
        reload=os.getenv("RELOAD", False),
        log_level=os.getenv("LOG_LEVEL", "info"),
        workers=os.getenv("WORKERS", 1),
    )


if __name__ == "__main__":
    main()
