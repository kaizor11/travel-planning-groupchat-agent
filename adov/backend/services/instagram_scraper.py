import os
from dotenv import load_dotenv
from apify_client import ApifyClient
import requests
from datetime import timedelta

load_dotenv()

apify_client = ApifyClient(os.getenv("APIFY_KEY"))
task = apify_client.task(os.getenv("TASK_URL"))

def scrapify_reel(reel_url):
    # PUT with payload updating instagram url
    put_load = {
            "username": [
        f"{reel_url}"
    ]}

    run_result = task.call(task_input=put_load)
    return next(apify_client.dataset(run_result["defaultDatasetId"]).iterate_items())
    
def main():
    result = scrapify_reel("https://www.instagram.com/reel/DKsqWZTv2tE/")
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