import io
import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ======================== 한글 폰트 CSS ========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
   font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# ======================== 데이터 로딩 함수 ========================
@st.cache_data
def load_env_csv(file):
    data = file.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            pass
    return pd.DataFrame()

@st.cache_data
def load_growth_csv(file):
    data = file.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            pass
    return pd.DataFrame()

# ======================== 열 이름 표준화 ========================
def std_cols(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename = {}
    for c in df.columns:
        k = c.lower().replace(" ", "")
        if k in ("time", "categories", "시간", "날짜", "datetime", "date"):
            rename[c] = "time"
        elif k in ("temperature", "온도"):
            rename[c] = "temperature"
        elif k in ("humidity", "습도"):
            rename[c] = "humidity"
        elif k == "ph":
            rename[c] = "ph"
        elif k == "ec":
            rename[c] = "ec"
        elif "생중량" in k:
            rename[c] = "생중량"
        elif "잎" in k:
            rename[c] = "잎 수"
        elif "지상부" in k and "길이" in k:
            rename[c] = "지상부 길이"
        elif "지하부" in k and "길이" in k:
            rename[c] = "지하부 길이"
        elif "지상부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지상부 질량"
        elif "지하부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지하부 질량"
        elif "개체" in k:
            rename[c] = "개체번호"
    df = df.rename(columns=rename)
    for c in df.columns:
        if c in ("time", "개체번호"):
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            num = pd.to_numeric(df[c].astype(str).str.replace(",", "").str.extract(r"(-?\d+\.?\d*)")[0], errors="coerce")
            if num.notna().mean() >= 0.5:
                df[c] = num
    if "생중량" not in df.columns and {"지상부 질량", "지하부 질량"} <= set(df.columns):
        df["생중량"] = df["지상부 질량"] + df["지하부 질량"]
    if "time" in df.columns:
        t = df["time"].astype(str).str.strip()
        parsed = pd.to_datetime(t, errors="coerce", format="mixed")
        bad = parsed.isna() & t.str.match(r"^\d{8}_\d{1,2}$")
        if bad.any():
            parts = t[bad].str.split("_", expand=True)
            parsed[bad] = pd.to_datetime(parts[0], format="%Y%m%d") + pd.to_timedelta(parts[1].astype(int), unit="h")
        df["time"] = parsed
    return df

# ======================== Plotly 공통 폰트 ========================
def set_fig_font(fig):
    fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))

# ======================== CSV 다운로드 헬퍼 ========================
def make_download_data(df):
    return df.to_csv(index=False).encode("utf-8-sig")

# ======================== 학교명 추출 ========================
def get_school_name(filename):
    if filename is None:
        return "우리 학교"
    base = os.path.basename(filename)
    name = base.replace(".csv", "").strip()
    # 앞쪽 학교명만 추출 (OO고 형태)
    import re
    m = re.match(r"^(.+?고)", name)
    if m:
        return m.group(1)
    return name

# ======================== 메인 앱 ========================
st.set_page_config(page_title="극지식물 생육 대시보드", layout="wide")
st.title("🌱 우리 학교 극지식물 개체별 생육 차이 분석")

# --- 사이드바 ---
st.sidebar.header("📁 데이터 업로드")
env_file = st.sidebar.file_uploader("환경 데이터 CSV", type="csv")
growth_file = st.sidebar.file_uploader("생육 결과 CSV", type="csv")

st.sidebar.markdown("---")
st.sidebar.header("📏 생육 측정 항목 선택")
available_metrics = ["잎 수", "지상부 길이", "지하부 길이", "생중량", "지상부 질량", "지하부 질량"]
selected_metrics = []
if growth_file is not None:
    raw_g = load_growth_csv(growth_file)
    g_df = std_cols(raw_g)
    available_metrics = [m for m in available_metrics if m in g_df.columns]
st.sidebar.multiselect("표시할 측정 항목", available_metrics, default=available_metrics[:3] if len(available_metrics) >= 3 else available_metrics, key="metric_sel")

st.sidebar.markdown("---")
school_name = get_school_name(env_file.name if env_file is not None else growth_file.name if growth_file is not None else None)
if school_name:
    st.sidebar.success(f"📌 {school_name} 데이터")

