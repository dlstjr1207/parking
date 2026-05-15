import streamlit as st
import pandas as pd
import requests
import folium
import os
from dotenv import load_dotenv
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

load_dotenv()

# 페이지 기본 설정
st.set_page_config(page_title="주차장 추천 서비스", layout="wide")

st.title("🚗 맞춤형 주차장 추천 서비스 (실시간 API 연동)")
st.markdown("서울시 실시간 공영주차장 API를 활용하여 우선순위에 따른 최적의 주차장을 추천합니다.")

try:
    # Streamlit Cloud 환경용 (Secrets)
    SEOUL_API_KEY = st.secrets["SEOUL_API_KEY"]
except:
    # 로컬 환경용 (.env 파일)
    SEOUL_API_KEY = os.environ.get("SEOUL_API_KEY", "")

@st.cache_data(ttl=300) # 5분마다 API 재호출
def load_realtime_parking_data():
    url = f"http://openapi.seoul.go.kr:8088/{SEOUL_API_KEY}/json/GetParkingInfo/1/200/"
    try:
        res = requests.get(url)
        data = res.json()
        rows = data['GetParkingInfo']['row']
        df = pd.DataFrame(rows)
        # 필요한 컬럼만 추출
        df = df[['PKLT_NM', 'ADDR', 'TPKCT', 'NOW_PRK_VHCL_CNT', 'BSC_PRK_CRG']]
        df.columns = ['주차장명', '주소', '총면수', '현재주차대수', '기본요금']
        
        # 숫자형 데이터 변환
        for col in ['총면수', '현재주차대수', '기본요금']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
        # 잔여면수 계산 (총면수 - 현재주차대수)
        df['잔여면수'] = df['총면수'] - df['현재주차대수']
        df.loc[df['잔여면수'] < 0, '잔여면수'] = 0
        df['잔여비율(%)'] = (df['잔여면수'] / df['총면수']) * 100
        df['잔여비율(%)'] = df['잔여비율(%)'].fillna(0)
        
        return df
    except Exception as e:
        st.error(f"API 호출 실패: {e}")
        return pd.DataFrame()

# 지오코딩 (주소 -> 위도/경도) 함수
@st.cache_data
def get_lat_lng(address):
    geolocator = Nominatim(user_agent="parking_app")
    try:
        # 지오코딩 정확도를 위해 '구'까지만 잘라서 검색하는 꼼수
        short_addr = " ".join(address.split()[:3]) 
        location = geolocator.geocode(short_addr)
        if location:
            return location.latitude, location.longitude
        return None, None
    except:
        return None, None

df_all = load_realtime_parking_data()

# --- 사용자 입력 ---
st.sidebar.header("🎯 목적지 및 우선순위 설정")
# API 데이터 124개 중 필터링을 위해 구 이름을 선택받음
gu_list = ["강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구", "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구", "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"]
destination = st.sidebar.selectbox("목적지 선택", gu_list, index=gu_list.index("종로구"))

st.sidebar.markdown("---")
st.sidebar.markdown("**1~5점으로 중요도를 설정해주세요.**")
weight_price = st.sidebar.slider("💰 저렴한 요금", 1, 5, 3)
weight_dist = st.sidebar.slider("📍 가까운 거리", 1, 5, 4)
weight_space = st.sidebar.slider("🅿️ 넉넉한 공간", 1, 5, 3)

