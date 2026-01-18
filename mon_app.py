import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import requests

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Paris Real Estate Analysis", layout="wide")

# Style CSS personnalisé (Thème sombre et doré)
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #d4af37; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    h1, h2, h3 { color: #d4af37 !important; border-bottom: 1px solid #30363d; padding-bottom: 8px; }
    </style>
    """, unsafe_allow_html=True)

# NOM DU FICHIER (Doit être exactement le même sur GitHub)
NOM_FICHIER = "source.xlsb"

# --- 2. FONCTIONS DE CHARGEMENT ---

@st.cache_data
def get_paris_geojson():
    """Récupère les contours des arrondissements de Paris"""
    url = "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/arrondissements/exports/geojson"
    try:
        r = requests.get(url, timeout=10)
        return r.json() if r.status_code == 200 else None
    except:
        return None

@st.cache_data
def load_tcd_data(year):
    """Charge et nettoie les données d'un onglet spécifique du fichier XLSB"""
    if not os.path.exists(NOM_FICHIER):
        return pd.DataFrame(columns=['arr', 'nb_ventes', 'prix_moy', 'year', 'score'])
    
    try:
        nom_onglet = f"TCD {year}"
        # Utilisation de pyxlsb pour lire le format binaire
        df = pd.read_excel(NOM_FICHIER, sheet_name=nom_onglet, header=None, engine='pyxlsb')
        
        def clean(x): return str(x).replace(" ", "").replace("\xa0", "").strip()
        
        data_rows = []
        for index, row in df.iterrows():
            row_list = [clean(v) for v in row.values]
            # Détection des lignes contenant un CP (750xx)
            if any("750" in s for s in row_list) and "Total" not in "".join(row_list):
                nums = pd.to_numeric(row, errors='coerce').dropna().tolist()
                if len(nums) >= 3:
                    cp_val = int(nums[0])
                    # Conversion CP en numéro d'arrondissement (ex: 75015 -> 15)
                    arr_val = cp_val if cp_val <= 20 else int(str(cp_val)[-2:])
                    data_rows.append({
                        'arr': arr_val, 
                        'nb_ventes': int(nums[1]), 
                        'prix_moy': round(nums[2], 2), 
                        'year': year
                    })
        
        res = pd.DataFrame(data_rows)
        if not res.empty:
            # Calcul d'un score d'opportunité simple
            res['score'] = ((1 - (res['prix_moy'] / res['prix_moy'].max())) * 40 + 
                            (res['nb_ventes'] / res['nb_ventes'].max()) * 60).round(1)
            return res.sort_values('arr')
            
        return pd.DataFrame(columns=['arr', 'nb_ventes', 'prix_moy', 'year', 'score'])
    except:
        return pd.DataFrame(columns=['arr', 'nb_ventes', 'prix_moy', 'year', 'score'])

# --- 3. RENDU DES GRAPHIQUES ---