# --- 데이터 로딩 ---
env_df = pd.DataFrame()
growth_df = pd.DataFrame()
if env_file is not None:
    with st.spinner("환경 데이터 로딩 중..."):
        env_df = std_cols(load_env_csv(env_file))
if growth_file is not None:
    with st.spinner("생육 데이터 로딩 중..."):
        growth_df = std_cols(load_growth_csv(growth_file))

# --- 탭 ---
tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

# ======================== Tab 1: 실험 개요 ========================
with tab1:
    try:
        st.header("🔬 연구 배경 및 목적")
        st.markdown(f"""
**{school_name} 극지식물 생육 비교 분석**

극지에서 자라는 식물은 낮은 온도, 강한 바람, 적은 물 등 혹독한 환경에서 생존하기 위해 특별한 적응 방식을 갖고 있습니다. 
이 대시보드에서는 **같은 학교 같은 실험 조건에서 자란 극지식물 개체들 사이의 생육 차이**를 분석합니다.

**분석 목적**
- 개체별로 생중량(전체 무게)이 얼마나 차이가 나는지 확인
- 잎 수, 지상부 길이와 생중량 사이에 어떤 관계가 있는지 알아보기
- 잘 자란 개체(상위 25%)와 덜 자란 개체(하위 25%)를 비교하여 차이 파악

> 💡 **통계 용어 간단 설명**
> - **평균**: 여러 값을 더해 개수로 나눈 값, 대표적인 중심 경향
> - **표준편차**: 값들이 평균에서 얼마나 흩어져 있는지 나타내는 지표 (클수록 차이 큼)
> - **CV(변동계수)**: 표준편차를 평균으로 나눈 값, 단위가 다른 집단끼리 비교 가능
> - **상관계수**: 두 변수가 함께 변하는 정도 (-1 ~ 1, 1에 가까울수록 강한 양의 관계)
        """)

        st.markdown("---")
        st.header("📋 데이터 요약")

        # 카드 데이터 준비
        total_individuals = len(growth_df) if len(growth_df) > 0 else 0
        avg_temp = env_df["temperature"].dropna().mean() if "temperature" in env_df.columns and len(env_df) > 0 else None
        avg_humidity = env_df["humidity"].dropna().mean() if "humidity" in env_df.columns and len(env_df) > 0 else None
        avg_biomass = growth_df["생중량"].dropna().mean() if "생중량" in growth_df.columns and len(growth_df) > 0 else None

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("총 개체수", f"{total_individuals}개")
        col2.metric("평균 온도", f"{avg_temp:.1f}°C" if avg_temp is not None else "데이터 없음")
        col3.metric("평균 습도", f"{avg_humidity:.1f}%" if avg_humidity is not None else "데이터 없음")
        col4.metric("평균 생중량", f"{avg_biomass:.2f}g" if avg_biomass is not None else "데이터 없음")

        st.markdown("---")
        # 측정 기간
        if "time" in env_df.columns and len(env_df) > 0:
            time_min = env_df["time"].min()
            time_max = env_df["time"].max()
            st.info(f"📅 측정 기간: {time_min.strftime('%Y-%m-%d')} ~ {time_max.strftime('%Y-%m-%d')}")

        # 측정 항목
        env_cols_display = []
        for c in ["temperature", "humidity", "ph", "ec", "water_temp", "co2"]:
            if c in env_df.columns:
                label_map = {"temperature": "온도", "humidity": "습도", "ph": "pH", "ec": "EC", "water_temp": "수온", "co2": "CO₂"}
                env_cols_display.append(f"- {label_map[c]} ({c})")
        if env_cols_display:
            st.markdown(f"**환경 측정 항목:**\n" + "\n".join(env_cols_display))
        else:
            st.info("환경 데이터가 없습니다.")

        growth_cols_display = []
        for c in ["잎 수", "지상부 길이", "지하부 길이", "생중량", "지상부 질량", "지하부 질량"]:
            if c in growth_df.columns:
                growth_cols_display.append(f"- {c}")
        if growth_cols_display:
            st.markdown(f"**생육 측정 항목:**\n" + "\n".join(growth_cols_display))
        else:
            st.info("생육 데이터가 없습니다.")

    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ======================== Tab 2: 환경 데이터 ========================
