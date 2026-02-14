import re
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.0 Mobile/15E148 Safari/604.1"
    )
}


def parse_blog_url(url: str) -> str:
    """네이버 블로그 URL을 모바일 URL로 변환한다."""
    url = url.strip()
    parsed = urlparse(url)
    host = parsed.hostname or ""

    # blog.naver.com/{blogId}/{postNo}
    if host in ("blog.naver.com", "m.blog.naver.com"):
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2:
            blog_id, post_no = parts[0], parts[1]
            return f"https://m.blog.naver.com/{blog_id}/{post_no}"

    # blog.naver.com/PostView.naver?blogId=...&logNo=...
    if "PostView" in parsed.path or "PostView" in url:
        qs = parse_qs(parsed.query)
        blog_id = qs.get("blogId", [None])[0]
        post_no = qs.get("logNo", [None])[0]
        if blog_id and post_no:
            return f"https://m.blog.naver.com/{blog_id}/{post_no}"

    raise ValueError(
        "올바른 네이버 블로그 URL을 입력해주세요.\n"
        "예: https://blog.naver.com/blogid/123456789"
    )


def scrape_blog(url: str) -> dict:
    """네이버 블로그 모바일 페이지에서 제목과 본문을 추출한다."""
    mobile_url = parse_blog_url(url)
    resp = requests.get(mobile_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # 제목 추출
    title_tag = soup.select_one("div.se-module-text.se-title-text") or soup.select_one(
        "div.tit_h3"
    )
    if title_tag:
        title = title_tag.get_text(strip=True)
    else:
        og = soup.find("meta", property="og:title")
        title = og["content"] if og else "제목 없음"

    # 본문 추출 – SmartEditor 구조 (se-main-container)
    container = soup.select_one("div.se-main-container")
    if container:
        content = _extract_se_content(container)
    else:
        # 구형 에디터 fallback
        container = soup.select_one("div#postViewArea") or soup.select_one(
            "div.post_ct"
        )
        content = container.get_text("\n", strip=True) if container else ""

    if not content.strip():
        raise ValueError("본문을 추출하지 못했습니다. 비공개 글이거나 지원하지 않는 형식일 수 있습니다.")

    return {"title": title, "content": content, "url": mobile_url}


def _extract_se_content(container) -> str:
    """SmartEditor3 본문에서 텍스트 블록을 순서대로 추출한다."""
    blocks: list[str] = []
    for module in container.select("div.se-module"):
        classes = module.get("class", [])

        # 소제목 / 인용
        if "se-module-text" in classes:
            text = module.get_text("\n", strip=True)
            if text:
                # 볼드/소제목 구분을 위해 strong 태그 확인
                if module.select("strong, b"):
                    blocks.append(f"## {text}")
                else:
                    blocks.append(text)

        # 구분선
        elif "se-module-horizontalLine" in classes:
            blocks.append("---")

        # 이미지 캡션
        elif "se-module-image" in classes:
            caption = module.select_one("div.se-caption")
            if caption:
                cap_text = caption.get_text(strip=True)
                if cap_text:
                    blocks.append(f"[이미지: {cap_text}]")
            else:
                blocks.append("[이미지]")

        # 링크/OG카드
        elif "se-module-oglink" in classes:
            link_text = module.get_text(strip=True)
            if link_text:
                blocks.append(f"[링크: {link_text}]")

    return "\n\n".join(blocks)
