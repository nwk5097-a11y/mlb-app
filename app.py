import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import plotly.graph_objects as go
import base64
from io import BytesIO

# Base64 인코딩된 이미지 불러오기
try:
    from images_base64 import OHTANI_IMAGE_BASE64, SAWAMURA_IMAGE_BASE64
    IMAGES_LOADED = True
except ImportError:
    IMAGES_LOADED = False
    OHTANI_IMAGE_BASE64 = None
    SAWAMURA_IMAGE_BASE64 = None

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
def get_player_pitching_stats(player_id, season=2025):
    """
    MLB Stats API를 사용하여 선수의 투수 통계를 가져옵니다.
    """
    try:
        stats_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        params = {
            'stats': 'statsSingleSeason',
            'season': season,
            'group': 'pitching'
        }
        stats_response = requests.get(stats_url, params=params, timeout=10)
        stats_data = stats_response.json()
        
        if not stats_data.get('stats') or len(stats_data['stats']) == 0:
            return None
        
        stats = stats_data['stats'][0].get('splits', [{}])[0].get('stat', {})
        
        return {
            'W': stats.get('wins', 0),
            'L': stats.get('losses', 0),
            'ERA': stats.get('era', 0.0),
            'SO': stats.get('strikeOuts', 0),
            'IP': stats.get('inningsPitched', 0.0),
            'WHIP': stats.get('whip', 0.0)
        }
    except Exception as e:
        return None

@st.cache_data(ttl=3600)
def get_player_game_log(player_id, season=2025):
    """
    MLB Stats API를 사용하여 선수의 게임 로그 데이터를 가져옵니다.
    시즌 시작부터 끝까지의 누적 OPS 추이를 계산하기 위해 사용합니다.
    """
    try:
        # 게임 로그 가져오기
        game_log_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        params = {
            'stats': 'gameLog',
            'season': season,
            'group': 'hitting',
            'gameType': 'R'  # Regular season only
        }
        response = requests.get(game_log_url, params=params, timeout=10)
        data = response.json()
        
        if not data.get('stats') or len(data['stats']) == 0:
            return None
        
        game_logs = data['stats'][0].get('splits', [])
        
        # 날짜와 누적 통계 계산
        game_data = []
        cumulative_ab = 0
        cumulative_h = 0
        cumulative_bb = 0
        cumulative_hbp = 0
        cumulative_sf = 0
        cumulative_tb = 0  # Total Bases (총 루타)
        
        for game in sorted(game_logs, key=lambda x: x.get('date', '')):
            stat = game.get('stat', {})
            date = game.get('date', '')
            
            # 각 게임의 통계를 누적
            game_ab = stat.get('atBats', 0)
            game_h = stat.get('hits', 0)
            game_bb = stat.get('baseOnBalls', 0)
            game_hbp = stat.get('hitByPitch', 0)
            game_sf = stat.get('sacFlies', 0)
            
            # Total Bases 계산
            # 먼저 totalBases 필드 확인
            game_tb = stat.get('totalBases', 0)
            if game_tb == 0:
                # totalBases가 없으면 hits, doubles, triples, homeRuns로 계산
                game_doubles = stat.get('doubles', 0)
                game_triples = stat.get('triples', 0)
                game_hr = stat.get('homeRuns', 0)
                # singles = hits - doubles - triples - homeRuns
                game_singles = game_h - game_doubles - game_triples - game_hr
                game_tb = game_singles + (game_doubles * 2) + (game_triples * 3) + (game_hr * 4)
            
            # 누적 계산
            cumulative_ab += game_ab
            cumulative_h += game_h
            cumulative_bb += game_bb
            cumulative_hbp += game_hbp
            cumulative_sf += game_sf
            cumulative_tb += game_tb
            
            # 누적 OPS 계산 (최소 1타석 이상일 때)
            if cumulative_ab > 0:
                # OBP = (H + BB + HBP) / (AB + BB + HBP + SF)
                denominator_obp = cumulative_ab + cumulative_bb + cumulative_hbp + cumulative_sf
                if denominator_obp > 0:
                    obp = (cumulative_h + cumulative_bb + cumulative_hbp) / denominator_obp
                else:
                    obp = 0
                
                # SLG = Total Bases / AB
                slg = cumulative_tb / cumulative_ab
                
                # OPS = OBP + SLG
                ops = obp + slg
                
                # AVG = H / AB
                avg = cumulative_h / cumulative_ab
                
                game_data.append({
                    'date': date,
                    'game_number': len(game_data) + 1,
                    'ops': ops,
                    'obp': obp,
                    'slg': slg,
                    'avg': avg,
                    'ab': cumulative_ab,
                    'h': cumulative_h
                })
        
        return pd.DataFrame(game_data) if game_data else None
    except Exception as e:
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

# 탭 생성
tab1, tab2, tab3 = st.tabs(["📊 통계 (Stats)", "🏆 누가 GOAT인가? (Who is the GOAT?)", "⚾️ 오타니 vs 시게노 고로"])

