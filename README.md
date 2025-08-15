
# Streamlit Flight Handling Visualizer

## 설치
```bash
pip install -r requirements.txt
```

## 실행
```bash
streamlit run app.py
```

## 사용법
1. 좌측 사이드바에서 운영일 시작 시각(기본 02시)과 BASE_DATE를 지정
2. CSV/엑셀 업로드 또는 '샘플 데이터 불러오기' 클릭
3. 상단 타임라인(ATD/ATA 점 포함) + 하단 10분(기본) 동시 작업 라인 확인
4. '전체 그림 PNG로 다운로드' 버튼으로 이미지 저장

## 데이터 포맷
- 컬럼: `FLT_DEP, ATD, FLT_ARR, ATA` (ATD/ATA는 4자리 HHMM)
- 자정 넘어가는 로직: 운영일 시작 시각보다 이른 HHMM은 다음날로 자동 보정
