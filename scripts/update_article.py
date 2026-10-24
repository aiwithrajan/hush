import urllib.request
import json
import sys

API_KEY = "FLPM6kshMRqqZ2uqq6FN1byt"
ARTICLE_ID = 4902697
DEV_API_URL = f"https://dev.to/api/articles/{ARTICLE_ID}"

with open("DEV_POST.md", "r", encoding="utf-8") as f:
    body_markdown = f.read()

payload = {
    "article": {
        "body_markdown": body_markdown
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
    method="PUT"
)

try:
    with urllib.request.urlopen(req) as response:
        res_body = response.read().decode("utf-8")
        result = json.loads(res_body)
        print("ARTICLE UPDATED SUCCESSFULLY ON DEV.TO!")
        print("URL:", result.get("url"))
except urllib.error.HTTPError as e:
    err_body = e.read().decode("utf-8")
    print(f"HTTPError {e.code}: {err_body}", file=sys.stderr)
    sys.exit(1)
