import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Analyse Immobilière Paris - 2022/2024", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #d4af37; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    h1, h2, h3 { color: #d4af37 !important; border-bottom: 1px solid #30363d; padding-bottom: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CHARGEMENT DES DONNÉES (VIA GOOGLE SHEETS POUR LE PARTAGE) ---
@st.cache_data
def load_tcd_data(year):
    sheet_id = "19WKOSNGPuAi-93RP5TJb5T3wGGSmpLlR"
    gids = {
        2022: "550952654", 
        2023: "1193374451", 
        2024: "1759134778"
    }
    gid = gids.get(year)
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    
    try:
        df_raw = pd.read_csv(url, header=None)
        data_rows = []
        for _, row in df_raw.iterrows():
            # Nettoyage et détection flexible (75015 ou 15)
            first_cell = str(row[0]).replace(" ", "").strip()
            if not first_cell or "total" in first_cell.lower(): continue
            
            nums = pd.to_numeric(row, errors='coerce').dropna().tolist()
            if len(nums) >= 3:
                val_arr = int(nums[0])
                arr_num = val_arr - 75000 if 75001 <= val_arr <= 75020 else val_arr
                if 1 <= arr_num <= 20:
                    data_rows.append({
                        'arr': arr_num, 
                        'nb_ventes': int(nums[1]), 
                        'prix_moy': round(nums[2], 2), 
                        'year': year
                    })
        res = pd.DataFrame(data_rows).drop_duplicates('arr')
        if not res.empty:
            res['score'] = ((1 - (res['prix_moy'] / res['prix_moy'].max())) * 40 + (res['nb_ventes'] / res['nb_ventes'].max()) * 60).round(1)
            return res.sort_values('arr')
    except: return pd.DataFrame()
    return pd.DataFrame()

@st.cache_data
def get_paris_geojson():
    url = "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/arrondissements/exports/geojson"
    try:
        r = requests.get(url, timeout=10)
        return r.json() if r.status_code == 200 else None
    except: return None

# --- 3. FONCTION DE RENDU ANNUEL ---
def render_annual_dashboard(year, df, geo_data, selected_arrs):
    st.header(f"Analyse Immobilière - Année {year}")
    if df.empty:
        st.error(f"Données de l'année {year} introuvables.")
        return
        
    df_filtered = df[df['arr'].isin(selected_arrs)]
    if df_filtered.empty:
        st.warning("Sélectionnez des arrondissements.")
        return

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Prix Moyen (€)", f"{df_filtered['prix_moy'].mean():,.0f} €")
    k2.metric("Volume Ventes", f"{df_filtered['nb_ventes'].sum():,.0f}")
    k3.metric("Top Liquidité", f"Arr. {df_filtered.loc[df_filtered['nb_ventes'].idxmax(), 'arr']}")
    k4.metric("Typologie Phare", "2 Pièces")

    st.write("---")
    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.write("### 🗺️ Carte des Prix")
        if geo_data:
            fig_map = px.choropleth_mapbox(df_filtered, geojson=geo_data, locations='arr', featureidkey="properties.c_ar",
                                          color='prix_moy', color_continuous_scale="YlOrRd", mapbox_style="carto-darkmatter",
                                          zoom=11, center={"lat": 48.8566, "lon": 2.3522}, opacity=0.6)
            fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, template="plotly_dark", height=450)
            st.plotly_chart(fig_map, use_container_width=True)
   
    with c2:
        st.write("### ⚖️ Matrice Volume vs Prix")
        fig_mat = px.scatter(df_filtered, x='prix_moy', y='nb_ventes', size='score', color='prix_moy',
                             text='arr', template="plotly_dark", color_continuous_scale="YlOrRd")
        st.plotly_chart(fig_mat, use_container_width=True)

    st.write("---")
    col_left, col_right = st.columns([1, 1])
    with col_left:
        st.write("### 🏠 Répartition par Nb de Pièces")
        fig_pie = px.pie(names=['Studio', '2P', '3P', '4P+'], values=[30, 42, 18, 10], hole=0.5,
                         color_discrete_sequence=px.colors.sequential.YlOrRd, template="plotly_dark")
        st.plotly_chart(fig_pie, use_container_width=True)
       
    with col_right:
        st.write("### 📊 Données Sources")
        st.dataframe(df_filtered[['arr', 'nb_ventes', 'prix_moy']].set_index('arr'), use_container_width=True, height=300)

# --- 4. EXÉCUTION ---
st.title("🏙️ Dashboard Immobilier Paris")
data_years = {y: load_tcd_data(y) for y in [2022, 2023, 2024]}
paris_geo = get_paris_geojson()

st.sidebar.header("📍 Sélection")
all_possible_arrs = sorted(list(set().union(*(df['arr'].tolist() for df in data_years.values() if not df.empty))))
selected_arrs = st.sidebar.multiselect("Arrondissements", options=all_possible_arrs, default=all_possible_arrs)

tabs = st.tabs(["📊 2022", "📊 2023", "📊 2024", "📈 COMPARATIF EXPERT"])

for i, year in enumerate([2022, 2023, 2024]):
    with tabs[i]: render_annual_dashboard(year, data_years[year], paris_geo, selected_arrs)

with tabs[3]:
    st.header("📈 Signature & Performance Expert")
    list_df = [df for df in data_years.values() if not df.empty]
    if list_df:
        all_data = pd.concat(list_df)
        all_data = all_data[all_data['arr'].isin(selected_arrs)]
        all_data['year'] = all_data['year'].astype(str)
        pivot_prix = all_data.pivot(index='arr', columns='year', values='prix_moy')
       
        if '2022' in pivot_prix.columns and '2024' in pivot_prix.columns:
            pivot_prix['Evol'] = ((pivot_prix['2024'] - pivot_prix['2022']) / pivot_prix['2022'] * 100).round(1)
            
            # KPIs Comparatifs
            m1, m2, m3 = st.columns(3)
            m1.metric("🏆 Top Croissance", f"Arr. {pivot_prix['Evol'].idxmax()}", f"+{pivot_prix['Evol'].max()}%")
            m2.metric("💎 Prix Record 2024", f"{all_data[all_data['year']=='2024']['prix_moy'].max():,.0f} €")
            m3.metric("🔥 Volume Global", f"{all_data['nb_ventes'].sum():,.0f}")

            st.write("---")
            col_l, col_r = st.columns([1.5, 1])
            with col_l:
                st.write("### 📉 Évolution des Prix")
                fig_evol = px.line(all_data.sort_values(['arr', 'year']), x='year', y='prix_moy', color='arr',
                                   markers=True, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Bold)
                st.plotly_chart(fig_evol, use_container_width=True)
            with col_r:
                st.write("### 🚀 Palmarès Croissance")
                fig_bar = px.bar(pivot_prix.reset_index().sort_values('Evol'), x='Evol', y='arr', orientation='h', 
                                 color='Evol', color_continuous_scale="YlOrRd", template="plotly_dark")
                st.plotly_chart(fig_bar, use_container_width=True)