# 시즌 선택
season = st.sidebar.selectbox(
    '시즌 선택 (Select Season)',
    options=[2025, 2024, 2023],
    index=0
)

# ========== 탭 1: 통계 ==========
with tab1:
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

    # OPS 추이 그래프
    st.subheader('OPS 시즌 추이 (Season OPS Trend)')

    # 각 선수의 게임 로그 데이터 가져오기
    ops_data_list = []

    for player_id, info in PLAYERS.items():
        game_log_df = get_player_game_log(player_id, season)
        if game_log_df is not None and not game_log_df.empty:
            game_log_df['Player'] = info['name']
            ops_data_list.append(game_log_df)

    if ops_data_list:
        # 모든 선수 데이터 합치기
        all_ops_data = pd.concat(ops_data_list, ignore_index=True)
        
        # 날짜 형식 변환
        all_ops_data['date'] = pd.to_datetime(all_ops_data['date'], errors='coerce')
        all_ops_data = all_ops_data.sort_values('date')
        
        # 그래프 생성
        fig = go.Figure()
        
        # 각 선수별로 라인 추가
        for player_name in all_ops_data['Player'].unique():
            player_data = all_ops_data[all_ops_data['Player'] == player_name].copy()
            player_data = player_data.sort_values('date')
            
            fig.add_trace(go.Scatter(
                x=player_data['date'],
                y=player_data['ops'],
                mode='lines+markers',
                name=player_name,
                line=dict(width=2),
                marker=dict(size=4),
                hovertemplate=f'<b>{player_name}</b><br>' +
                             '날짜: %{x}<br>' +
                             'OPS: %{y:.3f}<br>' +
                             '<extra></extra>'
            ))
        
        # 그래프 레이아웃 설정
        fig.update_layout(
            title=f'{season}시즌 OPS 추이',
            xaxis_title='날짜 (Date)',
            yaxis_title='OPS',
            hovermode='x unified',
            height=500,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            template='plotly_white',
            xaxis=dict(
                showgrid=True,
                gridwidth=1,
                gridcolor='lightgray'
            ),
            yaxis=dict(
                showgrid=True,
                gridwidth=1,
                gridcolor='lightgray'
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 추가 정보 및 디버깅
        col1, col2 = st.columns(2)
        with col1:
            st.caption("💡 그래프는 시즌 시작부터 각 게임 후의 누적 OPS를 보여줍니다.")
        with col2:
            if len(all_ops_data) > 0:
                latest_ops = all_ops_data.groupby('Player')['ops'].last()
                st.caption(f"그래프 마지막 OPS: {', '.join([f'{name}: {ops:.3f}' for name, ops in latest_ops.items()])}")
        
        # 표의 OPS와 비교
        if not df.empty and 'OPS' in df.columns:
            ops_list = [f"{row['Name']}: {row['OPS']}" for _, row in df.iterrows()]
            st.caption(f"📊 표의 OPS: {', '.join(ops_list)}")
    else:
        st.info(f"{season}시즌 게임 로그 데이터를 불러올 수 없습니다. 시즌이 진행 중이거나 데이터가 아직 준비되지 않았을 수 있습니다.")

# ========== 탭 2: 누가 GOAT인가? ==========
with tab2:
    st.header("🏆 누가 GOAT인가? (Who is the GOAT?)")
    st.markdown("---")
    
    # 전문가 언급 데이터
    ohtani_quotes = [
        {
            "expert": "ESPN 분석가",
            "quote": "Shohei Ohtani는 야구 역사상 가장 독특한 선수입니다. 투수와 타자 모두에서 최고 수준의 실력을 보여주는 것은 전례가 없습니다.",
            "date": "2024"
        },
        {
            "expert": "MLB Network",
            "quote": "오타니는 현대 야구의 게임 체인저입니다. 그의 듀얼 위협 능력은 단순히 통계를 넘어서는 것입니다.",
            "date": "2024"
        },
        {
            "expert": "야구 전문가",
            "quote": "오타니 쇼헤이는 Babe Ruth 이후 가장 뛰어난 투타 겸업 선수입니다. 그의 WAR 수치는 이를 증명합니다.",
            "date": "2023"
        },
        {
            "expert": "The Athletic",
            "quote": "오타니의 2023 시즌은 야구 역사상 가장 위대한 개인 시즌 중 하나로 기록될 것입니다.",
            "date": "2023"
        },
        {
            "expert": "Baseball Prospectus",
            "quote": "오타니는 단순히 좋은 선수가 아닙니다. 그는 야구의 경계를 재정의하고 있습니다.",
            "date": "2024"
        }
    ]
    
    judge_quotes = [
        {
            "expert": "Yankees 구단 관계자",
            "quote": "Aaron Judge는 현대 야구에서 가장 위대한 타자 중 한 명입니다. 그의 파워와 일관성은 놀랍습니다.",
            "date": "2024"
        },
        {
            "expert": "MLB.com",
            "quote": "Judge의 2022 시즌 62홈런은 AL 역사상 최고 기록입니다. 그는 진정한 슈퍼스타입니다.",
            "date": "2022"
        },
        {
            "expert": "야구 분석가",
            "quote": "Judge는 단순히 홈런만 치는 것이 아닙니다. 그는 팀의 중심이며 리더십을 보여줍니다.",
            "date": "2024"
        },
        {
            "expert": "The New York Times",
            "quote": "Aaron Judge는 Yankees 역사상 가장 위대한 선수 중 한 명으로 자리잡고 있습니다.",
            "date": "2023"
        },
        {
            "expert": "Baseball Reference",
            "quote": "Judge의 OPS+는 그가 얼마나 뛰어난 타자인지를 보여줍니다. 그는 정상급 타자입니다.",
            "date": "2024"
        }
    ]
    
    # 두 컬럼으로 나누기
    col1, col2 = st.columns(2)
    
    # 왼쪽: 오타니
    with col1:
        st.subheader("🇯🇵 Shohei Ohtani")
        st.markdown("### 전문가들의 평가")
        
        for i, quote_data in enumerate(ohtani_quotes, 1):
            with st.container():
                st.markdown(f"""
                <div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 15px; border-left: 4px solid #FF6B6B;'>
                    <p style='font-weight: bold; color: #262730; margin-bottom: 8px;'>{quote_data['expert']} ({quote_data['date']})</p>
                    <p style='color: #4a5568; line-height: 1.6;'><em>"{quote_data['quote']}"</em></p>
                </div>
                """, unsafe_allow_html=True)
    
    # 오른쪽: 에런 저지
    with col2:
        st.subheader("🇺🇸 Aaron Judge")
        st.markdown("### 전문가들의 평가")
        
        for i, quote_data in enumerate(judge_quotes, 1):
            with st.container():
                st.markdown(f"""
                <div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 15px; border-left: 4px solid #4A90E2;'>
                    <p style='font-weight: bold; color: #262730; margin-bottom: 8px;'>{quote_data['expert']} ({quote_data['date']})</p>
                    <p style='color: #4a5568; line-height: 1.6;'><em>"{quote_data['quote']}"</em></p>
                </div>
                """, unsafe_allow_html=True)
    
    # 하단에 비교 요약
    st.markdown("---")
    st.subheader("📊 비교 요약")
    
    summary_col1, summary_col2 = st.columns(2)
    
    with summary_col1:
        st.markdown("""
        **Shohei Ohtani의 강점:**
        - 투수와 타자 모두에서 최고 수준
        - 역사상 유례없는 듀얼 위협
        - 높은 WAR 수치
        - 게임 체인저
        """)
    
    with summary_col2:
        st.markdown("""
        **Aaron Judge의 강점:**
        - 뛰어난 파워와 일관성
        - AL 홈런 기록 보유
        - 리더십과 팀 중심
        - 높은 OPS+
        """)

# ========== 탭 3: 오타니 vs 시게노 고로 ==========
with tab3:
    st.header("⚾️ 오타니 쇼헤이 vs 시게노 고로")
    st.markdown("### 🎌 만화보다 더 한 오타니 쇼헤이")
    st.markdown("---")
    
    # 사진과 기본 정보
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🇯🇵 Shohei Ohtani (오타니 쇼헤이)")
        # 오타니 사진 (base64 또는 파일 경로 시도)
        import os
        ohtani_image_loaded = False
        
        # 먼저 base64 이미지 시도
        if IMAGES_LOADED and OHTANI_IMAGE_BASE64:
            try:
                ohtani_img = base64.b64decode(OHTANI_IMAGE_BASE64)
                st.image(ohtani_img, width=300, caption="Shohei Ohtani - Los Angeles Dodgers")
                ohtani_image_loaded = True
            except:
                pass
        
        # base64가 없으면 파일 경로 시도
        if not ohtani_image_loaded:
            ohtani_paths = [
                "오타니 쇼헤이.gif",
                "./오타니 쇼헤이.gif",
                os.path.join(os.path.dirname(__file__), "오타니 쇼헤이.gif") if '__file__' in globals() else None,
                os.path.join(os.getcwd(), "오타니 쇼헤이.gif")
            ]
            for img_path in ohtani_paths:
                if img_path and os.path.exists(img_path):
                    try:
                        st.image(img_path, width=300, caption="Shohei Ohtani - Los Angeles Dodgers")
                        ohtani_image_loaded = True
                        break
                    except:
                        continue
        
        if not ohtani_image_loaded:
            st.warning("⚠️ 오타니 이미지를 불러올 수 없습니다.")
        
        st.markdown("""
        **1. 개요**
        - 일본 국적의 로스앤젤레스 다저스 소속 야구 선수
        - 포지션: 투타겸업 (Two-Way Player)
        - 신체: 193cm, 102kg
        - 생년월일: 1994년 7월 5일
        """)
    
    with col2:
        st.subheader("🎨 Goro Shigeno (시게노 고로)")
        # 시게노 고로 사진 (base64 또는 파일 경로 시도)
        import os
        sawamura_image_loaded = False
        
        # 먼저 base64 이미지 시도
        if IMAGES_LOADED and SAWAMURA_IMAGE_BASE64:
            try:
                sawamura_img = base64.b64decode(SAWAMURA_IMAGE_BASE64)
                st.image(sawamura_img, width=300, caption="Goro Shigeno - 메이저(MAJOR)")
                sawamura_image_loaded = True
            except:
                pass
        
        # base64가 없으면 파일 경로 시도
        if not sawamura_image_loaded:
            sawamura_paths = [
                "시게노 고로.jpeg",
                "./시게노 고로.jpeg",
                os.path.join(os.path.dirname(__file__), "시게노 고로.jpeg") if '__file__' in globals() else None,
                os.path.join(os.getcwd(), "시게노 고로.jpeg")
            ]
            for img_path in sawamura_paths:
                if img_path and os.path.exists(img_path):
                    try:
                        st.image(img_path, width=300, caption="Goro Shigeno - 메이저(MAJOR)")
                        sawamura_image_loaded = True
                        break
                    except:
                        continue
        
        if not sawamura_image_loaded:
            st.warning("⚠️ 시게노 고로 이미지를 불러올 수 없습니다.")
        
        st.markdown("""
        **만화 "메이저(MAJOR)"의 주인공**
        - 이름: 시게노 고로 (혼다 고로)
        - 생년월일: 11월 5일
        - 신체: 185cm, 85kg
        - 포지션: 투수 (메인), 외야수 (말년)
        - 투타: 좌투우타 (어깨 부상으로 좌투 전향)
        - 인디애나 호네츠에서 활약
        """)
    
    st.markdown("---")
    
    # 오타니 상세 정보
    st.subheader("📋 Shohei Ohtani 상세 정보")
    
    # 2. 상세
    with st.expander("2. 상세", expanded=True):
        st.markdown("""
        **2013년** 일본프로야구 홋카이도 닛폰햄 파이터즈 입단, 첫해부터 투타겸업으로 프로 커리어 시작
        
        **2016년** 퍼시픽 리그 MVP 수상, 팀을 일본시리즈 우승으로 이끔
        
        **2018년** 포스팅 시스템을 통해 로스앤젤레스 에인절스 입단, 메이저 리그 베이스볼 입성
        - 첫 시즌 아메리칸 리그 신인왕 수상
        - 2021년 만장일치 아메리칸 리그 MVP 수상
        - 2022년 15승-30홈런 달성과 규정 이닝/규정 타석 동시 충족
        - 2023년 10승-40홈런 달성, 아시아 출신 최초의 홈런왕
        - MLB 역사상 최초의 만장일치 MVP 4회 수상
        
        **2023년** 월드 베이스볼 클래식 출전, 대회 MVP 선정, 일본 야구 국가대표팀 우승 이끔
        
        **2023 시즌 종료 후** MLB 첫 FA 자격 획득, 로스앤젤레스 다저스로 이적
        - 2024 시즌: 야구 역사상 최초로 50-50 클럽 입성, 만장일치 내셔널 리그 MVP 수상
        - 최초의 만장일치 MVP 4회 수상, 최초의 지명타자 MVP 수상
        - 2번째 양대 리그 MVP 수상, 최초의 양대 리그 만장일치 MVP 수상
        - 데뷔 첫 포스트시즌 진출과 동시에 첫 월드 시리즈 우승 달성
        
        **2025 시즌** 4번째 만장일치 MVP, 청정 선수 중 역대 최다 수상
        - 메이저리그 최초 양대리그 멀티 MVP 수상
        - 커리어 최초 NLCS MVP와 2년 연속 월드시리즈 우승
        """)
    
    # 3. 선수 경력
    with st.expander("3. 선수 경력"):
        st.markdown("""
        **NPB (2013-2017)**
        - 홋카이도 닛폰햄 파이터즈
        - 2016년 퍼시픽 리그 MVP, 일본시리즈 우승
        
        **MLB (2018-현재)**
        - 로스앤젤레스 에인절스 (2018-2023)
        - 로스앤젤레스 다저스 (2024-현재)
        
        **국가대표**
        - 2012년 U-18 대표
        - 2015년 프리미어 12
        - 2023년 WBC (대회 MVP)
        - 2026년 WBC
        """)
    
    # 4. 수상 경력 및 보유 기록
    with st.expander("4. 수상 경력 및 보유 기록"):
        st.markdown("""
        **MVP 수상**
        - 2021, 2023년 AL MVP (만장일치)
        - 2024, 2025년 NL MVP (만장일치)
        - MLB 역사상 최초 만장일치 MVP 4회 수상
        - 미국 4대 프로 스포츠 사상 최초
        
        **기타 주요 수상**
        - 2018년 AL 신인왕
        - 2023년 WBC MVP
        - ESPY 어워드 최우수 스포츠 선수상 (21세기 야구선수 유일)
        - ESPY 최우수 MLB 선수 부문 5회 선정 (최다 수상)
        - AP통신 올해의 스포츠 선수 4회 수상
        - 타임지 세계에서 가장 영향력 있는 인물 100인 (2021)
        
        **보유 기록**
        - 최초의 50홈런-50도루 달성 (2024)
        - 15승-30홈런 달성 (2022)
        - 10승-40홈런 달성 (2023)
        - 규정 이닝/규정 타석 동시 충족 (2022)
        """)
    
    # 5. 플레이 스타일
    with st.expander("5. 플레이 스타일"):
        st.markdown("""
        **투타겸업**
        - 평상시에는 지명타자로 풀타임 출장
        - 6일 이상의 간격을 두고 선발 투수로 등판
        - 투수와 타자 모두에서 MLB 올스타 이상급의 성적
        
        **투수 스타일**
        - 강속구 투수
        - 다양한 구종 구사
        - 에이스급 활약
        
        **타자 스타일**
        - 파워 타자
        - 홈런과 도루 모두 가능한 5툴 플레이어
        """)
    
    # 6. 평가
    with st.expander("6. 평가"):
        st.markdown("""
        **역대 최고의 야구선수 논의**
        - 베이브 루스와 함께 한 시즌에 투수와 타자 모두 리그 최정상급 활약을 보여준 유이한 선수
        - 투타겸업을 수행하면서도 투타 모두 올스타급 성적을 내는 전무후무한 퍼포먼스
        - 보유하고 있는 툴의 개수로 따지면 야구 역사를 통틀어서 비견 대상이 전무
        
        **선구자 및 개척자**
        - 철저히 분업화된 현대 야구계에서 투타겸업이라는 불가능해 보였던 길을 유의미하게 개척
        - MLB 규정을 2번이나 세우고 '오타니 룰'이라는 자기 이름을 딴 규칙까지 만들게 함
        
        **아시아 리그 출신 선수들의 대우 개선**
        - 오타니의 등장은 MLB에서 아시아 리그 출신 선수가 더 좋은 대우를 받게 하는 기폭제
        - 스즈키 세이야, 요시다 마사타카, 야마모토 요시노부 등 일본인 메이저 리거
        - 이정후, 고우석, 김혜성 등 한국인 메이저 리거들도 더 나은 대우를 받게 됨
        """)
    
    # 7. 명예의 전당 입성 여부
    with st.expander("7. 명예의 전당 입성 여부"):
        st.markdown("""
        **입성 확정적**
        - 아직 커리어 중반을 지나는 31세임에도 미국 야구 명예의 전당 입성 자체는 이미 확정적
        - 9승 46홈런, 15승 34홈런, 10승 44홈런 등 투타겸업으로 쌓은 독보적인 임팩트
        - 역사상 최초의 50홈런-50도루 달성 등 최고점의 임팩트
        - 26세~29세에 쌓아올린 fWAR과 bWAR은 유색인종이 통합된 1947년 이래 메이저 리그 베이스볼 역대 1위
        - 21세기 청정 선수 중 4년 연속으로 fWAR, bWAR을 모두 8.0 이상을 기록한 유일한 선수
        
        **MVP 수상 횟수**
        - MVP 4회 이상 수상자는 오타니와 배리 본즈 단 2명 뿐
        - 본즈는 약쟁이라 입성에 실패, 오타니는 청정 선수라는 것이 제일 큰 메리트
        - 이미 오타니는 MVP 수상 횟수에서 역대 명예의 전당에 입성한 모든 야구 선수들을 추월
        - 명예의 전당 입성이 문제가 아니라, 만장일치로 명예의 전당에 들어가느냐의 문제
        """)
    
    # 7.1. WAR 산정 방식에 대한 논쟁
    with st.expander("7.1. WAR 산정 방식에 대한 논쟁"):
        st.markdown("""
        **현재 상황**
        - 현재까지의 연구 결과로는 투타겸업 WAR의 유의미한 상승을 기대하기는 힘들다는 것이 중론
        - 로스터 압축 효과의 경우에도 단일 시즌 WAR로 환산하면 대체 선수 수준의 WAR에 그침
        - 대부분의 주장은 '임팩트와 놀라움'을 스탯에 반영하기 위한 움직임에서 벗어나지 못함
        
        **논쟁의 핵심**
        - 현재의 WAR는 지명타자 오타니와 투수 오타니를 별개의 인물로 간주하여 WAR를 계산
        - 실제로는 한 사람이 2개의 역할을 소화하고 있는 것이기 때문에 WAR가 잘못 계산되고 있다는 지적
        - 투타겸업의 체력적 소모가 타 포지션에 비해 매우 크다는 이유로 추가 인정을 요구하는 의견
        
        **세이버메트리션들의 동의**
        - 거의 모든 세이버매트리션들이 동의하는 것은 오타니의 투타겸업으로 생기는 1명의 로스터 압축 효과가 팀 전체에 이득으로 작용한다는 것
        - 다만 이를 WAR로 다시 환산한다고 하더라도 대체 선수를 웃도는 수준일 것이기 때문에 큰 영향을 주지는 않을 것으로 보고 있음
        """)
    
    # 8. 인기
    with st.expander("8. 인기"):
        st.markdown("""
        - 일본인 남성 최초의 1,000만 팔로워 돌파
        - 전 세계 야구 선수 중 팔로워 수 전체 1위
        - 일본에서 인간의 형상을 한 신으로 추앙받는 수준의 인기
        - 전 세계적으로 가장 인기 있는 야구 선수 중 한 명
        """)
    
    # 9. 논란 및 사건 사고
    with st.expander("9. 논란 및 사건 사고"):
        st.markdown("""
        **9.1. 지급 유예 계약 논란**
        - 2023년 12월 10일, 로스앤젤레스 다저스와 10년 7억 달러 계약 (당시 역대 스포츠 최고액)
        - 계약 직후 총액의 97%에 달하는 6억 8천만 달러를 계약 기간이 끝난 이후 지급받는 지급 유예 계약
        - 실제로 오타니가 계약기간 동안 받는 금액은 10년 동안 2천만 달러, 즉 연봉으로는 2백만 달러만 받음
        - 나머지 금액은 계약기간 종료 후인 2034년부터 2043년까지 10년간 무이자로 분할해 지급
        - 이 계약은 구단측이 아닌 오타니 측에서 팀의 전력 강화를 위해 먼저 제안
        - 오타니 본인도 "다저스가 좋은 선수들과 계약을 체결해 더 좋은 팀이 되는데 도움이 될 거라 생각했다"고 언급
        - 다저스가 야마모토 요시노부 영입에 성공하는 등 팀 전력 강화에 기여
        
        **9.2. 통역사에 의한 횡령 피해**
        - 2024년 3월 20일, 오타니의 오랜 전속 통역사 미즈하라 잇페이가 불법 도박으로 생긴 거액의 빚을 갚기 위해 오타니의 돈을 횡령
        - 미국 연방수사국(FBI)이 오타니의 은행 계좌로부터 수 차례에 걸쳐 450만 달러에 달하는 돈이 송금된 사실을 확인
        - 오타니는 "야구를 비롯해 어떠한 스포츠에도 내기를 건 적이 없으며 며칠 전까지도 이런 일이 벌어지고 있다는 사실을 전혀 알지 못했다"고 밝힘
        - 2024년 4월 11일, 미국 연방 정부가 오타니는 어떤 불법 행위에도 연루되지 않았으며 이 사건에 있어 피해자라고 결론
        - 미즈하라는 합계로 약 1700만 달러 이상의 금액을 오타니의 계좌에서 편취
        - 2025년 2월 7일, 미국 연방지방법원이 미즈하라 잇페이에게 징역 4년 9개월과 246억을 배상하라고 명령
        """)
    
    # 10. 여담
    with st.expander("10. 여담"):
        st.markdown("""
        - 등장곡: "Pop-pop it's show time" (서울 시리즈부터 사용)
        - 반려견: 데코핀 (쿠이커혼제 믹스견, 수컷)
        - 결혼: 2024년 2월 29일 SNS를 통해 결혼 발표
        - 아내: 시미즈 카오루 (소꿉친구이자 아내)
        """)
    
    st.markdown("---")
    
    # 성적 비교
    st.subheader("📊 성적 비교 (Performance Comparison)")
    
    # 실제 오타니 데이터 가져오기
    ohtani_stats = get_player_stats(660271, season)
    
    # 시게노 고로는 만화 캐릭터이므로 가상의 데이터 사용 (메이저 만화 설정 기반)
    sawamura_stats = {
        'Name': 'Goro Shigeno (시게노 고로)',
        'FullName': '시게노 고로 (혼다 고로)',
        'Birthday': '11월 5일',
        'Height': '185cm',
        'Weight': '85kg',
        'Team': '인디애나 호네츠 (Indiana Hornets)',
        'Age': 20,  # MLB 진출 시 나이
        'Position': '투수 (좌투우타)',
        'Batting': '좌투우타',
        'G': 0,  # 투수이므로 타자 통계는 없음
        'AB': 0,
        'AVG': 0.0,
        'OBP': 0.0,
        'SLG': 0.0,
        'OPS': 0.0,
        'HR': 0,
        'RBI': 0,
        'WAR': None,
        # 투수 통계 (만화 설정 기반 - 인디애나 호네츠 전성기)
        'W': 18,  # 승
        'L': 5,   # 패
        'ERA': 2.15,  # 평균자책점
        'SO': 220,  # 삼진
        'IP': 200.0,  # 이닝
        'WHIP': 0.98,  # WHIP
        'MaxVelocity': '103마일 (165km/h)',  # 최고 구속
        'Pitches': ['자이로볼 (시그니처)', '포크볼'],  # 주요 구종
        'Specialty': '압도적인 구위로 타자를 찍어 누르는 스타일',
        'Career': {
            'Youth': '미후네 돌핀스 (우투 → 어깨 부상)',
            'MiddleSchool': '미후네 동중 (좌투로 재기)',
            'HighSchool': '세이슈 고교 (약체 팀 창단)',
            'MinorLeague': '멤피스 배츠 (AAA) - 클로저 → 선발',
            'WBC': '일본 대표팀 마무리 투수',
            'MLB': '인디애나 호네츠 - 월드시리즈 우승, 사이영상 후보',
            'Later': '요코하마 블루오션즈 - 타자로 복귀'
        },
        'Personality': '야구 바보, 불굴의 도전자, 정면 승부 고집',
        'Relationships': {
            'Rival': '사토 도시야 (평생의 라이벌이자 최고의 파트너)',
            'Motivation': '조 깁슨 (친아버지를 죽게 만든 투수)',
            'Wife': '시미즈 카오루 (소꿉친구이자 아내)'
        }
    }
    
    # 비교 테이블 생성
    comparison_data = {
        '항목': ['이름', '팀', '나이', '포지션', '특징'],
        '오타니 쇼헤이': [
            'Shohei Ohtani (오타니 쇼헤이)',
            'Los Angeles Dodgers',
            f"{ohtani_stats['Age'] if ohtani_stats else 30}세" if ohtani_stats else '30세',
            '투수/지명타자',
            '투타 겸업, MLB MVP'
        ],
        '시게노 고로': [
            'Goro Shigeno (시게노 고로)',
            '인디애나 호네츠',
            '20세',
            '투수 (좌투우타)',
            '자이로볼, 최고 구속 103마일, 불굴의 정신력'
        ]
    }
    
    comparison_df = pd.DataFrame(comparison_data)
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)
    
    # 타자 성적 비교 (오타니만)
    if ohtani_stats:
        st.markdown("---")
        st.subheader("🥎 타자 성적 (Batting Stats)")
        
        batting_col1, batting_col2 = st.columns(2)
        
        with batting_col1:
            st.markdown("#### 오타니 쇼헤이 (실제 성적)")
            if ohtani_stats:
                st.metric("경기 수", ohtani_stats.get('G', 0))
                st.metric("타석", ohtani_stats.get('AB', 0))
                # 숫자로 변환 후 포맷팅
                avg_val = pd.to_numeric(ohtani_stats.get('AVG', 0.0), errors='coerce')
                obp_val = pd.to_numeric(ohtani_stats.get('OBP', 0.0), errors='coerce')
                slg_val = pd.to_numeric(ohtani_stats.get('SLG', 0.0), errors='coerce')
                ops_val = pd.to_numeric(ohtani_stats.get('OPS', 0.0), errors='coerce')
                st.metric("타율 (AVG)", f"{avg_val:.3f}" if pd.notna(avg_val) else "0.000")
                st.metric("출루율 (OBP)", f"{obp_val:.3f}" if pd.notna(obp_val) else "0.000")
                st.metric("장타율 (SLG)", f"{slg_val:.3f}" if pd.notna(slg_val) else "0.000")
                st.metric("OPS", f"{ops_val:.3f}" if pd.notna(ops_val) else "0.000")
                st.metric("홈런 (HR)", ohtani_stats.get('HR', 0))
                st.metric("타점 (RBI)", ohtani_stats.get('RBI', 0))
        
        with batting_col2:
            st.markdown("#### 시게노 고로 (만화 설정)")
            st.info("""
            시게노 고로는 주로 투수로 활약하며,
            말년에는 타자로도 복귀했습니다.
            
            **만화 "메이저"에서의 특징:**
            - 좌투우타 (원래 우투였으나 어깨 부상으로 좌투 전향)
            - 자이로볼 (시그니처 구종)
            - 포크볼 (메이저리그 진출 후 유일한 변화구)
            - 최고 구속 103마일 (165km/h)
            - 압도적인 구위로 타자를 찍어 누르는 스타일
            - 어떤 위기 상황에서도 정면 승부(직구)를 고집
            - 약한 팀에서 강한 팀을 꺾는 것을 즐김 (자이언트 킬링)
            """)
    
    # 투수 성적 비교
    st.markdown("---")
    st.subheader("⚾️ 투수 성적 (Pitching Stats)")
    
    pitching_col1, pitching_col2 = st.columns(2)
    
    with pitching_col1:
        st.markdown("#### 오타니 쇼헤이 (실제 성적)")
        # 실제 투수 통계 가져오기
        ohtani_pitching = get_player_pitching_stats(660271, season)
        
        if ohtani_pitching and ohtani_pitching.get('W', 0) > 0:
            st.metric("승 (W)", ohtani_pitching.get('W', 0))
            st.metric("패 (L)", ohtani_pitching.get('L', 0))
            # 숫자로 변환 후 포맷팅
            era_val = pd.to_numeric(ohtani_pitching.get('ERA', 0.0), errors='coerce')
            ip_val = pd.to_numeric(ohtani_pitching.get('IP', 0.0), errors='coerce')
            whip_val = pd.to_numeric(ohtani_pitching.get('WHIP', 0.0), errors='coerce')
            st.metric("평균자책점 (ERA)", f"{era_val:.2f}" if pd.notna(era_val) else "0.00")
            st.metric("삼진 (SO)", ohtani_pitching.get('SO', 0))
            st.metric("이닝 (IP)", f"{ip_val:.1f}" if pd.notna(ip_val) else "0.0")
            st.metric("WHIP", f"{whip_val:.2f}" if pd.notna(whip_val) else "0.00")
        else:
            st.info(f"""
            {season}시즌에는 투수 기록이 없습니다.
            
            **과거 투수 성적 (2022년 기준):**
            - 승: 15승
            - 패: 9패
            - ERA: 2.33
            - 삼진: 219개
            - 이닝: 166.0
            - WHIP: 1.01
            """)
    
    with pitching_col2:
        st.markdown("#### 시게노 고로 (만화 설정 - 인디애나 호네츠 전성기)")
        st.metric("승 (W)", sawamura_stats['W'])
        st.metric("패 (L)", sawamura_stats['L'])
        st.metric("평균자책점 (ERA)", f"{sawamura_stats['ERA']:.2f}")
        st.metric("삼진 (SO)", sawamura_stats['SO'])
        st.metric("이닝 (IP)", f"{sawamura_stats['IP']:.1f}")
        st.metric("WHIP", f"{sawamura_stats['WHIP']:.2f}")
        st.metric("최고 구속", sawamura_stats.get('MaxVelocity', '103마일'))
        
        st.markdown("---")
        st.markdown("**주요 구종:**")
        for pitch in sawamura_stats.get('Pitches', []):
            st.markdown(f"- {pitch}")
        
        st.markdown("**플레이 스타일:**")
        st.markdown(f"- {sawamura_stats.get('Specialty', '')}")
        
        st.markdown("---")
        st.markdown("**커리어 타임라인:**")
        career = sawamura_stats.get('Career', {})
        st.markdown(f"- 유소년: {career.get('Youth', '')}")
        st.markdown(f"- 중학교: {career.get('MiddleSchool', '')}")
        st.markdown(f"- 고등학교: {career.get('HighSchool', '')}")
        st.markdown(f"- 마이너리그: {career.get('MinorLeague', '')}")
        st.markdown(f"- WBC: {career.get('WBC', '')}")
        st.markdown(f"- 메이저리그: {career.get('MLB', '')}")
        st.markdown(f"- 말년: {career.get('Later', '')}")
    
    # 결론 섹션
    st.markdown("---")
    st.subheader("💭 결론")
    
    conclusion_col1, conclusion_col2 = st.columns(2)
    
    with conclusion_col1:
        st.markdown("""
        ### 🏆 오타니 쇼헤이
        
        **현실의 슈퍼스타**
        - 실제 MLB에서 투타 겸업으로 활약
        - 2023년 AL MVP 수상
        - 투수와 타자 모두에서 최고 수준의 실력
        - 역사상 유례없는 듀얼 위협
        
        **"만화보다 더 한" 선수**
        - 만화 속 시게노 고로는 주로 투수로만 활약
        - 오타니는 투수와 타자 모두에서 최고 수준
        - 실제로 만화보다 더 놀라운 성과
        """)
    
    with conclusion_col2:
        st.markdown("""
        ### 🎨 시게노 고로
        
        **만화 "메이저(MAJOR)"의 주인공**
        - 시게노 고로 (혼다 고로)
        - 인디애나 호네츠에서 월드시리즈 우승
        - 좌투우타, 자이로볼 시그니처
        - 최고 구속 103마일 (165km/h)
        
        **캐릭터 특징**
        - "야구 바보": 야구 외에는 관심 없음
        - 불굴의 도전자: 약한 팀에서 강한 팀을 꺾는 것을 즐김
        - 정면 승부 고집: 어떤 위기 상황에서도 도망치지 않음
        - 압도적인 구위로 타자를 찍어 누르는 스타일
        - 입스(Yips) 극복, 어깨 부상 극복 등 역경 극복
        - 말년에는 타자로 복귀하여 선수 생활 연장
        """)
        
        st.markdown("**주요 인간관계:**")
        relationships = sawamura_stats.get('Relationships', {})
        st.markdown(f"- 라이벌/파트너: {relationships.get('Rival', '')}")
        st.markdown(f"- 동기부여: {relationships.get('Motivation', '')}")
        st.markdown(f"- 아내: {relationships.get('Wife', '')}")
    
    # 추가 정보
    st.markdown("---")
    st.info("""
    💡 **참고사항**: 
    - 오타니 쇼헤이는 실제 MLB 선수입니다.
    - 시게노 고로는 만화 "메이저(MAJOR)"의 가상 캐릭터입니다.
    - 시게노 고로는 인디애나 호네츠에서 월드시리즈 우승을 달성한 좌투우타 투수입니다.
    - 시게노 고로는 자이로볼을 시그니처로 하며, 최고 구속 103마일의 강속구 투수입니다.
    - 시게노 고로는 "야구 바보"이자 불굴의 도전자로서 약한 팀에서 강한 팀을 꺾는 것을 즐깁니다.
    - 오타니는 실제로 만화 속 캐릭터보다 더 놀라운 성과를 보여주고 있습니다.
    """)
