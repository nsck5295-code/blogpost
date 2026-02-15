import re

from openai import OpenAI

SYSTEM_PROMPT = """\
당신은 블로그 글 재작성 전문가입니다. 아래 규칙을 반드시 따르세요.

1. 원문의 소제목 구조(##)를 그대로 유지하세요.
2. 원문의 말투와 분위기(존댓말/반말, 이모티콘 사용 여부 등)를 동일하게 유지하세요.
3. 핵심 정보와 주제를 유지하되, 문장을 새롭게 재구성하세요.
4. 원문에 [이미지]라고 표시된 곳이 있습니다. 이미지 위치를 표시해야 하므로, 원문의 [이미지] 태그를 절대 생략하지 마세요.
   - 원문에 [이미지]가 N개 있으면, 재작성에서도 반드시 N개의 [이미지] 태그를 동일한 위치에 포함하세요.
   - 원문에서 [이미지]가 연속으로 묶여 있으면 재작성에서도 동일하게 연속 배치하세요.
   - [이미지] 태그가 하나라도 빠지면 실패입니다.
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


def _get_image_groups(content: str) -> list[int]:
    """원문의 이미지 묶음 패턴을 추출한다. 예: [2, 1, 4, 3] = 2개묶음, 1개, 4개묶음, 3개묶음."""
    groups: list[int] = []
    count = 0
    for line in content.split("\n"):
        stripped = line.strip()
        if "[이미지" in stripped:
            count += 1
        elif stripped == "" and count > 0:
            continue  # 이미지 사이 빈줄은 무시
        else:
            if count > 0:
                groups.append(count)
                count = 0
    if count > 0:
        groups.append(count)
    return groups


def _analyze_image_pattern(content: str) -> str:
    """원문의 이미지 배치 패턴을 분석하여 설명 문자열로 반환한다."""
    groups = _get_image_groups(content)
    total = sum(groups)
    if not groups:
        return ""
    pattern = ", ".join(str(g) for g in groups)
    return (
        f"\n\n⚠️ 절대 중요: 원문에는 [이미지] 태그가 총 {total}개 있습니다. "
        f"재작성에서도 반드시 {total}개의 [이미지] 태그를 포함하세요. "
        f"묶음 패턴: [{pattern}]. 하나라도 빠뜨리면 안 됩니다."
    )


def _ensure_images(rewritten: str, original_content: str) -> str:
    """재작성 결과에 이미지 태그가 부족하면 원문 패턴 기반으로 삽입한다."""
    groups = _get_image_groups(original_content)
    expected = sum(groups)
    if expected == 0:
        return rewritten

    actual = len(re.findall(r"\[이미지", rewritten))
    if actual >= expected // 2:
        return rewritten  # GPT가 충분히 넣었으면 그대로

    # [본문] 섹션 추출
    body_match = re.search(r"\[본문\]\s*(.+?)(?=\[해시태그\]|\Z)", rewritten, re.DOTALL)
    if body_match:
        pre = rewritten[: body_match.start(1)]
        body = body_match.group(1).strip()
        post = rewritten[body_match.end(1) :]
    else:
        pre = ""
        body = rewritten
        post = ""

    # 본문을 단락으로 분리
    paras = [p for p in body.split("\n\n") if p.strip()]
    n_paras = len(paras)
    n_groups = len(groups)

    if n_paras == 0:
        # 단락이 없으면 이미지만 추가
        img_block = "\n\n".join("\n".join(["[이미지]"] * g) for g in groups)
        return pre + img_block + post

    # 이미지 그룹을 단락 사이에 균등 배치
    result: list[str] = []
    gi = 0
    for i, para in enumerate(paras):
        result.append(para)
        if gi < n_groups:
            # 현재 단락 후에 이미지를 넣을지 결정 (균등 분배)
            threshold = (gi + 1) * n_paras / (n_groups + 1)
            if i + 1 >= threshold:
                result.append("\n".join(["[이미지]"] * groups[gi]))
                gi += 1

    # 남은 이미지 그룹 추가
    while gi < n_groups:
        result.append("\n".join(["[이미지]"] * groups[gi]))
        gi += 1

    new_body = "\n\n".join(result)
    return pre + "\n" + new_body + "\n" + post


def rewrite(title: str, content: str, api_key: str) -> str:
    """원문을 GPT-4o로 재작성한다."""
    client = OpenAI(api_key=api_key)

    image_hint = _analyze_image_pattern(content)
    system = SYSTEM_PROMPT + image_hint
    user_message = f"# 원문 제목\n{title}\n\n# 원문 본문\n{content}"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        max_tokens=8192,
    )

    result = response.choices[0].message.content

    # 이미지 태그 부족 시 프로그래밍으로 보정
    result = _ensure_images(result, content)

    return result
