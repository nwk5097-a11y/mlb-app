import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="MLB Data Analysis",
    page_icon="⚾️",
    layout="wide"
)

# 제목
st.title('⚾️ MLB Data Analysis')

# 선수 정보 (선수 ID, 이름)
PLAYERS = {
    660271: {'name': 'Shohei Ohtani', 'team': 'LAD'},
    592450: {'name': 'Aaron Judge', 'team': 'NYY'}
}

@st.cache_data(ttl=3600)  # 1시간 캐싱
def get_player_stats(player_id, season=2025):
    """
    MLB Stats API를 사용하여 선수 통계를 가져옵니다.
    """
    try:
        # 선수 기본 정보 가져오기
        player_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
        player_response = requests.get(player_url, timeout=10)
        player_data = player_response.json()
        
        # 타자 통계 가져오기
        stats_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        params = {
            'stats': 'statsSingleSeason',
            'season': season,
            'group': 'hitting'
        }
        stats_response = requests.get(stats_url, params=params, timeout=10)
        stats_data = stats_response.json()
        
        if not stats_data.get('stats') or len(stats_data['stats']) == 0:
            return None
        
        player_info = player_data.get('people', [{}])[0]
        stats = stats_data['stats'][0].get('splits', [{}])[0].get('stat', {})
        
        # 나이 계산
        birth_date = player_info.get('birthDate', '')
        if birth_date:
            birth_year = int(birth_date.split('-')[0])
            age = season - birth_year
        else:
            age = None
        
        return {
            'Name': player_info.get('fullName', ''),
            'Team': player_info.get('currentTeam', {}).get('abbreviation', ''),
            'Age': age,
            'G': stats.get('gamesPlayed', 0),
            'AB': stats.get('atBats', 0),
            'AVG': stats.get('avg', 0.0),
            'OBP': stats.get('obp', 0.0),
            'SLG': stats.get('slg', 0.0),
            'OPS': stats.get('ops', 0.0),
            'HR': stats.get('homeRuns', 0),
            'RBI': stats.get('rbi', 0),
            'WAR': stats.get('war', 0.0) if 'war' in stats else None
        }
    except Exception as e:
        st.error(f"선수 데이터를 가져오는 중 오류 발생: {e}")
        return None

@st.cache_data(ttl=3600)
def load_sample_data(season=2025):
    """
    MLB Stats API를 사용하여 오타니와 에런 저지의 실제 데이터를 가져옵니다.
    """
    players_data = []
    
    for player_id, info in PLAYERS.items():
        stats = get_player_stats(player_id, season)
        if stats:
            players_data.append(stats)
        else:
            # API에서 데이터를 가져올 수 없는 경우 기본값 사용
            players_data.append({
                'Name': info['name'],
                'Team': info['team'],
                'Age': None,
                'G': 0,
                'AB': 0,
                'AVG': 0.0,
                'OBP': 0.0,
                'SLG': 0.0,
                'OPS': 0.0,
                'HR': 0,
                'RBI': 0,
                'WAR': None
            })
    
    return pd.DataFrame(players_data)

# 시즌 선택
season = st.sidebar.selectbox(
    '시즌 선택 (Select Season)',
    options=[2025, 2024, 2023],
    index=0
)

# 데이터 로드
with st.spinner(f'{season}시즌 데이터를 불러오는 중...'):
    df = load_sample_data(season)

# 비율 스탯 포맷팅 (소수점 3자리)
ratio_stats = ['AVG', 'OBP', 'SLG', 'OPS']
for stat in ratio_stats:
    if stat in df.columns:
        df[stat] = df[stat].apply(
            lambda x: f"{x:.3f}" if pd.notna(x) and isinstance(x, (int, float)) else x
        )

# 데이터프레임 표시
st.subheader(f'{season}시즌 타자 기록')

st.info(f"총 {len(df)}명의 선수")

# 데이터프레임 표시
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)

# 통계 요약
st.subheader('통계 요약')
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("총 선수 수", len(df))

with col2:
    if 'HR' in df.columns:
        total_hr = pd.to_numeric(df['HR'], errors='coerce').sum()
        st.metric("총 홈런", f"{total_hr:.0f}")

with col3:
    if 'RBI' in df.columns:
        total_rbi = pd.to_numeric(df['RBI'], errors='coerce').sum()
        st.metric("총 타점", f"{total_rbi:.0f}")

with col4:
    if 'AVG' in df.columns:
        avg_values = pd.to_numeric(df['AVG'], errors='coerce')
        avg_avg = avg_values.mean()
        if pd.notna(avg_avg):
            st.metric("평균 타율", f"{avg_avg:.3f}")
        else:
            st.metric("평균 타율", "N/A")
