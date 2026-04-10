#-*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from dotenv import load_dotenv
import re
import numpy as np
from collections import Counter
from phs_logic import calculate_phs_score, diagnose_gentrification_stage, calculate_dna_similarity

# 1. 환경 설정 및 세션 상태 초기화
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_dir, ".env"))

st.set_page_config(page_title="Post-Hotplace Detection System (PHS)", layout="wide")

# CSS for Modern UI
st.markdown("""
    <style>
    .stApp { background: #0d1117; color: #c9d1d9; }
    .metric-card {
        background: #161b22;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #30363d;
        text-align: center;
    }
    .phs-score {
        font-size: 48px;
        font-weight: bold;
        color: #58a6ff;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. API 연동 함수
def get_naver_credentials():
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")
    try:
        if "NAVER_CLIENT_ID" in st.secrets: client_id = st.secrets["NAVER_CLIENT_ID"]
        if "NAVER_CLIENT_SECRET" in st.secrets: client_secret = st.secrets["NAVER_CLIENT_SECRET"]
    except: pass
    return client_id, client_secret

def fetch_datalab_trend(keywords, start_date, end_date):
    cid, csec = get_naver_credentials()
    if not cid: return None
    url = "https://openapi.naver.com/v1/datalab/search"
    body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": "date",
        "keywordGroups": [{"groupName": k, "keywords": [k]} for k in keywords]
    }
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", str(cid))
    req.add_header("X-Naver-Client-Secret", str(csec))
    req.add_header("Content-Type", "application/json")
    try:
        data = json.dumps(body).encode("utf-8")
        with urllib.request.urlopen(req, data=data) as res:
            return json.loads(res.read().decode('utf-8'))['results']
    except: return None

def fetch_naver_search(keyword, category):
    cid, csec = get_naver_credentials()
    if not cid: return None
    cat_map = {"news": "news", "blog": "blog", "cafe": "cafearticle", "shop": "shop"}
    url = f"https://openapi.naver.com/v1/search/{cat_map.get(category, 'blog')}.json?query={urllib.parse.quote(keyword)}&display=50&sort=sim"
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", str(cid))
    req.add_header("X-Naver-Client-Secret", str(csec))
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode('utf-8'))
    except: return None

# 3. Kakao Map HTML Core
def generate_kakao_map_html(key, keyword=""):
    return f"""
    <div id="map" style="width:100%;height:500px;border-radius:12px;border:1px solid #30363d;"></div>
    <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={key}&libraries=services"></script>
    <script>
        var mapContainer = document.getElementById('map'),
            mapOption = {{ center: new kakao.maps.LatLng(37.5446, 127.0560), level: 3 }};
        if (typeof kakao !== 'undefined') {{
            var map = new kakao.maps.Map(mapContainer, mapOption);
            var ps = new kakao.maps.services.Places();
            ps.keywordSearch("{keyword}", function(data, status) {{
                if (status === kakao.maps.services.Status.OK) {{
                    var bounds = new kakao.maps.LatLngBounds();
                    for (var i=0; i<data.length; i++) {{
                        var marker = new kakao.maps.Marker({{ map: map, position: new kakao.maps.LatLng(data[i].y, data[i].x) }});
                        bounds.extend(new kakao.maps.LatLng(data[i].y, data[i].x));
                    }}
                    map.setBounds(bounds);
                }}
            }});
        }}
    </script>
    """

# 4. Main Page Structure
st.title("🛡️ Post-Hotplace Detection System (PHS)")
st.markdown("상권 DNA 분석 및 선행 지표 기반 '포스트 핫플레이스' 탐지 시스템")

# Sidebar
with st.sidebar:
    st.header("⚙️ 분석 설정")
    anchor_city = st.selectbox("Anchor 상권 (DNA 기준점)", ["성수동 (2015)", "연남동 (2014)", "한남동 (2013)"])
    candidate_target = st.text_input("분석 대상지 (Candidate)", value="신당동")
    
    st.markdown("---")
    industry_preset = st.multiselect("주요 DNA 지표 (업종/공간)", 
                                     ["노후 건축물 비율", "6m 미만 도로 밀도", "독립 카페 비중", "업종 전환율", "SNS 선행지표"],
                                     default=["노후 건축물 비율", "독립 카페 비중", "SNS 선행지표"])

# Logic Layer: Simulated DNA Data
# 실제 데이터 연동 전 가상의 DNA 벡터 생성 (계획서 기반)
anchor_dna = [85, 70, 75, 80, 90] # 성수동 과거 DNA
candidate_dna = [78, 65, 55, 60, 45] # 신당동 현재 DNA

# 5. PHS Summary Section
col1, col2, col3 = st.columns([1.5, 2, 1.5])

with col2:
    similarity = calculate_dna_similarity(anchor_dna, candidate_dna)
    # 검색 데이터 기반의 Trend Signal 계산 (가상)
    trend_sig = 55 # 네이버 검색량 증가율 등 반영 가중치
    phs_score = calculate_phs_score(80, 70, trend_sig) # 임의의 공간/업종 점수와 트렌드 결합
    diagnosis = diagnose_gentrification_stage(phs_score)
    
    st.markdown(f"""
        <div class="metric-card">
            <h4>PHS (Post Hot-place Score)</h4>
            <div class="phs-score">{phs_score:.1f}</div>
            <p style="color:{diagnosis['color']}; font-weight:bold;">[{diagnosis['name']}]</p>
            <p style="font-size:14px;">{diagnosis['desc']}</p>
        </div>
        """, unsafe_allow_html=True)

# 6. Detailed Analysis Tabs
tab1, tab2, tab3 = st.tabs(["🧬 DNA Matching", "📡 Lead Signal Analysis", "🗺️ Spatial Exploration"])

with tab1:
    st.subheader(f"Anchor({anchor_city}) vs Candidate({candidate_target}) DNA 일치도")
    
    df_compare = pd.DataFrame({
        "DNA Factor": ["Spatial", "Industry", "Trend", "Rent", "Perception"],
        "Anchor (Past)": anchor_dna,
        "Candidate (Present)": candidate_dna
    })
    
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(r=anchor_dna, theta=df_compare['DNA Factor'], fill='toself', name='Anchor DNA'))
    fig_radar.add_trace(go.Scatterpolar(r=candidate_dna, theta=df_compare['DNA Factor'], fill='toself', name='Candidate DNA'))
    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=True, title="상권 DNA 구조 비교")
    st.plotly_chart(fig_radar, use_container_width=True)
    
    st.success(f"두 상권의 DNA 유사도는 **{similarity:.1f}%**입니다.")

with tab2:
    st.subheader("선행 지표(Lead Signal) 분석")
    with st.spinner("네이버 검색어 트렌드 분석 중..."):
        # Anchor와 Candidate의 최근 검색량 추이 비교
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=180)
        trend_keywords = [candidate_target, anchor_city.split(" ")[0]]
        trends = fetch_datalab_trend(trend_keywords, start_dt, end_dt)
        
        if trends:
            dfs = []
            for res in trends:
                tdf = pd.DataFrame(res['data'])
                tdf.columns = ['date', res['title']]
                dfs.append(tdf)
            df_merged = pd.merge(dfs[0], dfs[1], on='date')
            df_merged['date'] = pd.to_datetime(df_merged['date'])
            
            # 증가율 계산 (Lead Signal)
            df_merged['Growth'] = df_merged[candidate_target].pct_change().rolling(window=7).mean() * 100
            
            fig_trend = px.line(df_merged, x='date', y=[candidate_target, 'Growth'], 
                                 title=f"{candidate_target} 검색량 및 증가율(Lead Signal)",
                                 labels={"value": "지수", "variable": "지표"})
            st.plotly_chart(fig_trend, use_container_width=True)

with tab3:
    st.subheader(f"{candidate_target} 마이크로블록 분석")
    k_key = os.getenv("KAKAO_MAP_JS_KEY", "b75b39c26830047512e095defdb4ae22")
    components.html(generate_kakao_map_html(k_key, candidate_target), height=550)
    st.info("지도는 100m 寃⑹옄/H3 留덉씠?щ줈釉붾줉 ?⑥쐞??遺꾩꽍??蹂묓뻾?섎릺, ?꾩옱??Kaako Map API瑜??듯빐 ?쒖옉 장소를 탐색합니다.")

# 7. Channel Impact (Naver Search)
st.markdown("---")
st.subheader("📱 소셜 및 검색 반응 분석")
res_search = fetch_naver_search(candidate_target, "blog")
if res_search:
    items = res_search.get('items', [])
    titles = [re.sub(r'<[^>]*>', '', i['title']) for i in items]
    words = re.findall(r'\b\w{2,}\b', " ".join(titles))
    top_words = Counter(words).most_common(15)
    df_w = pd.DataFrame(top_words, columns=['단어', '빈도'])
    st.plotly_chart(px.bar(df_w, x='빈도', y='단어', orientation='h', title=f"'{candidate_target}' 연관 키워드 TOP 15"), use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.caption("PHS Analysis v1.0 | DNA-driven Area Detection")