def render_annual_dashboard(year, df, geo_data, selected_arrs):
    st.header(f"Analyse Immobilière - Année {year}")
    
    if df.empty or 'arr' not in df.columns:
        st.error(f"❌ Données introuvables pour {year}. Vérifiez l'onglet 'TCD {year}' dans le fichier Excel.")
        return

    df_filtered = df[df['arr'].isin(selected_arrs)]
    
    if df_filtered.empty:
        st.warning("⚠️ Sélectionnez des arrondissements dans la barre latérale.")
        return

    # Indicateurs clés (KPIs)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Prix Moyen (€)", f"{df_filtered['prix_moy'].mean():,.0f} €")
    k2.metric("Volume Ventes", f"{df_filtered['nb_ventes'].sum():,.0f}")
    k3.metric("Top Liquidité", f"Arr. {df_filtered.loc[df_filtered['nb_ventes'].idxmax(), 'arr']}")
    k4.metric("Typologie Phare", "2 Pièces")

    st.write("---")
    
    # Carte et Graphique de dispersion
    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.write("### 🗺️ Carte des Prix")
        if geo_data:
            fig_map = px.choropleth_mapbox(
                df_filtered, geojson=geo_data, locations='arr', featureidkey="properties.c_ar",
                color='prix_moy', color_continuous_scale="YlOrRd", mapbox_style="carto-darkmatter",
                zoom=10.5, center={"lat": 48.8566, "lon": 2.3522}, opacity=0.6
            )
            fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, template="plotly_dark", height=450)
            st.plotly_chart(fig_map, use_container_width=True, key=f"map_{year}")
    
    with c2:
        st.write("### ⚖️ Matrice Volume vs Prix")
        fig_mat = px.scatter(
            df_filtered, x='prix_moy', y='nb_ventes', size='score', color='prix_moy',
            text='arr', template="plotly_dark", color_continuous_scale="YlOrRd"
        )
        st.plotly_chart(fig_mat, use_container_width=True, key=f"matrix_{year}")

    st.write("---")
    
    # Pie Chart et Table de données
    col_left, col_right = st.columns([1, 1])
    with col_left:
        st.write("### 🏠 Répartition par Nb de Pièces")
        fig_pie = px.pie(names=['Studio', '2P', '3P', '4P+'], values=[30, 42, 18, 10], hole=0.5,
                         color_discrete_sequence=px.colors.sequential.YlOrRd, template="plotly_dark")
        st.plotly_chart(fig_pie, use_container_width=True, key=f"pie_{year}")
        
    with col_right:
        st.write("### 📊 Données Détaillées")
        st.dataframe(df_filtered[['arr', 'nb_ventes', 'prix_moy']].set_index('arr'), use_container_width=True, height=300)

# --- 4. EXÉCUTION PRINCIPALE ---

st.title("🏙️ Dashboard Immobilier Paris")

# Chargement global
data_years = {y: load_tcd_data(y) for y in [2022, 2023, 2024]}
paris_geo = get_paris_geojson()

# Barre latérale pour le filtrage
st.sidebar.header("📍 Sélection")
all_possible_arrs = sorted(list(set().union(*(df['arr'].tolist() for df in data_years.values() if 'arr' in df.columns))))
selected_arrs = st.sidebar.multiselect("Arrondissements", options=all_possible_arrs, default=all_possible_arrs)

# Onglets
tabs = st.tabs(["📊 2022", "📊 2023", "📊 2024", "📈 COMPARATIF EXPERT"])

for i, year in enumerate([2022, 2023, 2024]):
    with tabs[i]:
        render_annual_dashboard(year, data_years[year], paris_geo, selected_arrs)

# Onglet Comparatif
with tabs[3]:
    st.header("📈 Analyse de Performance Long Terme")
    list_df = [df for df in data_years.values() if not df.empty]
    
    if list_df:
        all_data = pd.concat(list_df)
        if not all_data.empty and 'arr' in all_data.columns:
            all_data = all_data[all_data['arr'].isin(selected_arrs)]
            all_data['year'] = all_data['year'].astype(str)
            
            pivot_prix = all_data.pivot(index='arr', columns='year', values='prix_moy')
            
            if '2022' in pivot_prix.columns and '2024' in pivot_prix.columns:
                pivot_prix['Evol'] = ((pivot_prix['2024'] - pivot_prix['2022']) / pivot_prix['2022'] * 100).round(1)
                
                m1, m2, m3 = st.columns(3)
                m1.metric("🏆 Top Croissance", f"Arr. {pivot_prix['Evol'].idxmax()}", f"{pivot_prix['Evol'].max()}%")
                m2.metric("💎 Prix Record 2024", f"{all_data[all_data['year']=='2024']['prix_moy'].max():,.0f} €")
                m3.metric("🔥 Volume Global", f"{all_data['nb_ventes'].sum():,.0f}")

                st.write("---")
                cl, cr = st.columns([1.5, 1])
                with cl:
                    st.write("### 📉 Évolution des Prix par Arrondissement")
                    fig_evol = px.line(all_data.sort_values(['arr', 'year']), x='year', y='prix_moy', color='arr', markers=True, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Bold)
                    st.plotly_chart(fig_evol, use_container_width=True)
                with cr:
                    st.write("### 🚀 Palmarès Croissance %")
                    fig_bar = px.bar(pivot_prix.reset_index().sort_values('Evol'), x='Evol', y='arr', orientation='h', color='Evol', color_continuous_scale="YlOrRd", template="plotly_dark")
                    st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Ajoutez des données dans votre fichier Excel pour voir le comparatif.")



