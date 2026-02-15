import difflib
import re
from urllib.parse import quote_plus

import streamlit as st
from scraper import scrape
from rewriter import rewrite


def attach_image_links(body: str) -> str:
    """본문의 [이미지: keyword]를 Google 이미지 검색 링크로 변환한다."""
    def replace_match(m):
        keyword = m.group(1).strip()
        search_url = f"https://www.google.com/search?q={quote_plus(keyword)}&tbm=isch"
        return f"[이미지] (추천 이미지 검색: {search_url})"

    return re.sub(r"\[이미지:\s*(.+?)\]", replace_match, body)


def parse_rewrite_result(text: str) -> dict:
    """GPT 결과를 [제목], [본문], [해시태그] 섹션으로 파싱한다."""
    title = ""
    body = ""
    hashtags = ""

    # 섹션 분리
    sections = re.split(r"\[제목\]|\[본문\]|\[해시태그\]", text)
    headers = re.findall(r"\[제목\]|\[본문\]|\[해시태그\]", text)

    mapping = {}
    for i, header in enumerate(headers):
        mapping[header] = sections[i + 1].strip() if i + 1 < len(sections) else ""

    title = mapping.get("[제목]", "")
    body = mapping.get("[본문]", "")
    hashtags = mapping.get("[해시태그]", "")

    # 파싱 실패 시 전체를 본문으로
    if not body:
        body = text
    return {"title": title, "body": body, "hashtags": hashtags}

st.set_page_config(page_title="블로그 재작성", page_icon="✏️", layout="wide")

# ── 비밀번호 잠금 ──
if not st.session_state.get("authenticated"):
    st.title("🔒 로그인")
    pw = st.text_input("비밀번호를 입력하세요", type="password")
    if st.button("확인", type="primary"):
        if pw == st.secrets["PASSWORD"]:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

# ── 메인 ──
st.title("✏️ 네이버 블로그 재작성")
st.caption("블로그 URL을 한 줄에 하나씩 입력하세요.")

urls_input = st.text_area(
    "블로그 URL 목록",
    placeholder="https://blog.naver.com/blogid/111111111\nhttps://blog.naver.com/blogid/222222222",
    height=150,
)

if st.button("재작성하기", type="primary", use_container_width=True):
    urls = [u.strip() for u in urls_input.strip().splitlines() if u.strip()]
    if not urls:
        st.error("블로그 URL을 입력해주세요.")
        st.stop()

    api_key = st.secrets["OPENAI_API_KEY"]
    results = []
    progress = st.progress(0, text="시작하는 중...")

    for i, url in enumerate(urls):
        progress.progress(i / len(urls), text=f"{i + 1}/{len(urls)} 처리 중...")

        # 1) 크롤링
        try:
            data = scrape(url)
        except Exception as e:
            results.append({"url": url, "error": f"크롤링 실패: {e}"})
            continue

        # 2) 재작성
        try:
            rewritten = rewrite(data["title"], data["content"], api_key)
        except Exception as e:
            results.append({"url": url, "error": f"재작성 실패: {e}"})
            continue

        # 3) 파싱 & 이미지 검색 & 통계
        parsed = parse_rewrite_result(rewritten)
        original_text = data["content"]
        image_count = original_text.count("[이미지")
        body = parsed["body"]

        # 이미지 검색 링크 생성
        body = attach_image_links(body)

        similarity = difflib.SequenceMatcher(None, original_text, body).ratio()

        results.append({
            "url": url,
            "title": data["title"],
            "original": original_text,
            "original_len": len(original_text),
            "image_count": image_count,
            "new_title": parsed["title"],
            "body": body,
            "hashtags": parsed["hashtags"],
            "rewritten_len": len(body),
            "similarity": similarity,
        })

    progress.progress(1.0, text="완료!")

    # ── 결과 리스트 ──
    st.markdown("---")
    st.subheader("결과")

    for i, r in enumerate(results, 1):
        if "error" in r:
            st.error(f"**{i}.** {r['url']}\n\n{r['error']}")
            continue

        # 요약 카드
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("원문 길이", f"{r['original_len']:,}자")
        col2.metric("이미지", f"{r['image_count']}장")
        col3.metric("재작성 길이", f"{r['rewritten_len']:,}자")
        col4.metric("유사율", f"{r['similarity']:.0%}")

        # 원문 & 재작성 결과 (접혀있음)
        with st.expander(f"**{i}. {r['title']}**", expanded=False):
            tab_rewrite, tab_original = st.tabs(["재작성 결과", "원문"])
            with tab_rewrite:
                if r["new_title"]:
                    st.markdown(f"**추천 제목**")
                    st.code(r["new_title"], language=None)
                st.markdown(f"**본문**")
                # 이미지 검색 링크를 클릭 가능하게 변환
                display_body = re.sub(
                    r"\(추천 이미지 검색: (https://[^\)]+)\)",
                    r"(추천 이미지 검색: [\1](\1))",
                    r["body"],
                )
                st.markdown(display_body)
                st.code(r["body"], language=None)
                st.caption("↑ 복사용 텍스트")
                if r["hashtags"]:
                    st.markdown(f"**해시태그**")
                    st.code(r["hashtags"], language=None)
            with tab_original:
                st.text(r["original"])

    st.balloons()