with tab2:
    try:
        if len(env_df) == 0:
            st.info("🌡️ 환경 데이터 CSV를 업로드해 주세요. 사이드바에서 파일을 선택하면 이 탭의 내용을 볼 수 있습니다.")
        else:
            st.header("🌡️ 환경 데이터 요약")

            # 요약 표
            env_summary_cols = [c for c in ["temperature", "humidity", "ph", "ec", "water_temp", "co2"] if c in env_df.columns]
            if env_summary_cols:
                summary_data = []
                label_map = {"temperature": "온도(°C)", "humidity": "습도(%)", "ph": "pH", "ec": "EC(mS/cm)", "water_temp": "수온(°C)", "co2": "CO₂(ppm)"}
                for c in env_summary_cols:
                    vals = env_df[c].dropna()
                    if len(vals) >= 2:
                        summary_data.append({"항목": label_map.get(c, c), "평균": round(vals.mean(), 2), "최소": round(vals.min(), 2), "최대": round(vals.max(), 2), "측정 수": len(vals)})
                if summary_data:
                    st.dataframe(pd.DataFrame(summary_data), width="stretch")
                else:
                    st.info("유효한 숫자 데이터가 충분하지 않습니다.")
            else:
                st.info("표시할 환경 측정 열이 없습니다.")

            st.markdown("---")
            st.header("📈 날짜별 시계열")

            env_daily_cols = [c for c in ["temperature", "humidity", "ph", "ec"] if c in env_df.columns]
            if env_daily_cols:
                env_daily = env_df.copy()
                env_daily["date"] = env_daily["time"].dt.date
                daily = env_daily.groupby("date")[env_daily_cols].mean().reset_index()

                # 온도
                if "temperature" in daily.columns:
                    fig_temp = px.line(daily, x="date", y="temperature", title="일별 평균 온도 변화", markers=True)
                    fig_temp.update_yaxes(title="온도 (°C)")
                    set_fig_font(fig_temp)
                    st.plotly_chart(fig_temp, width="stretch")

                # 습도
                if "humidity" in daily.columns:
                    fig_hum = px.line(daily, x="date", y="humidity", title="일별 평균 습도 변화", markers=True)
                    fig_hum.update_yaxes(title="습도 (%)")
                    set_fig_font(fig_hum)
                    st.plotly_chart(fig_hum, width="stretch")

                # pH·EC (2개 서브플롯)
                if "ph" in daily.columns or "ec" in daily.columns:
                    ph_ec_cols = [c for c in ["ph", "ec"] if c in daily.columns]
                    fig_pe = make_subplots(rows=1, cols=len(ph_ec_cols), subplot_titles=["일별 평균 pH", "일별 평균 EC"])
                    for i, c in enumerate(ph_ec_cols):
                        fig_pe.add_trace(go.Scatter(x=daily["date"], y=daily[c], mode="lines", name=c), row=1, col=i+1)
                    fig_pe.update_xaxes(title_text="날짜")
                    if "ph" in daily.columns:
                        fig_pe.update_yaxes(title_text="pH", row=1, col=1)
                    if "ec" in daily.columns:
                        fig_pe.update_yaxes(title_text="EC (mS/cm)", row=1, col=2)
                    set_fig_font(fig_pe)
                    st.plotly_chart(fig_pe, width="stretch")
            else:
                st.info("표시할 환경 시계열 데이터가 없습니다.")

            with st.expander("📄 환경 데이터 원본 테이블"):
                st.dataframe(env_df, width="stretch")
                st.download_button("📥 환경 CSV 다운로드", make_download_data(env_df), "환경데이터.csv", "text/csv")

    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ======================== Tab 3: 생육 결과 ========================
