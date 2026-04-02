"""
Stok Planlama Sistemi — Streamlit Arayüzü
Rolling Forecast with Chronos
"""

import os
import sys
import io
import tempfile

import streamlit as st

# --- Path & Working Directory Setup ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_DIR = os.path.join(BASE_DIR, "main")

# chronos_forecasts.json yolu cwd'ye bağlı; main/ altında olmalı
os.chdir(MAIN_DIR)

if MAIN_DIR not in sys.path:
    sys.path.insert(0, MAIN_DIR)

from orchestrator import StockPlanningOrchestrator  # noqa: E402

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402

# ---------------------------------------------------------------------------
# Page config — Streamlit'in ilk komutu olmalı
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Stok Planlama Sistemi",
    page_icon="📦",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Orchestrator cache — model_size veya use_col_forecast değişince yenisi kurulur
# ---------------------------------------------------------------------------
@st.cache_resource
def get_orchestrator(model_size: str, use_col_forecast: bool) -> StockPlanningOrchestrator:
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        orch = StockPlanningOrchestrator(
            chronos_model_size=model_size,
            use_column_forecast=use_col_forecast,
        )
    finally:
        sys.stdout = old
    return orch


# ---------------------------------------------------------------------------
# Session state başlangıç değerleri
# ---------------------------------------------------------------------------
_DEFAULTS: dict = {
    "material_loaded": False,
    "material_id": None,
    "tmp_path": None,
    "lead_time": 6,
    "loaded_model_key": None,   # hangi model ile veri yüklendi
    "weekly_decision": None,
    "weekly_log": "",
    "sim_decisions": None,
    "sim_log": "",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ---------------------------------------------------------------------------
# Yardımcı: log yakalayarak fonksiyon çalıştır
# ---------------------------------------------------------------------------
def run_with_log(fn, *args, **kwargs):
    """fn'i çalıştırır; stdout'u yakalar. (sonuç, log_str) döner."""
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        result = fn(*args, **kwargs)
    finally:
        sys.stdout = old
    return result, buf.getvalue()


# ---------------------------------------------------------------------------
# Başlık
# ---------------------------------------------------------------------------
st.title("📦 Stok Planlama Sistemi")
st.caption("Rolling Forecast with Chronos — Hibrit Tahmin Motoru")

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Yapılandırma")

    uploaded = st.file_uploader("Excel Dosyası (.xlsx / .xls)", type=["xlsx", "xls"])
    material_id_input = st.text_input("Material ID", value="M100F133RO")
    lead_time = st.number_input(
        "Lead Time (hafta)", min_value=1, max_value=52, value=6, step=1
    )
    model_size = st.selectbox(
        "Chronos Model Boyutu",
        options=["bolt-tiny", "bolt-mini", "bolt-small", "bolt-base",
                 "tiny", "mini", "small", "base", "large"],
        index=3,
    )
    use_col_forecast = st.checkbox(
        "Sütun Tahmini Kullan (use_column_forecast)", value=False
    )

    st.divider()
    load_btn = st.button("Veriyi Yükle", type="primary", use_container_width=True)

    if load_btn:
        if not uploaded:
            st.error("Lütfen bir Excel dosyası yükleyin.")
        elif not material_id_input.strip():
            st.error("Material ID boş olamaz.")
        else:
            # Geçici dosyaya yaz (file_uploader BytesIO verir)
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name

            orch = get_orchestrator(model_size, use_col_forecast)

            try:
                with st.spinner("Veri yükleniyor..."):
                    _, load_log = run_with_log(
                        orch.load_material_data,
                        filepath=tmp_path,
                        material_id=material_id_input.strip(),
                        lead_time_weeks=int(lead_time),
                    )
                st.session_state.material_loaded = True
                st.session_state.material_id = material_id_input.strip()
                st.session_state.tmp_path = tmp_path
                st.session_state.lead_time = int(lead_time)
                st.session_state.loaded_model_key = f"{model_size}_{use_col_forecast}"
                # Yeni veri yüklenince önceki sonuçları temizle
                st.session_state.weekly_decision = None
                st.session_state.sim_decisions = None
            except Exception as exc:
                st.error(f"Yükleme hatası: {exc}")
                st.session_state.material_loaded = False

    # Durum göstergesi
    if st.session_state.material_loaded:
        st.success(f"✅ Yüklendi: **{st.session_state.material_id}**")
        st.caption(
            f"Lead time: {st.session_state.lead_time} hafta"
        )
        current_key = f"{model_size}_{use_col_forecast}"
        if current_key != st.session_state.loaded_model_key:
            st.warning(
                "Model ayarları değişti. Yeni ayarlarla çalıştırmadan önce "
                "veriyi tekrar yükleyin."
            )
    else:
        st.info("Henüz veri yüklenmedi.")


# ---------------------------------------------------------------------------
# ANA SEKMELER
# ---------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(
    ["🗓️ Haftalık Planlama", "📈 Simülasyon", "📊 Hata Analizi"]
)

