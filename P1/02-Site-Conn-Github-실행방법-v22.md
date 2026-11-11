# 02-Site-Conn-Github-실행방법-v22

- 작성일: 2026-11-12
- 작업 폴더: /Users/KBS/kbsjmj/08-DevOps/02-Site-Conn/02-Site-Conn-Github/P1
- 짝 문서: Site-Conn-Github-지침-v22.md, Site-Conn-Github-컨텍스트-v22.md
- 이 문서는 Site-Conn-Local의 실행방법과 별개다. Local 문서는 이 문서에서 참조하지 않는다.

## 1. 현재시황뉴스 PDF 만들기

1. 입력 파일을 `P1/report/inputs/` 아래에 만든다. 이름은 `현재시황뉴스 (YYYYMMDD)-vN.json`이다. 내용과 형식은 보고서 입력 규칙을 따른다 (표 행의 `check` 값으로 종가·등락·등락률을 검산한다).
2. 실행 명령 (P1 폴더에서):

   ```bash
   cd "/Users/KBS/kbsjmj/08-DevOps/02-Site-Conn/02-Site-Conn-Github/P1"
   python3 main.py current-news --input "report/inputs/현재시황뉴스 (YYYYMMDD)-vN.json"
   ```

3. 결과:
   - PDF: 프로젝트 폴더 루트 (`02-Site-Conn-Github/현재시황뉴스 (YYYYMMDD)-vN.pdf`).
   - HTML은 PDF 변환용 임시 파일이며 자동으로 지워진다 (보고서는 PDF만 남긴다).
   - 기록: `P1/out/현재시황뉴스 (YYYYMMDD)-vN.manifest.json`.
4. 같은 번호의 파일이 이미 있으면 실패하고 아무 파일도 덮어쓰지 않는다. 번호를 `report_no`에서 바꾸거나 빼서 다음 번호를 쓴다.

## 2. 검사 항목

- 표 검산: 종가, 등락, 등락률이 입력 값과 같은지, 등락률이 종가와 등락폭으로 계산한 값과 맞는지 본다. 어긋나면 "입력 검산 실패"가 나오고 파일을 만들지 않는다.
- 쪽 확인: 4쪽 이하, 2쪽 첫 줄 "2. 주요 경제 지표", 3쪽 첫 줄 "3. 참고 사항". 문제가 있으면 "쪽 확인 문제"가 나온다. 문장을 줄여 다시 실행한다.

## 3. 주의

- Chrome이 설치되어 있어야 PDF를 만든다 (`/Applications/Google Chrome.app`).
- 입력 값은 사람이 적는다. 프로그램은 기사를 찾지 않는다. 검색으로 값을 확인한 뒤 입력 파일에 적는다.
- 값을 찾지 못하면 "—"로 두고 3절에 이유를 적는다. 이전 버전의 값을 그대로 복사하지 않는다.

## 변경 이력

- v22 (2026-11-12): 최초 작성. 현재시황뉴스 (20261112)-v1 생성 절차 기록. 지침, 컨텍스트 v22와 번호 맞춤.
