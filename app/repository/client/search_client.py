# app/repository/client/search_client.py
import os
import requests
from app.repository.client.base import BaseSearchClient
from dotenv import load_dotenv

if os.getenv("KUBERNETES_SERVICE_HOST") is None:
    load_dotenv()


class SerperSearchClient(BaseSearchClient):
    def __init__(self):
        self.api_key = os.getenv("SERPER_API_KEY")

    def search(self, query: str, num: int = 10) -> list:
        # 노트북의 web_search_serper 로직 이식
        url = "https://google.serper.dev/search"
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = {"q": query, "num": num}

        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)
            r.raise_for_status()
            j = r.json()
            organic = j.get("organic", [])
            results = []
            for item in organic:
                results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet"),
                })
            return results
        except Exception as e:
            print(f"[SerperSearchClient] Error: {e}")
            return []