import streamlit as st
from scraper import scrape_blog
from rewriter import rewrite

st.set_page_config(page_title="블로그 재작성", page_icon="✏️", layout="wide")

# ── 비밀번호 잠금 ──
if not st.session_state.get("authenticated"):
    st.title("🔒 로그인")
    pw = st.text_input("비밀번호를 입력하세요", type="password")
    if st.button("확인", type="primary"):
        if pw == st.secrets["app"]["password"]:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

# ── 메인 ──
st.title("✏️ 네이버 블로그 재작성")
st.caption("네이버 블로그 URL을 입력하면 비슷한 구조와 톤으로 글을 재작성해줍니다.")

url = st.text_input("네이버 블로그 URL", placeholder="https://blog.naver.com/blogid/123456789")

if st.button("재작성하기", type="primary", use_container_width=True):
    if not url:
        st.error("블로그 URL을 입력해주세요.")
        st.stop()

    api_key = st.secrets["openai"]["api_key"]

    # 1) 크롤링
    with st.spinner("블로그 글을 가져오는 중..."):
        try:
            data = scrape_blog(url)
        except Exception as e:
            st.error(f"크롤링 실패: {e}")
            st.stop()

    # 원문 표시
    with st.expander("📄 원문 보기", expanded=False):
        st.subheader(data["title"])
        st.text(data["content"])

    # 2) 재작성
    with st.spinner("AI가 재작성하는 중..."):
        try:
            result = rewrite(data["title"], data["content"], api_key)
        except Exception as e:
            st.error(f"재작성 실패: {e}")
            st.stop()

    # 결과 표시
    st.subheader("재작성 결과")
    st.text_area("결과", value=result, height=500, label_visibility="collapsed")

    # 복사 버튼
    st.code(result, language=None)
    st.caption("↑ 위 코드 블록 오른쪽 상단의 복사 버튼을 눌러 복사하세요.")
