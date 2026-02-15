from openai import OpenAI

SYSTEM_PROMPT = """\
당신은 블로그 글 재작성 전문가입니다. 아래 규칙을 반드시 따르세요.

1. 원문의 소제목 구조(##)를 그대로 유지하세요.
2. 원문의 말투와 분위기(존댓말/반말, 이모티콘 사용 여부 등)를 동일하게 유지하세요.
3. 핵심 정보와 주제를 유지하되, 문장을 새롭게 재구성하세요.
4. 원문의 [이미지] 배치 패턴을 정확히 따르세요. 원문에서 [이미지]가 연속으로 2~4개 묶여 있으면 재작성에서도 반드시 같은 수만큼 연속 배치하세요. 총 개수도 원문과 동일하게 유지하세요. 각 이미지는 [이미지: 검색키워드] 형태로 표시하되, 검색키워드는 해당 문맥의 구체적인 영문 검색어(인물명, 브랜드명, 제품명 등 고유명사 포함)로 작성하세요. 연속된 이미지들은 같은 키워드여도 됩니다. 예:
[이미지: jennie blackpink lace bodysuit concert]
[이미지: jennie blackpink lace bodysuit concert]
[이미지: jennie blackpink lace bodysuit concert]
[이미지: jennie blackpink lace bodysuit concert]
5. 결과물은 마크다운 없이 순수 텍스트로 작성하되, 소제목만 ## 으로 표시하세요.
6. 원문 길이와 비슷하게 작성하세요.
7. 원문 작성자의 고유 정보(닉네임, 필명, SNS 계정, 인스타그램 ID, 블로그 이름, 자기소개, 저작권 표기 등)는 절대 포함하지 마세요. 이런 정보가 원문에 있더라도 재작성 결과에서는 완전히 제거하세요.

출력 형식은 반드시 아래와 같이 작성하세요:

[제목]
재작성 글에 어울리는 블로그 제목 (원문 제목과 다르게, 클릭하고 싶게 작성)

[본문]
재작성된 본문 내용

[해시태그]
#관련태그1 #관련태그2 ... (10~15개, 네이버 블로그 검색에 유리한 키워드 위주)
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