if not df_all.empty and destination:
    # 해당 목적지(구 단위)가 포함된 주차장만 필터링
    df_filtered = df_all[df_all['주소'].str.contains(destination)].copy()
    
    if df_filtered.empty:
        st.warning(f"'{destination}'에 해당하는 실시간 공영주차장 데이터가 없습니다. (종로구, 중구, 영등포구 등을 검색해보세요)")
    else:
        st.success(f"'{destination}' 주변 {len(df_filtered)}개의 실시간 주차장 정보를 분석합니다!")
        
        # 목적지 좌표 가져오기
        dest_lat, dest_lng = get_lat_lng(f"서울 {destination}")
        if dest_lat is None:
            dest_lat, dest_lng = 37.5700, 126.9796 # 종로구 기본값
            
        with st.spinner("지도를 불러오는 중입니다..."):
            # 각 주차장 거리 계산
            distances, lats, lngs = [], [], []
            for idx, row in df_filtered.iterrows():
                lat, lng = get_lat_lng(row['주소'])
                if lat and lng:
                    dist = geodesic((dest_lat, dest_lng), (lat, lng)).meters
                else:
                    # 좌표를 못 찾으면 임의의 근처 좌표 부여 (데모용)
                    lat, lng = dest_lat + 0.005, dest_lng + 0.005 
                    dist = 9999
                lats.append(lat)
                lngs.append(lng)
                distances.append(dist)
                
            df_filtered['위도'] = lats
            df_filtered['경도'] = lngs
            df_filtered['거리(m)'] = distances

        # --- 알고리즘 계산 ---
        # Min-Max Scaling (가장 싼 곳 1점, 가장 비싼 곳 0점)
        if df_filtered['기본요금'].max() != df_filtered['기본요금'].min():
            norm_price = 1 - (df_filtered['기본요금'] - df_filtered['기본요금'].min()) / (df_filtered['기본요금'].max() - df_filtered['기본요금'].min())
        else: norm_price = 1

        if df_filtered['거리(m)'].max() != df_filtered['거리(m)'].min():
            norm_dist = 1 - (df_filtered['거리(m)'] - df_filtered['거리(m)'].min()) / (df_filtered['거리(m)'].max() - df_filtered['거리(m)'].min())
        else: norm_dist = 1
        
        if df_filtered['잔여비율(%)'].max() != df_filtered['잔여비율(%)'].min():
            norm_space = (df_filtered['잔여비율(%)'] - df_filtered['잔여비율(%)'].min()) / (df_filtered['잔여비율(%)'].max() - df_filtered['잔여비율(%)'].min())
        else: norm_space = 1

        df_filtered['추천점수(Score)'] = (weight_price * norm_price) + (weight_dist * norm_dist) + (weight_space * norm_space)
        df_filtered = df_filtered.sort_values(by='추천점수(Score)', ascending=False).reset_index(drop=True)

        # --- 시각화 (Folium Map & Custom Cards) ---
        # CSS 주입
        st.markdown("""
        <style>
        .parking-card {
            background-color: #ffffff;
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            border: 1px solid #f0f0f0;
        }
        .badge-best {
            background-color: #e8f3ff;
            color: #0066ff;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
            display: inline-block;
            margin-bottom: 12px;
        }
        .park-title {
            font-size: 20px;
            font-weight: 800;
            color: #111;
            margin: 0 0 5px 0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .park-desc {
            font-size: 14px;
            color: #888;
            margin: 0 0 15px 0;
        }
        .info-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-top: 10px;
            border-top: 1px solid #f5f5f5;
        }
        .price-text {
            font-size: 18px;
            font-weight: 800;
            color: #111;
        }
        .space-text {
            font-size: 14px;
            color: #ff4757;
            font-weight: bold;
        }
        .space-good {
            color: #2ed573;
            font-weight: bold;
            font-size: 14px;
        }
        .btn-nav {
            background-color: #0066ff;
            color: white !important;
            border: none;
            border-radius: 10px;
            padding: 14px;
            text-align: center;
            font-weight: bold;
            display: block;
            text-decoration: none;
            transition: 0.2s;
        }
        .btn-nav:hover {
            background-color: #0052cc;
            color: white !important;
        }
        </style>
        """, unsafe_allow_html=True)

        st.subheader("🗺️ 실시간 추천 위치 (지도)")
        m = folium.Map(location=[dest_lat, dest_lng], zoom_start=14)
        
        # 목적지
        folium.Marker([dest_lat, dest_lng], tooltip="목적지", icon=folium.Icon(color="red", icon="star")).add_to(m)
        
        # 추천 Top 3 마커 
        colors = ["red", "orange", "green"]
        for i, row in df_filtered.head(3).iterrows():
            rank = i + 1
            folium.Marker(
                [row['위도'], row['경도']],
                popup=f"[{rank}위] {row['주차장명']}<br>잔여: {int(row['잔여면수'])}대",
                tooltip=f"{rank}위 추천!",
                icon=folium.Icon(color=colors[i], icon="info-sign")
            ).add_to(m)
            
        # 지도 너비 확장
        st_folium(m, width=1200, height=450)

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("🏆 ParkWise 최적 추천 Top 3")
        
        # 3개의 카드를 나란히 배치
        cols = st.columns(3)
        for i, (idx, row) in enumerate(df_filtered.head(3).iterrows()):
            rank = i + 1
            dist_m = int(row['거리(m)'])
            space = int(row['잔여면수'])
            space_class = "space-good" if space >= 5 else "space-text"
            price = f"{int(row['기본요금']):,}원" if row['기본요금'] > 0 else "무료"
            
            card_html = f"""
<div class="parking-card">
<div class="badge-best">A{rank} 최적 추천</div>
<div class="park-title" title="{row['주차장명']}">{row['주차장명']}</div>
<div class="park-desc">🚶 {destination} 기준 도보 약 {dist_m//80}분 ({dist_m}m)</div>
<div class="info-row">
<span class="price-text">{price} <span style="font-size:12px; color:#888; font-weight:normal;">/기본</span></span>
<span class="{space_class}">여유 {space}대</span>
</div>
<a href="https://map.kakao.com/link/to/{row['주차장명']},{row['위도']},{row['경도']}" target="_blank" class="btn-nav">
▲ 카카오맵 안내 시작
</a>
</div>
"""
            cols[i].markdown(card_html, unsafe_allow_html=True)
            
        st.markdown("---")
        st.markdown("### 📊 주변 주차장 실시간 현황")
        st.dataframe(df_filtered[['주차장명', '주소', '기본요금', '거리(m)', '잔여면수', '총면수', '잔여비율(%)']].round(1), width='stretch')
