import streamlit as st
from scraper import scrape_blog
from rewriter import rewrite

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
st.caption("네이버 블로그 URL을 한 줄에 하나씩 입력하세요.")

urls_input = st.text_area(
    "네이버 블로그 URL 목록",
    placeholder="https://blog.naver.com/blogid/111111111\nhttps://blog.naver.com/blogid/222222222",
    height=150,
)

if st.button("재작성하기", type="primary", use_container_width=True):
    urls = [u.strip() for u in urls_input.strip().splitlines() if u.strip()]
    if not urls:
        st.error("블로그 URL을 입력해주세요.")
        st.stop()

    api_key = st.secrets["OPENAI_API_KEY"]
    progress = st.progress(0, text="시작하는 중...")

    for i, url in enumerate(urls):
        st.markdown(f"---\n### {i + 1}/{len(urls)}")
        progress.progress((i) / len(urls), text=f"{i + 1}/{len(urls)} 처리 중...")

        # 1) 크롤링
        with st.spinner(f"크롤링 중... ({url})"):
            try:
                data = scrape_blog(url)
            except Exception as e:
                st.error(f"크롤링 실패: {url}\n{e}")
                continue

        with st.expander(f"📄 원문: {data['title']}", expanded=False):
            st.text(data["content"])

        # 2) 재작성
        with st.spinner("AI가 재작성하는 중..."):
            try:
                result = rewrite(data["title"], data["content"], api_key)
            except Exception as e:
                st.error(f"재작성 실패: {e}")
                continue

        st.code(result, language=None)
        st.caption("↑ 오른쪽 상단 복사 버튼으로 복사하세요.")

    progress.progress(1.0, text="완료!")
    st.balloons()
