"""PyPress Entry Point — equivalent to WordPress's index.php."""
import uvicorn, logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def main():
    uvicorn.run("backend.core.app:app", host="0.0.0.0", port=8000, reload=True, log_level="info")

if __name__ == "__main__":
    main()
