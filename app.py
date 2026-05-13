import streamlit as st
import pandas as pd
import numpy as np

# 페이지 기본 설정
st.set_page_config(page_title="주차장 추천 서비스", layout="wide")

st.title("🚗 맞춤형 주차장 추천 서비스 (프로토타입)")
st.markdown("운전자의 우선순위(가격, 거리, 잔여 공간)에 따라 최적의 주차장을 추천해주는 데모입니다.")

# --- 1. 사용자 입력 (가중치 설정) ---
st.sidebar.header("🤔 주차 시 무엇이 가장 걱정되시나요?")
st.sidebar.markdown("1~5점으로 중요도를 설정해주세요.")
weight_price = st.sidebar.slider("💰 저렴한 요금", 1, 5, 3)
weight_dist = st.sidebar.slider("📍 목적지와의 가까운 거리", 1, 5, 3)
weight_space = st.sidebar.slider("🅿️ 넉넉한 주차 공간", 1, 5, 3)

# --- 2. 가상(Dummy) 주차장 데이터 ---
# (실제 서비스에서는 이 부분을 서울시 API 실시간 데이터로 교체합니다)
data = {
    '주차장명': ['A 공영주차장', 'B 민영주차장', 'C 빌딩주차장', 'D 환승주차장', 'E 쇼핑몰주차장'],
    '요금(1시간)': [2400, 6000, 5000, 1200, 8000],
    '목적지거리(m)': [800, 100, 500, 1200, 200],
    '총면수': [100, 50, 200, 300, 500],
    '잔여면수': [5, 20, 150, 10, 400]
}
df = pd.DataFrame(data)
df['잔여비율(%)'] = (df['잔여면수'] / df['총면수']) * 100

# --- 3. 추천 알고리즘 계산 ---
# 각 항목을 0~1 사이로 정규화 (Min-Max Scaling)
# 요금과 거리는 낮을수록 좋으므로 1에서 빼줍니다.
norm_price = 1 - (df['요금(1시간)'] - df['요금(1시간)'].min()) / (df['요금(1시간)'].max() - df['요금(1시간)'].min())
norm_dist = 1 - (df['목적지거리(m)'] - df['목적지거리(m)'].min()) / (df['목적지거리(m)'].max() - df['목적지거리(m)'].min())
norm_space = (df['잔여비율(%)'] - df['잔여비율(%)'].min()) / (df['잔여비율(%)'].max() - df['잔여비율(%)'].min())

# 사용자가 설정한 가중치를 곱하여 최종 점수 산출
df['추천점수(Score)'] = (weight_price * norm_price) + (weight_dist * norm_dist) + (weight_space * norm_space)

# 점수 높은 순으로 정렬
df = df.sort_values(by='추천점수(Score)', ascending=False).reset_index(drop=True)

# --- 4. 결과 출력 ---
st.subheader("🏆 추천 주차장 Top 3")

# 결과를 보기 좋게 포맷팅
display_df = df[['주차장명', '요금(1시간)', '목적지거리(m)', '잔여면수', '총면수', '추천점수(Score)']].head(3).copy()
display_df['추천점수(Score)'] = display_df['추천점수(Score)'].round(2)

st.dataframe(display_df, width='stretch')

st.info("💡 팁: 좌측 사이드바에서 우선순위 슬라이더를 움직여보세요. 유저의 상황에 따라 1위 주차장이 실시간으로 바뀝니다!")

st.markdown("---")
st.markdown("### 📊 전체 주차장 현황 (참고용)")
st.dataframe(df[['주차장명', '요금(1시간)', '목적지거리(m)', '잔여면수', '총면수', '잔여비율(%)']].round(1), width='stretch')