# ==========================================================================
# TAB 1 — Haftalık Planlama
# ==========================================================================
with tab1:
    st.subheader("Tek Hafta Planlama")

    if not st.session_state.material_loaded:
        st.info("Sol panelden veri yükleyin.")
    else:
        col_inp, _ = st.columns([1, 3])
        with col_inp:
            current_week = st.number_input(
                "Mevcut Hafta", min_value=1, max_value=200, value=3, step=1,
                key="weekly_week"
            )

        run_weekly = st.button("▶ Çalıştır", type="primary", key="btn_weekly")

        if run_weekly:
            orch = get_orchestrator(model_size, use_col_forecast)
            try:
                with st.spinner("Tahmin hesaplanıyor..."):
                    decision, log = run_with_log(
                        orch.run_weekly_planning,
                        st.session_state.material_id,
                        current_week=int(current_week),
                    )
                st.session_state.weekly_decision = decision
                st.session_state.weekly_log = log
            except Exception as exc:
                st.error(f"Hata: {exc}")
                st.session_state.weekly_decision = None

        if st.session_state.weekly_decision:
            d = st.session_state.weekly_decision
            st.success("Tamamlandı!")

            # --- Metrik kartları ---
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Kaynak", d.selected_source)
            m2.metric("Ham Tahmin", f"{d.raw_forecast:.2f}")
            m3.metric("Düzeltilmiş Tahmin", f"{d.bias_corrected_forecast:.2f}")
            if d.horizon_error:
                m4.metric("RMSE", f"{d.horizon_error.rmse:.2f}")
                m5.metric("Bias", f"{d.horizon_error.bias:.2f}")
            else:
                m4.metric("RMSE", "—")
                m5.metric("Bias", "—")

            # --- Detay expander ---
            with st.expander("Detaylar"):
                dc1, dc2 = st.columns(2)
                with dc1:
                    st.write(f"**Hedef Hafta:** {d.lead_time_week}")
                    if d.actual_target_week is not None:
                        actual = d.actual_target_week
                        st.write(f"**Gerçek Değer:** {actual:.2f}")
                        # % hata hesapla (pozitif = fazla tahmin, negatif = eksik tahmin)
                        if actual != 0:
                            raw_err_pct = (d.raw_forecast - actual) / actual * 100
                            cor_err_pct = (d.bias_corrected_forecast - actual) / actual * 100
                            raw_sign = "+" if raw_err_pct >= 0 else ""
                            cor_sign = "+" if cor_err_pct >= 0 else ""
                            st.write(f"**Ham Tahmin Hata %:** {raw_sign}{raw_err_pct:.1f}%")
                            st.write(f"**Düzeltilmiş Hata %:** {cor_sign}{cor_err_pct:.1f}%")
                        else:
                            st.write("**Hata %:** Gerçek değer sıfır, hesaplanamıyor")
                    else:
                        st.write("**Gerçek Değer:** Henüz bilinmiyor")
                        st.write("**Hata %:** —")
                with dc2:
                    if d.chronos_raw_forecast is not None:
                        st.write(f"**Chronos Ham:** {d.chronos_raw_forecast:.2f}")
                    if d.edi_raw_forecast is not None:
                        st.write(f"**EDI Ham:** {d.edi_raw_forecast:.2f}")
                    if d.horizon_error:
                        st.write(
                            f"**Örnek Sayısı:** {d.horizon_error.sample_count} | "
                            f"**Std:** {d.horizon_error.std:.2f}"
                        )

            if st.session_state.weekly_log:
                with st.expander("İşlem Logları"):
                    st.code(st.session_state.weekly_log, language="text")


