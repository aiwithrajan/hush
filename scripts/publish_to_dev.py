import urllib.request
import json
import sys

API_KEY = "FLPM6kshMRqqZ2uqq6FN1byt"
DEV_API_URL = "https://dev.to/api/articles"

with open("DEV_POST.md", "r", encoding="utf-8") as f:
    body_markdown = f.read()

title = "Hush: I Hid 10 Emergencies in My Own Notifications. An On-Device Gemma OS Found All 10."
cover_image = "https://raw.githubusercontent.com/aiwithrajan/hush/main/hush_cover.png"
tags = ["devchallenge", "hf26challenge", "ai", "opensource"]

# Step 1: Create article (first as published: true or published: false)
payload = {
    "article": {
        "title": title,
        "published": True,
        "body_markdown": body_markdown,
        "tags": tags,
        "main_image": cover_image
    }
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    DEV_API_URL,
    data=data,
    headers={
        "Content-Type": "application/json",
        "api-key": API_KEY,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(req) as response:
        res_body = response.read().decode("utf-8")
        result = json.loads(res_body)
        print("SUCCESS!")
        print("Article ID:", result.get("id"))
        print("URL:", result.get("url"))
        print("Published:", result.get("published"))
        print("Cover Image:", result.get("cover_image") or result.get("main_image"))
except urllib.error.HTTPError as e:
    err_body = e.read().decode("utf-8")
    print(f"HTTPError {e.code}: {err_body}", file=sys.stderr)
    sys.exit(1)
