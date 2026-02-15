import requests

PEXELS_URL = "https://api.pexels.com/v1/search"


def search_image(query: str, api_key: str) -> str | None:
    """Pexels에서 이미지를 검색하여 첫 번째 결과 URL을 반환한다."""
    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": 1, "size": "medium"}
    try:
        resp = requests.get(PEXELS_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if photos:
            return photos[0]["src"]["medium"]
    except Exception:
        pass
    return None
