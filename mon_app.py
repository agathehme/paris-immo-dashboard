import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Analyse Immo Paris", layout="wide")

# Style pour rendre le dashboard élégant
st.markdown("""
    <style>
    .stMetric { background-color: #161b22; border: 1px solid #d4af37; border-radius: 10px; padding: 15px; }
    [data-testid="stMetricValue"] { color: #d4af37; font-weight: bold; }
    h1, h2 { color: #d4af37 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CHARGEMENT DES DONNÉES ---
@st.cache_data
def load_data():
    # REMPLACEZ 'source.xlsx' par le nom EXACT de votre fichier sur GitHub
    url = "https://github.com/agathehme/paris-immo-dashboard/raw/main/source.xlsx"
    
    try:
        # Lecture du fichier Excel
        all_sheets = pd.read_excel(url, sheet_name=None, engine='openpyxl')
        combined_data = []
        
        for name, df in all_sheets.items():
            if "TCD" in name:
                # Nettoyage : 3 premières colonnes
                temp_df = df.iloc[:, :3].copy()
                temp_df.columns = ['arr', 'ventes', 'prix']
                
                # Extraction année
                year_digits = "".join(filter(str.isdigit, name))
                temp_df['year'] = int(year_digits) if year_digits else 2024
                combined_data.append(temp_df)
        
        final_df = pd.concat(combined_data).dropna(subset=['arr'])
        final_df['arr'] = pd.to_numeric(final_df['arr'], errors='coerce')
        final_df = final_df.dropna(subset=['arr'])
        final_df['arr'] = final_df['arr'].apply(lambda x: int(x - 75000) if x > 75000 else int(x))
        return final_df[final_df['arr'].between(1, 20)]

    except Exception:
        # Données de secours si le fichier Excel ne peut pas être lu
        demo_data = []
        for y in [2022, 2023, 2024]:
            for a in range(1, 21):
                demo_data.append({'arr': a, 'ventes': 100 + a, 'prix': 10000 + (a*100), 'year': y})
        return pd.DataFrame(demo_data)

# --- 3. LOGIQUE DU DASHBOARD ---
st.title("🏙️ Dashboard Immobilier Paris (2022-2024)")

df = load_data()

# Sidebar
st.sidebar.header("Options d'affichage")
all_arrs = sorted(df['arr'].unique())
selected_arrs = st.sidebar.multiselect("Sélectionner les arrondissements", all_arrs, default=all_arrs)

# Filtrage
df_filtered = df[df['arr'].isin(selected_arrs)]

# Onglets
tab1, tab2 = st.tabs(["📊 Analyse Annuelle", "📈 Évolution Historique"])

with tab1:
    year_choice = st.selectbox("Choisir l'année", sorted(df['year'].unique(), reverse=True))
    df_year = df_filtered[df_filtered['year'] == year_choice]
    
    m1, m2, m3 = st.columns(3)
    if not df_year.empty:
        m1.metric("Prix Moyen", f"{df_year['prix'].mean():,.0f} €/m²")
        m2.metric("Total Ventes", f"{int(df_year['ventes'].sum()):,}")
        m3.metric("Top Arrondissement", f"N° {df_year.loc[df_year['prix'].idxmax(), 'arr']}")
        
        fig_bar = px.bar(df_year, x='arr', y='prix', color='prix',
                         title=f"Prix au m² par arrondissement en {year_choice}",
                         color_continuous_scale="YlOrRd", template="plotly_dark")
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Sélectionnez au moins un arrondissement.")

with tab2:
    st.subheader("Trajectoire des prix moyens")
    if not df_filtered.empty:
        df_evol = df_filtered.sort_values('year')
        df_evol['year'] = df_evol['year'].astype(str)
        fig_line = px.line(df_evol, x='year', y='prix', color='arr', markers=True,
                           title="Évolution du prix au m² (2022-2024)",
                           template="plotly_dark")
        st.plotly_chart(fig_line, use_container_width=True)

st.sidebar.info(f"Données chargées : {len(df)} lignes.")


