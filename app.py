import difflib
import re
from urllib.parse import quote_plus

import streamlit as st
from scraper import scrape
from rewriter import rewrite


def attach_image_links(body: str, image_urls: list[str]) -> str:
    """본문의 [이미지: keyword] 또는 [이미지]를 원본 역이미지 검색 링크 + 키워드 검색 링크로 변환한다."""
    url_iter = iter(image_urls)

    def replace_match(m):
        full = m.group(0)
        # 키워드가 있으면 추출
        kw_match = re.match(r"\[이미지:\s*(.+?)\]", full)
        keyword = kw_match.group(1).strip() if kw_match else ""

        # 원본 이미지 URL이 있으면 Google Lens 역이미지 검색
        orig_url = next(url_iter, None)
        if orig_url:
            lens_url = f"https://lens.google.com/uploadbyurl?url={quote_plus(orig_url)}"
            result = f"[이미지] (유사 이미지 찾기: {lens_url})"
        elif keyword:
            search_url = f"https://www.google.com/search?q={quote_plus(keyword)}&tbm=isch"
            result = f"[이미지] (이미지 검색: {search_url})"
        else:
            result = "[이미지]"
        return result

    return re.sub(r"\[이미지:[^\]]*\]|\[이미지\]", replace_match, body)


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

st.set_page_config(page_title="블로그 재작성 for 세희", page_icon="✏️", layout="wide")

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
st.title("✏️ 네이버 블로그 재작성 for 세희")

# URL 입력 칸 관리
if "url_count" not in st.session_state:
    st.session_state["url_count"] = 3

url_count = st.session_state["url_count"]
valid_urls = []

st.markdown(f"**URL 목록 ({'{'}0{'}'})** 👇".replace("{0}", "0"))
url_placeholder = st.empty()

with url_placeholder.container():
    for idx in range(url_count):
        val = st.text_input(
            f"URL {idx + 1}",
            placeholder="https://blog.naver.com/blogid/123456789",
            key=f"url_input_{idx}",
            label_visibility="collapsed",
        )
        if val and val.strip():
            valid_urls.append(val.strip())

    col_add, col_count = st.columns([1, 3])
    if col_add.button("➕ URL 추가", key="add_url"):
        st.session_state["url_count"] += 1
        st.rerun()
    col_count.markdown(f"입력된 URL: **{len(valid_urls)}**개")

if st.button("재작성하기", type="primary", use_container_width=True):
    urls = valid_urls
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

        # 순수 텍스트 길이 계산 (이미지 태그, 키워드 제거)
        pure_body = re.sub(r"\[이미지:[^\]]*\]|\[이미지\]", "", body).strip()
        rewritten_len = len(pure_body)

        # 이미지 검색 링크 생성 (원본 이미지 URL로 역이미지 검색)
        body = attach_image_links(body, data.get("image_urls", []))

        similarity = difflib.SequenceMatcher(None, original_text, pure_body).ratio()

        results.append({
            "url": url,
            "title": data["title"],
            "original": original_text,
            "original_len": len(original_text),
            "image_count": image_count,
            "new_title": parsed["title"],
            "body": body,
            "hashtags": parsed["hashtags"],
            "rewritten_len": rewritten_len,
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
                # ## 소제목을 볼드로, 이미지 링크를 클릭 가능하게 변환
                display_body = re.sub(
                    r"^## (.+)$",
                    r"**\1**",
                    r["body"],
                    flags=re.MULTILINE,
                )
                display_body = re.sub(
                    r"\(유사 이미지 찾기: (https://[^\)]+)\)",
                    r"([유사 이미지 찾기 →](\1))",
                    display_body,
                )
                display_body = re.sub(
                    r"\(이미지 검색: (https://[^\)]+)\)",
                    r"([이미지 검색 →](\1))",
                    display_body,
                )
                st.markdown(display_body)

                # 복사용 텍스트: 이미지 링크를 [이미지1], [이미지2]... 로 변환
                img_counter = [0]
                def _number_images(m):
                    img_counter[0] += 1
                    return f"[이미지{img_counter[0]}]"
                copy_text = re.sub(
                    r"\[이미지\] \(유사 이미지 찾기: [^\)]+\)|\[이미지\] \(이미지 검색: [^\)]+\)|\[이미지\]",
                    _number_images,
                    r["body"],
                )

                # 전체 복사 텍스트 (제목 + 본문 + 해시태그)
                full_copy = ""
                if r["new_title"]:
                    full_copy += r["new_title"] + "\n\n"
                full_copy += copy_text
                if r["hashtags"]:
                    full_copy += "\n\n" + r["hashtags"]

                import json
                escaped = json.dumps(full_copy)
                st.components.v1.html(f"""
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                    <span style="font-weight:700;font-size:14px;">복사용 텍스트</span>
                    <button onclick="copyText(this)" style="
                        padding:4px 12px;font-size:13px;cursor:pointer;
                        border:1px solid #ccc;border-radius:6px;background:#fff;
                    ">📋 복사하기</button>
                </div>
                <script>
                function copyText(btn) {{
                    navigator.clipboard.writeText({escaped}).then(function() {{
                        btn.textContent = '✅ 복사 완료!';
                        btn.style.background = '#e6ffe6';
                        setTimeout(function() {{
                            btn.textContent = '📋 복사하기';
                            btn.style.background = '#fff';
                        }}, 2000);
                    }});
                }}
                </script>
                """, height=40)

                import hashlib
                content_hash = hashlib.md5(full_copy.encode()).hexdigest()[:8]
                st.text_area(
                    "copy",
                    value=full_copy,
                    height=300,
                    label_visibility="collapsed",
                    key=f"copy_{i}_{content_hash}",
                )

                if r["hashtags"]:
                    st.markdown(f"**해시태그**")
                    st.code(r["hashtags"], language=None)
            with tab_original:
                st.text(r["original"])

    st.balloons()