with tab3:
    try:
        if len(growth_df) == 0:
            st.info("📊 생육 결과 CSV를 업로드해 주세요. 사이드바에서 파일을 선택하면 이 탭의 내용을 볼 수 있습니다.")
        else:
            st.header("🥇 핵심 결과")

            if "생중량" in growth_df.columns:
                clean_g = growth_df.dropna(subset=["생중량"])
                if len(clean_g) >= 2:
                    avg_b = clean_g["생중량"].mean()
                    max_idx = clean_g["생중량"].idxmax()
                    min_idx = clean_g["생중량"].idxmin()
                    max_row = clean_g.loc[max_idx]
                    min_row = clean_g.loc[min_idx]

                    c1, c2, c3 = st.columns(3)
                    c1.metric("평균 생중량", f"{avg_b:.2f}g")
                    c2.metric("최대 생중량 개체", f"개체 {max_row['개체번호']}: {max_row['생중량']:.2f}g")
                    c3.metric("최소 생중량 개체", f"개체 {min_row['개체번호']}: {min_row['생중량']:.2f}g")
                else:
                    st.info("생중량 데이터가 충분하지 않아 핵심 결과를 표시할 수 없습니다.")
            else:
                st.info("생중량 열이 없습니다.")

            st.markdown("---")
            st.header("📊 개체별 생육 비교")

            # 막대 그래프 함수
            def make_bar_chart(df, col, title, color):
                d = df.dropna(subset=[col])
                if len(d) < 2:
                    return None
                fig = px.bar(
                    d, x="개체번호", y=col,
                    title=title,
                    color=col,
                    color_continuous_scale=color,
                    labels={col: col}
                )
                fig.update_xaxes(title="개체번호")
                fig.update_yaxes(title=col)
                set_fig_font(fig)
                return fig

            viz_cols = [m for m in selected_metrics if m in growth_df.columns]
            if viz_cols:
                cols_n = min(2, len(viz_cols))
                rows_n = (len(viz_cols) + cols_n - 1) // cols_n
                for i in range(0, len(viz_cols), cols_n):
                    row = st.columns(cols_n)
                    for j in range(cols_n):
                        if i + j < len(viz_cols):
                            col_name = viz_cols[i + j]
                            fig = make_bar_chart(growth_df, col_name, f"개체별 평균 {col_name}", "Viridis")
                            if fig:
                                row[j].plotly_chart(fig, width="stretch")
                            else:
                                row[j].info(f"{col_name} 데이터가 충분하지 않습니다.")
            else:
                st.info("표시할 생육 측정 항목이 없습니다.")

            st.markdown("---")
            st.header("📦 생중량 분포")

            if "생중량" in growth_df.columns:
                clean_g = growth_df.dropna(subset=["생중량"])
                if len(clean_g) >= 3:
                    fig_box = px.box(
                        growth_df.dropna(subset=["생중량"]),
                        y="생중량", x="개체번호",
                        title="개체별 생중량 분포 (박스플롯)",
                        labels={"생중량": "생중량 (g)"}
                    )
                    set_fig_font(fig_box)
                    st.plotly_chart(fig_box, width="stretch")

                    # 바이올린 플롯 추가
                    fig_violin = px.violin(
                        growth_df.dropna(subset=["생중량"]),
                        y="생중량", x="개체번호",
                        title="개체별 생중량 분포 (바이올린 플롯)",
                        labels={"생중량": "생중량 (g)"}
                    )
                    set_fig_font(fig_violin)
                    st.plotly_chart(fig_violin, width="stretch")
                else:
                    st.info("생중량 데이터가 충분하지 않아 분포를 표시할 수 없습니다.")
            else:
                st.info("생중량 데이터가 없습니다.")

            st.markdown("---")
            st.header("🔗 상관관계 분석")

            if "생중량" in growth_df.columns:
                clean_g = growth_df.dropna(subset=["생중량"])
                if len(clean_g) >= 2:
                    # 상관관계 서브플롯
                    corr_targets = [m for m in ["잎 수", "지상부 길이"] if m in growth_df.columns]
                    if corr_targets:
                        fig_corr = make_subplots(rows=1, cols=len(corr_targets), subplot_titles=[f"{t} vs 생중량" for t in corr_targets])

                        for i, tgt in enumerate(corr_targets):
                            sub = clean_g.dropna(subset=[tgt])
                            if len(sub) >= 2:
                                r = sub["생중량"].corr(sub[tgt])
                                # 산점도
                                fig_corr.add_trace(go.Scatter(x=sub[tgt], y=sub["생중량"], mode="markers", name=tgt, marker=dict(size=6)), row=1, col=i+1)
                                # 추세선(np.polyfit)
                                z = np.polyfit(sub[tgt], sub["생중량"], 1)
                                p = np.poly1d(z)
                                x_line = np.linspace(sub[tgt].min(), sub[tgt].max(), 100)
                                fig_corr.add_trace(go.Scatter(x=x_line, y=p(x_line), mode="lines", name=f"추세선 (r={r:.2f})", line=dict(color="red", dash="dash")), row=1, col=i+1)
                                fig_corr.update_xaxes(title_text=tgt, row=1, col=i+1)
                                fig_corr.update_yaxes(title_text="생중량 (g)", row=1, col=i+1)

                        set_fig_font(fig_corr)
                        st.plotly_chart(fig_corr, width="stretch")

                        # 상관계수 표
                        corr_rows = []
                        for tgt in corr_targets:
                            sub = clean_g.dropna(subset=[tgt])
                            if len(sub) >= 2:
                                r = sub["생중량"].corr(sub[tgt])
                                corr_rows.append({"비교": f"{tgt} vs 생중량", "상관계수(r)": round(r, 3), "해석": "강한 양의 관계" if r > 0.7 else "중간 양의 관계" if r > 0.4 else "약한 관계" if r > 0 else "음의 관계"})
                        if corr_rows:
                            st.dataframe(pd.DataFrame(corr_rows), width="stretch")
                    else:
                        st.info("상관분석에 필요한 잎 수·지상부 길이 데이터가 없습니다.")
                else:
                    st.info("상관분석에 충분한 데이터가 없습니다.")
            else:
                st.info("생중량 데이터가 없어 상관분석을 할 수 없습니다.")

            st.markdown("---")
            st.header("🏆 생중량 상위 25% vs 하위 25% 비교")

            if "생중량" in growth_df.columns:
                clean_g = growth_df.dropna(subset=["생중량"])
                if len(clean_g) >= 4:
                    q75 = clean_g["생중량"].quantile(0.75)
                    q25 = clean_g["생중량"].quantile(0.25)
                    top = clean_g[clean_g["생중량"] >= q75]
                    bottom = clean_g[clean_g["생중량"] <= q25]

                    st.markdown(f"**상위 25% 기준: {q75:.2f}g 이상** ({len(top)}개체)")
                    st.markdown(f"**하위 25% 기준: {q25:.2f}g 이하** ({len(bottom)}개체)")

                    comp_cols = [c for c in ["잎 수", "지상부 길이", "지하부 길이"] if c in growth_df.columns]
                    if comp_cols:
                        comp_data = []
                        for c in comp_cols:
                            top_avg = top[c].dropna().mean()
                            bottom_avg = bottom[c].dropna().mean()
                            comp_data.append({"측정 항목": c, "상위 25% 평균": round(top_avg, 2), "하위 25% 평균": round(bottom_avg, 2), "차이": round(top_avg - bottom_avg, 2), "비율": f"{(top_avg/bottom_avg):.1f}x" if bottom_avg != 0 else "N/A"})
                        st.dataframe(pd.DataFrame(comp_data), width="stretch")
                    else:
                        st.info("비교할 생육 측정 항목이 없습니다.")
                else:
                    st.info("개체 수가 충분하지 않아 상위·하위 25% 비교를 할 수 없습니다.")
            else:
                st.info("생중량 데이터가 없습니다.")

            with st.expander("📄 생육 데이터 원본 테이블"):
                st.dataframe(growth_df, width="stretch")
                st.download_button("📥 생육 CSV 다운로드", make_download_data(growth_df), "생육결과데이터.csv", "text/csv")

    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ======================== 푸터 ========================
st.markdown("---")
st.caption(f"📍 {school_name} 극지식물 생육 분석 대시보드 | 데이터 기반 개체 비교 분석")
