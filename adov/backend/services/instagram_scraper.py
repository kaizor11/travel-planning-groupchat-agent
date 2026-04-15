import logging
import os
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()

logger = logging.getLogger(__name__)

apify_client = ApifyClient(os.getenv("APIFY_KEY"))
task = apify_client.task(os.getenv("TASK_URL"))


def scrapify_reel(reel_url: str) -> dict | None:
    """
    Scrape an Instagram reel via Apify and return the first result item.
    Returns None on any failure (timeout, empty dataset, API error) so callers
    can degrade gracefully without crashing the parse endpoint.
    """
    try:
        put_load = {"username": [reel_url]}
        run_result = task.call(task_input=put_load)
        item = next(apify_client.dataset(run_result["defaultDatasetId"]).iterate_items(), None)
        return item
    except StopIteration:
        return None
    except Exception as exc:
        logger.warning(f"[Apify] Failed to scrape {reel_url}: {exc}")
        return None


def main():
    result = scrapify_reel("https://www.instagram.com/reel/DKsqWZTv2tE/")
    if result:
        print(result["url"])
        print(result["caption"])
        print(result["hashtags"])
        print(result["timestamp"])
        print(result["locationName"])
        print(result["locationId"])
        print(result["ownerFullName"])
        print(result["ownerUsername"])
        print(result["transcript"])


if __name__ == "__main__":
    main()
