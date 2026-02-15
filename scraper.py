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


def _is_naver_blog(url: str) -> bool:
    host = (urlparse(url.strip()).hostname or "").lower()
    return "blog.naver.com" in host


def scrape(url: str) -> dict:
    """URL에 따라 네이버 블로그 또는 일반 웹페이지를 크롤링한다."""
    url = url.strip()
    if _is_naver_blog(url):
        return _scrape_naver_blog(url)
    return _scrape_generic(url)


def _scrape_naver_blog(url: str) -> dict:
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
    image_urls = []
    container = soup.select_one("div.se-main-container")
    if container:
        content, image_urls = _extract_se_content(container)
    else:
        # 구형 에디터 fallback
        container = soup.select_one("div#postViewArea") or soup.select_one(
            "div.post_ct"
        )
        content = container.get_text("\n", strip=True) if container else ""

    if not content.strip():
        raise ValueError("본문을 추출하지 못했습니다. 비공개 글이거나 지원하지 않는 형식일 수 있습니다.")

    return {"title": title, "content": content, "image_urls": image_urls, "url": mobile_url}


def _scrape_generic(url: str) -> dict:
    """일반 웹페이지에서 제목과 본문을 추출한다."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # 제목
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"]
    elif soup.title:
        title = soup.title.get_text(strip=True)
    else:
        title = "제목 없음"

    # 본문 – article 태그 우선, 없으면 body
    article = soup.select_one("article") or soup.select_one("[role='main']")
    if not article:
        article = soup.body

    if not article:
        raise ValueError("본문을 추출하지 못했습니다.")

    # 불필요한 태그 제거
    for tag in article.select("script, style, nav, header, footer, aside, iframe"):
        tag.decompose()

    # img 태그를 [이미지] 마커로 치환하고 URL 추출
    image_urls = []
    for img in article.select("img"):
        src = img.get("data-lazy-src") or img.get("data-src") or img.get("src") or ""
        if src and not src.startswith("data:"):
            image_urls.append(src)
            img.replace_with("[이미지]")
        else:
            img.decompose()

    content = article.get_text("\n", strip=True)

    if not content.strip():
        raise ValueError("본문을 추출하지 못했습니다.")

    return {"title": title, "content": content, "image_urls": image_urls, "url": url}


# 하위 호환
scrape_blog = scrape


def _extract_se_content(container) -> tuple[str, list[str]]:
    """SmartEditor3 본문에서 텍스트 블록과 이미지 URL을 순서대로 추출한다."""
    blocks: list[str] = []
    image_urls: list[str] = []

    for module in container.select("div.se-module"):
        classes = module.get("class", [])

        # 소제목 / 인용
        if "se-module-text" in classes:
            text = module.get_text("\n", strip=True)
            if text:
                if module.select("strong, b"):
                    blocks.append(f"## {text}")
                else:
                    blocks.append(text)

        # 구분선
        elif "se-module-horizontalLine" in classes:
            blocks.append("---")

        # 이미지 — URL도 함께 추출
        elif "se-module-image" in classes:
            img_tag = module.select_one("img")
            img_url = ""
            if img_tag:
                img_url = img_tag.get("data-lazy-src") or img_tag.get("src") or ""

            caption = module.select_one("div.se-caption")
            if caption:
                cap_text = caption.get_text(strip=True)
                if cap_text:
                    blocks.append(f"[이미지: {cap_text}]")
                else:
                    blocks.append("[이미지]")
            else:
                blocks.append("[이미지]")

            if img_url:
                image_urls.append(img_url)

        # 링크/OG카드
        elif "se-module-oglink" in classes:
            link_text = module.get_text(strip=True)
            if link_text:
                blocks.append(f"[링크: {link_text}]")

    return _clean_content("\n\n".join(blocks)), image_urls


def _clean_content(text: str) -> str:
    """본문에서 작성자 정보, 해시태그, 하단 관련글 링크를 제거한다."""
    lines = text.split("\n")
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        # 해시태그 줄 (#블랙핑크, #aespa 등)
        if stripped.startswith("#") and not stripped.startswith("##"):
            continue
        # 하단 관련글 링크 블록
        if stripped.startswith("[링크:"):
            continue
        # 글/사진 저작권 표기 (글/사진 ©맛토, 사진 출처: 등)
        if re.match(r"^(글|사진|글/사진|photo|credit)\s*[©ⓒ:]", stripped, re.IGNORECASE):
            continue
        # SNS 핸들만 있는 줄 (@username, instagram.com/... 등)
        if re.match(r"^@\w+$", stripped):
            continue
        if re.match(r"^(instagram|insta|youtube|twitter|tiktok)\.com/", stripped, re.IGNORECASE):
            continue
        # 짧은 영문/숫자만 있는 줄 (SNS 아이디 등: luo_603)
        if re.match(r"^[a-zA-Z0-9_.]{2,20}$", stripped) and not stripped.isdigit():
            continue
        cleaned.append(line)
    return "\n".join(cleaned)