# ==========================================================================
# TAB 2 — Simülasyon
# ==========================================================================
with tab2:
    st.subheader("Çok Haftalı Simülasyon")

    if not st.session_state.material_loaded:
        st.info("Sol panelden veri yükleyin.")
    else:
        sc1, sc2 = st.columns(2)
        with sc1:
            start_week = st.number_input(
                "Başlangıç Haftası", min_value=1, max_value=199, value=3, step=1
            )
        with sc2:
            end_week = st.number_input(
                "Bitiş Haftası", min_value=2, max_value=200, value=12, step=1
            )

        run_sim = st.button("▶ Simülasyon Çalıştır", type="primary", key="btn_sim")

        if run_sim:
            if int(end_week) <= int(start_week):
                st.error("Bitiş haftası başlangıç haftasından büyük olmalı.")
            else:
                orch = get_orchestrator(model_size, use_col_forecast)
                try:
                    with st.spinner(
                        f"Hafta {int(start_week)}–{int(end_week)} simülasyonu çalışıyor..."
                    ):
                        decisions, log = run_with_log(
                            orch.run_simulation,
                            st.session_state.material_id,
                            start_week=int(start_week),
                            end_week=int(end_week),
                        )
                    st.session_state.sim_decisions = decisions
                    st.session_state.sim_log = log
                except Exception as exc:
                    st.error(f"Hata: {exc}")
                    st.session_state.sim_decisions = None

        if st.session_state.sim_decisions:
            decisions = st.session_state.sim_decisions
            st.success(f"{len(decisions)} hafta tamamlandı!")

            # Tablo verisi
            rows = []
            for d in decisions:
                actual = d.actual_target_week
                if actual is not None and actual != 0:
                    raw_err_pct = round((d.raw_forecast - actual) / actual * 100, 1)
                    cor_err_pct = round((d.bias_corrected_forecast - actual) / actual * 100, 1)
                else:
                    raw_err_pct = None
                    cor_err_pct = None
                rows.append(
                    {
                        "Hafta": d.current_week,
                        "Hedef Hafta": d.lead_time_week,
                        "Kaynak": d.selected_source,
                        "Ham Tahmin": round(d.raw_forecast, 2),
                        "Düzeltilmiş Tahmin": round(d.bias_corrected_forecast, 2),
                        "Gerçek": round(actual, 2) if actual is not None else None,
                        "Ham Hata %": raw_err_pct,
                        "Düzeltilmiş Hata %": cor_err_pct,
                        "RMSE": (
                            round(d.horizon_error.rmse, 2) if d.horizon_error else None
                        ),
                        "Bias": (
                            round(d.horizon_error.bias, 2) if d.horizon_error else None
                        ),
                    }
                )
            df = pd.DataFrame(rows)

            # Özet metrikler
            orch = get_orchestrator(model_size, use_col_forecast)
            report = orch.get_summary_report(st.session_state.material_id, decisions)
            if report:
                r1, r2, r3 = st.columns(3)
                r1.metric(
                    "Dönem",
                    f"H{report['period']['start_week']} – H{report['period']['end_week']}",
                )
                r2.metric(
                    "Ort. Ham Tahmin",
                    f"{report['forecast']['avg_raw']:.2f}",
                )
                r3.metric(
                    "Ort. Düzeltilmiş",
                    f"{report['forecast']['avg_corrected']:.2f}",
                )

            # Plotly çizgi grafiği
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=df["Hafta"],
                    y=df["Ham Tahmin"],
                    name="Ham Tahmin",
                    mode="lines+markers",
                    line=dict(color="#2196F3", width=2),
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=df["Hafta"],
                    y=df["Düzeltilmiş Tahmin"],
                    name="Düzeltilmiş Tahmin",
                    mode="lines+markers",
                    line=dict(color="#4CAF50", width=2),
                )
            )
            if df["Gerçek"].notna().any():
                fig.add_trace(
                    go.Scatter(
                        x=df["Hafta"],
                        y=df["Gerçek"],
                        name="Gerçek",
                        mode="lines+markers",
                        line=dict(color="#FF5722", width=2, dash="dot"),
                    )
                )
            fig.update_layout(
                title="Tahmin vs Gerçek",
                xaxis_title="Hafta",
                yaxis_title="Miktar",
                hovermode="x unified",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                ),
                height=420,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Veri tablosu
            st.dataframe(df, use_container_width=True, hide_index=True)

            if st.session_state.sim_log:
                with st.expander("İşlem Logları"):
                    st.code(st.session_state.sim_log, language="text")


