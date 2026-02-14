from openai import OpenAI

SYSTEM_PROMPT = """\
당신은 블로그 글 재작성 전문가입니다. 아래 규칙을 반드시 따르세요.

1. 원문의 소제목 구조(##)를 그대로 유지하세요.
2. 원문의 말투와 분위기(존댓말/반말, 이모티콘 사용 여부 등)를 동일하게 유지하세요.
3. 핵심 정보와 주제를 유지하되, 문장을 새롭게 재구성하세요.
4. 원문에 [이미지]나 [링크] 표시가 있으면 해당 위치를 그대로 표시하세요.
5. 결과물은 마크다운 없이 순수 텍스트로 작성하되, 소제목만 ## 으로 표시하세요.
6. 원문 길이와 비슷하게 작성하세요.
"""


def rewrite(title: str, content: str, api_key: str) -> str:
    """원문을 GPT-4o로 재작성한다."""
    client = OpenAI(api_key=api_key)

    user_message = f"# 원문 제목\n{title}\n\n# 원문 본문\n{content}"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        max_tokens=4096,
    )

    return response.choices[0].message.content
