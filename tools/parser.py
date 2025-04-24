#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
이 스크립트는 wowhead_raw_data.txt 파일 내 HTML을 파싱하여,
각 직업별 전문화에 해당하는 제작 장비와 장식을 JSON 구조로 추출하고 저장합니다.
"""

import os
import re
import json
from bs4 import BeautifulSoup

def extract_item_id(href):
    """
    링크 URL에서 item= 이후의 숫자만 추출.
    예: /ko/item=222817/축성된-망토 -> "222817"
    """
    match = re.search(r'item=(\d+)', href)
    if match:
        return match.group(1)
    return ""

def parse_items(td_element):
    """
    td 태그 내부의 자식 요소들을 순회하며 각 아이템 정보를 리스트에 담아 반환.
    - <a> 태그인 경우: 텍스트와 링크에서 id 추출.
    - 텍스트 노드인 경우: 텍스트만 기록하고 id는 빈 문자열.
    <br> 태그는 구분용이므로 생략.
    """
    items = []
    # td 태그 안의 children은 Tag, NavigableString, 혹은 <br> 태그 등이 섞여 있음.
    for child in td_element.children:
        # <br> 태그는 건너뜁니다.
        if child.name == 'br':
            continue

        # 순수 텍스트인 경우
        if isinstance(child, str):
            text = child.strip()
            if text:
                items.append({
                    "name": text,
                    "id": ""
                })
        # 링크 태그 <a>의 경우
        elif child.name == 'a':
            link_text = child.get_text(strip=True)
            href = child.get("href", "")
            item_id = extract_item_id(href)
            items.append({
                "name": link_text,
                "id": item_id
            })
        # 그 외 태그가 있을 경우 (예: <b> 태그 등)
        else:
            text = child.get_text(strip=True)
            if text:
                items.append({
                    "name": text,
                    "id": ""
                })
    return items

def parse_html():
    # 파일 경로 설정
    input_path = os.path.join("data", "wowhead_raw_data.txt")
    output_path = os.path.join("data", "bis_crafting_items.json")
    
    # 파일 읽기
    with open(input_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # BeautifulSoup로 HTML 파싱
    soup = BeautifulSoup(html_content, "html.parser")
    
    # 최종 데이터 구조 (직업별)
    result = {}

    # h3 태그(class="heading-size-3")를 이용하여 직업명을 찾습니다.
    for h3 in soup.find_all("h3", class_="heading-size-3"):
        job_name = h3.get_text(strip=True)
        if not job_name:
            continue

        # h3 이후의 형제 요소 중 첫 번째 table 요소를 찾습니다.
        table = None
        for sibling in h3.find_next_siblings():
            if sibling.name == "table":
                table = sibling
                break
        
        if table is None:
            continue  # 테이블이 없으면 넘어갑니다.

        # 테이블 내부의 모든 행(tr)을 가져오고 첫 행(헤더)은 건너뛰기
        rows = table.find_all("tr")[1:]
        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 3:
                continue

            # 첫 번째 td: 전문화 정보
            spec_raw = tds[0].get_text(strip=True)
            # 전문화 이름에서 직업명이 포함되어 있다면 제거
            spec_name = spec_raw.replace(job_name, "").strip()
            # 제거 후 비어있다면 원래 전문화명을 사용
            if not spec_name:
                spec_name = spec_raw

            # 두 번째 td: 제작 장비(gear)
            gear_items = parse_items(tds[1])
            # 세 번째 td: 장식(embellishments)
            embellishments_items = parse_items(tds[2])

            # 직업명이 이미 result에 있다면 그대로, 없으면 추가
            if job_name not in result:
                result[job_name] = {}

            result[job_name][spec_name] = {
                "gear": gear_items,
                "embellishments": embellishments_items
            }
    
    # JSON으로 출력 (한글 깨짐 방지를 위해 ensure_ascii=False)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"JSON 파일이 성공적으로 저장되었습니다: {output_path}")

if __name__ == "__main__":
    parse_html()