# ==========================================================================
# TAB 3 — Hata Analizi
# ==========================================================================
with tab3:
    st.subheader("Hata Analizi")

    if not st.session_state.sim_decisions:
        st.info("Önce **Simülasyon** sekmesinden simülasyon çalıştırın.")
    else:
        decisions = st.session_state.sim_decisions

        # Hata satırları
        horizon_rows = []
        for d in decisions:
            if d.horizon_error:
                horizon_rows.append(
                    {
                        "Hafta": d.current_week,
                        "Horizon": d.horizon_error.horizon,
                        "RMSE": d.horizon_error.rmse,
                        "Bias": d.horizon_error.bias,
                        "Std": d.horizon_error.std,
                        "Örnek Sayısı": d.horizon_error.sample_count,
                    }
                )

        if not horizon_rows:
            st.warning("Hata metrikleri hesaplanamadı — yeterli geçmiş veri olmayabilir.")
        else:
            df_h = pd.DataFrame(horizon_rows)

            # Horizon bazlı ortalamalar
            df_agg = (
                df_h.groupby("Horizon", as_index=False)
                .agg({"RMSE": "mean", "Bias": "mean", "Std": "mean"})
                .round(2)
            )

            # Bar chart
            fig_bar = go.Figure()
            fig_bar.add_trace(
                go.Bar(
                    x=df_agg["Horizon"],
                    y=df_agg["RMSE"],
                    name="Ort. RMSE",
                    marker_color="#2196F3",
                )
            )
            fig_bar.add_trace(
                go.Bar(
                    x=df_agg["Horizon"],
                    y=df_agg["Bias"].abs(),
                    name="|Ort. Bias|",
                    marker_color="#FF9800",
                )
            )
            fig_bar.update_layout(
                title="Horizon Bazlı Ortalama RMSE ve |Bias|",
                xaxis_title="Horizon (hafta)",
                yaxis_title="Hata",
                barmode="group",
                height=380,
            )
            st.plotly_chart(fig_bar, use_container_width=True)

            # Bias vs RMSE scatter (hafta bazlı)
            fig_scatter = go.Figure()
            fig_scatter.add_trace(
                go.Scatter(
                    x=df_h["Hafta"],
                    y=df_h["RMSE"],
                    name="RMSE",
                    mode="lines+markers",
                    line=dict(color="#2196F3"),
                )
            )
            fig_scatter.add_trace(
                go.Scatter(
                    x=df_h["Hafta"],
                    y=df_h["Bias"],
                    name="Bias",
                    mode="lines+markers",
                    line=dict(color="#FF9800"),
                )
            )
            fig_scatter.add_hline(
                y=0, line_dash="dash", line_color="gray", annotation_text="Bias=0"
            )
            fig_scatter.update_layout(
                title="Hafta Bazlı RMSE ve Bias",
                xaxis_title="Hafta",
                yaxis_title="Hata",
                hovermode="x unified",
                height=340,
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

            # Detay tablosu
            st.dataframe(df_h, use_container_width=True, hide_index=True)
