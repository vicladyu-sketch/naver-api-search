#-*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from dotenv import load_dotenv
import koreanize_matplotlib
import numpy as np
from collections import Counter
import re

# 1. 환경 설정 및 세션 상태 초기화
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_dir, ".env"))

st.set_page_config(page_title="Naver Real-time Market Dashboard", layout="wide")

# CSS for Glassmorphism
st.markdown("""
    <style>
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# 2. Naver API 연동 함수
def get_api_credentials():
    # 1. Streamlit Secrets (for Cloud Deployment)
    # 2. .env (for Local Development)
    
    client_id = None
    client_secret = None
    
    try:
        if "NAVER_CLIENT_ID" in st.secrets:
            client_id = st.secrets["NAVER_CLIENT_ID"]
        if "NAVER_CLIENT_SECRET" in st.secrets:
            client_secret = st.secrets["NAVER_CLIENT_SECRET"]
    except:
        pass
        
    if not client_id:
        client_id = os.getenv("NAVER_CLIENT_ID")
    if not client_secret:
        client_secret = os.getenv("NAVER_CLIENT_SECRET")
        
    return client_id, client_secret

def call_naver_api(url, body=None):
    client_id, client_secret = get_api_credentials()
    if not client_id or not client_secret:
        st.error("🔑 네이버 API Client ID 또는 Secret이 설정되지 않았습니다. Streamlit Secrets 또는 .env 파일을 확인해 주세요.")
        return None
    
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", str(client_id))
    req.add_header("X-Naver-Client-Secret", str(client_secret))
    req.add_header("Content-Type", "application/json")
    
    try:
        data = json.dumps(body).encode("utf-8") if body else None
        with urllib.request.urlopen(req, data=data) as res:
            return json.loads(res.read().decode('utf-8'))
    except Exception as e:
        st.error(f"❌ API 호출 중 오류 발생: {e}")
        return None

def fetch_datalab_trend(keywords, start_date, end_date):
    url = "https://openapi.naver.com/v1/datalab/search"
    body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": "date",
        "keywordGroups": [{"groupName": k, "keywords": [k]} for k in keywords]
    }
    res = call_naver_api(url, body)
    return res['results'] if res else None

def fetch_shopping_trend(keywords, start_date, end_date):
    # 키워드별 쇼핑인사이트 트렌드 조회
    url = "https://openapi.naver.com/v1/datalab/shopping/category/keyword"
    # 쇼핑인사이트는 카테고리 ID가 필요함 (기본 '50000000'(패션의류) 등이나, 여기선 생략하고 카테고리별 트렌드 API 대신 검색어 트렌드 API를 주로 사용)
    # 실제 키워드 쇼핑 트렌드는 별도 API 권한이 필요할 수 있으므로, 검색 트렌드 결과를 기반으로 함
    return fetch_datalab_trend(keywords, start_date, end_date)

def fetch_search_results(keyword, category):
    category_map = {
        "news": "news", "blog": "blog", "cafe": "cafearticle", "shop": "shop"
    }
    cat_path = category_map.get(category, "blog")
    url = f"https://openapi.naver.com/v1/search/{cat_path}.json?query={urllib.parse.quote(keyword)}&display=100&sort=sim"
    
    # search API는 GET이므로 body 없음
    client_id, client_secret = get_api_credentials()
    if not client_id or not client_secret: return None
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", str(client_id))
    req.add_header("X-Naver-Client-Secret", str(client_secret))
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode('utf-8'))
    except:
        return None

# 3. 사이드바 - 실시간 입력 및 상태 관리
st.sidebar.title("🔍 실시간 검색 설정")
keywords_input = st.sidebar.text_input("분석 키워드 (쉼표 구분)", value="핫팩, 선풍기")
keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]

date_range = st.sidebar.date_input("분석 기간", 
                                  value=(datetime.now() - timedelta(days=90), datetime.now()),
                                  max_value=datetime.now())

# 4. 데이터 로드 로직 (Purely Real-time)
if len(date_range) == 2:
    start_dt, end_dt = date_range
    
    st.info(f"🔄 '{', '.join(keywords)}'에 대한 실시간 데이터를 네이버 API에서 직접 수집 중입니다...")
    
    # 트렌드 데이터 수집
    trend_results = fetch_datalab_trend(keywords, start_dt, end_dt)
    
    if trend_results:
        dfs = []
        for res in trend_results:
            tdf = pd.DataFrame(res['data'])
            tdf.columns = ['date', res['title']]
            dfs.append(tdf)
        df_trend = dfs[0]
        for i in range(1, len(dfs)):
            df_trend = pd.merge(df_trend, dfs[i], on='date', how='outer')
        df_trend['date'] = pd.to_datetime(df_trend['date'])
        
        # 메인 페이지 구성
        st.title(f"📊 Naver Real-time Dashboard: {', '.join(keywords)}")
        
        tab1, tab2, tab3, tab4 = st.tabs(["💡 트렌드 리포트", "📈 데이터 프로파일링", "📱 채널별 분석", "📂 Raw Data"])
        
        with tab1:
            st.header("실시간 검색어 트렌드")
            # KPI
            cols = st.columns(len(keywords))
            for i, k in enumerate(keywords):
                with cols[i]:
                    max_idx = df_trend[k].max()
                    avg_idx = df_trend[k].mean()
                    st.metric(f"{k} 최고 지수", f"{max_idx:.1f}", f"평균 {avg_idx:.1f}")
            
            # Trend Chart
            fig = px.line(df_trend, x='date', y=keywords, title="기간별 검색량 변화 (네이버 데이터랩)")
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.header("실시간 데이터 프로파일링")
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.subheader("기술 통계 요약")
                st.write(df_trend.describe())
            with col_p2:
                st.subheader("데이터 품질 지표")
                quality = pd.DataFrame({
                    "변수명": df_trend.columns,
                    "유형": [str(d) for d in df_trend.dtypes],
                    "결측치": df_trend.isnull().sum().values,
                    "고유값": df_trend.nunique().values
                })
                st.dataframe(quality, use_container_width=True)

        with tab3:
            st.header("플랫폼별 정보량 및 텍스트 마이닝")
            selected_k = st.selectbox("집중 분석 키워드 선택", keywords)
            
            # 실시간 카운트 수집
            categories = ["news", "blog", "cafe", "shop"]
            cat_counts = []
            all_text = ""
            
            for cat in categories:
                res = fetch_search_results(selected_k, cat)
                if res:
                    total = res.get('total', 0)
                    cat_counts.append({"Platform": cat, "Count": total})
                    # 텍스트 빈도 분석용 (제목 수집)
                    for item in res.get('items', []):
                        all_text += re.sub(r'<[^>]*>', '', item['title']) + " "
            
            if cat_counts:
                df_cat = pd.DataFrame(cat_counts)
                # Sunburst/Treemap
                fig_sun = px.sunburst(df_cat, path=['Platform'], values='Count', color='Count', title="플랫폼별 정보 점유율")
                st.plotly_chart(fig_sun, use_container_width=True)
                
                # Bar chart with Table
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.plotly_chart(px.bar(df_cat, x='Platform', y='Count', color='Platform'), use_container_width=True)
                with c2:
                    st.table(df_cat)
            
            # Word Frequency (Top 30)
            if all_text:
                st.subheader(f"'{selected_k}' 연관 키워드 TOP 30 (형태소 분석 제외)")
                words = re.findall(r'\b\w{2,}\b', all_text)
                word_counts = Counter(words).most_common(30)
                df_words = pd.DataFrame(word_counts, columns=['단어', '빈도'])
                fig_word = px.bar(df_words, x='빈도', y='단어', orientation='h', title="주요 키워드 출현 빈도")
                fig_word.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_word, use_container_width=True)

        with tab4:
            st.header("네이버 API 수집 Raw Data")
            st.dataframe(df_trend, use_container_width=True)
            csv = df_trend.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 수집 데이터 CSV 다운로드", csv, f"naver_live_{datetime.now().strftime('%H%M')}.csv", "text/csv")
            
    else:
        st.error("⚠️ 데이터를 불러오지 못했습니다. API 키 설정 및 네트워크 상태를 확인해 주세요.")
else:
    st.warning("분석할 날짜 범위를 선택해 주세요.")

st.sidebar.markdown("---")
st.sidebar.caption("실시간 수집 모드 활성화됨")
