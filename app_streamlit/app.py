"""
app.py — SIGRET-AQP

Aplicacion Streamlit del sistema de soporte a la decision para la localizacion
de minimarkets en Arequipa Metropolitana: recalcula el score segun los
parametros elegidos y lo presenta en cuatro pestañas (mapa de oportunidad,
ranking descargable, simulador financiero tipo Huff y validacion del modelo).
"""
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

st.set_page_config(page_title="SIGRET-AQP", page_icon="🏪", layout="wide")

GASTO_MES = 180
INVERSION = 160_000
MARGEN = 0.22


@st.cache_data
def cargar():
    h = pd.read_parquet("data/hexes.parquet")
    m = pd.read_parquet("data/mass.parquet")
    c = pd.read_parquet("data/competencia.parquet")
    b = pd.read_parquet("data/backtesting.parquet")
    return h, m, c, b


hexes, mass, comp, bt = cargar()

st.sidebar.title("Parametros")
st.sidebar.caption("El score se recalcula al mover los controles")

w_pot = st.sidebar.slider(
    "Peso · perfil de sitio (modelo ML)", 0.0, 1.0, 0.45, 0.05,
    help="Cuanto pesa el patron aprendido de donde el retail moderno decide abrir")
w_dem = 1 - w_pot
st.sidebar.caption(f"Peso · demanda residual = **{w_dem:.2f}**")

pen_mass = st.sidebar.slider(
    "Penalizacion por cercania a Mass", 0.0, 1.0, 0.60, 0.05,
    help="Un hard discount cercano es una amenaza para un independiente")
radio_mass = st.sidebar.slider("Radio de amenaza (m)", 300, 1500, 800, 50)
pob_min = st.sidebar.slider("Poblacion minima a 500 m", 500, 6000, 1500, 250)

st.sidebar.divider()
dists = sorted(hexes["DIST"].dropna().unique())
sel_d = st.sidebar.multiselect("Distritos", dists, default=dists)
solo_v = st.sidebar.checkbox("Solo ubicaciones viables", True)

st.sidebar.divider()
capas = st.sidebar.multiselect(
    "Capas del mapa", ["Tiendas Mass", "Competencia OSM"], default=["Tiendas Mass"])
alto3d = st.sidebar.checkbox("Extrusion 3D", True)

d = hexes.copy()
d["riesgo"] = np.clip(1 - d["d_mass_2026"] / radio_mass, 0, 1)
d["viable_u"] = (d["pob_k1"] >= pob_min) & (d["mass_k1_2026"] == 0)
d["SCORE"] = ((w_pot * d["p_potencial"] + w_dem * d["dem_res_n"])
              * (1 - pen_mass * d["riesgo"]))
d.loc[~d["viable_u"], "SCORE"] = 0.0

d["captura_mes"] = d["pob_k1"] * GASTO_MES / (1 + d["n_comp_osm_k1"] + 3 * d["mass_k1_2026"])
d["margen_mes"] = d["captura_mes"] * MARGEN
d["payback_meses"] = np.where(d["margen_mes"] > 0, INVERSION / d["margen_mes"], np.nan)

vis = d[d["DIST"].isin(sel_d)]
if solo_v:
    vis = vis[vis["viable_u"]]

st.title("Localizacion optima de minimarkets · Arequipa Metropolitana")
st.caption("Malla H3 resolucion 9 (0.105 km²/celda) · Censo INEI 2017 · "
           "OpenStreetMap · SUNAT · red de tiendas Mass")

k = st.columns(5)
k[0].metric("Hexagonos analizados", f"{len(d):,}")
k[1].metric("Ubicaciones viables", f"{int(d['viable_u'].sum()):,}")
k[2].metric("Poblacion cubierta", f"{d['pob_2017'].sum()/1e6:.2f} M")
k[3].metric("Competencia moderna", f"{len(mass) + len(comp):,}")
k[4].metric("ROC-AUC (CV espacial)", "0.92")

t1, t2, t3, t4 = st.tabs(
    ["🗺️ Mapa de oportunidad", "🏆 Ranking", "🧮 Simulador", "📊 Validacion"])

with t1:
    if vis.empty:
        st.warning("Ningun hexagono cumple los filtros.")
    else:
        mx = max(vis["SCORE"].max(), 1e-9)
        vis = vis.assign(s=vis["SCORE"] / mx)
        vis["r"] = (40 + 215 * vis["s"]).astype(int)
        vis["g"] = (190 - 150 * vis["s"]).astype(int)
        vis["b"] = (120 - 90 * vis["s"]).astype(int)
        vis["elev"] = vis["s"] * 900 if alto3d else 0

        capas_deck = [pdk.Layer(
            "H3HexagonLayer", vis, get_hexagon="h3",
            get_fill_color="[r, g, b, 190]", get_elevation="elev",
            extruded=alto3d, pickable=True, auto_highlight=True,
            elevation_scale=1, coverage=0.96)]

        if "Tiendas Mass" in capas:
            capas_deck.append(pdk.Layer(
                "ScatterplotLayer", mass, get_position=["lng", "lat"],
                get_fill_color=[10, 40, 200, 235], get_radius=68,
                radius_min_pixels=4, pickable=True))
        if "Competencia OSM" in capas:
            capas_deck.append(pdk.Layer(
                "ScatterplotLayer", comp, get_position=["lon", "lat"],
                get_fill_color=[120, 120, 130, 200], get_radius=48,
                radius_min_pixels=3, pickable=True))

        st.pydeck_chart(pdk.Deck(
            layers=capas_deck,
            initial_view_state=pdk.ViewState(
                latitude=-16.40, longitude=-71.54, zoom=11.3,
                pitch=48 if alto3d else 0, bearing=0),
            map_style="light",
            tooltip={"html":
                "<b>{DIST}</b><hr style='margin:3px 0'>"
                "Score <b>{SCORE}</b><br>"
                "Poblacion 500 m: {pob_k1}<br>"
                "Competencia 500 m: {n_comp_osm_k1}<br>"
                "Mass mas cercano: {d_mass_2026} m<br>"
                "POIs de flujo: {n_poi_k1}",
                "style": {"fontSize": "12px"}}),
            height=560)
        st.caption("Verde = menor prioridad · Rojo/naranja = mayor prioridad. "
                   "Puntos azules = tiendas Mass. Altura = score.")

with t2:
    n = st.slider("Cuantas ubicaciones mostrar", 5, 100, 20, 5)
    top = vis.nlargest(n, "SCORE").reset_index(drop=True)
    top.index += 1
    show = top[["DIST", "pob_k1", "n_comp_osm_k1", "d_mass_2026", "n_poi_k1",
                "p_potencial", "SCORE", "captura_mes", "payback_meses", "lat", "lon"]]
    st.dataframe(
        show.rename(columns={
            "DIST": "Distrito", "pob_k1": "Pob. 500 m", "n_comp_osm_k1": "Compet.",
            "d_mass_2026": "d Mass (m)", "n_poi_k1": "POIs",
            "p_potencial": "Perfil ML", "SCORE": "Score",
            "captura_mes": "Captura S//mes", "payback_meses": "Payback (meses)"}),
        use_container_width=True,
        column_config={
            "Score": st.column_config.ProgressColumn(format="%.3f", min_value=0, max_value=1),
            "Captura S//mes": st.column_config.NumberColumn(format="S/ %.0f"),
            "Payback (meses)": st.column_config.NumberColumn(format="%.0f"),
            "Perfil ML": st.column_config.NumberColumn(format="%.2f"),
            "Pob. 500 m": st.column_config.NumberColumn(format="%.0f"),
            "d Mass (m)": st.column_config.NumberColumn(format="%.0f")})
    st.download_button("⬇ Descargar ranking (CSV)",
                       top.to_csv(index=False).encode("utf-8-sig"),
                       "ranking_ubicaciones.csv", "text/csv")

    st.subheader("Ubicaciones por distrito")
    st.bar_chart(top["DIST"].value_counts())

with t3:
    st.subheader("Simulador de escenario")
    st.caption("Modelo de interaccion espacial tipo Huff sobre la oferta existente")

    cand = vis.nlargest(60, "SCORE")
    if cand.empty:
        st.warning("Sin candidatos con los filtros actuales.")
    else:
        etiquetas = [f"#{i+1} · {r.DIST} · score {r.SCORE:.3f}"
                     for i, r in enumerate(cand.itertuples())]
        pick = st.selectbox("Ubicacion a evaluar", range(len(cand)),
                            format_func=lambda i: etiquetas[i])
        h = cand.iloc[pick]

        c1, c2 = st.columns(2)
        with c1:
            m2 = st.number_input("Superficie de venta (m²)", 40, 400, 100, 10)
            inv = st.number_input("Inversion (S/)", 50_000, 500_000, INVERSION, 10_000)
        with c2:
            gasto = st.number_input("Gasto per capita/mes (S/)", 80, 400, GASTO_MES, 10)
            marg = st.slider("Margen bruto", 0.10, 0.40, MARGEN, 0.01)

        A_new = m2 ** 1.0
        A_riv = (h["n_comp_osm_k1"] * 45 ** 1.0) + (h["mass_k1_2026"] * 175 ** 1.0)
        cuota = A_new / (A_new + A_riv) if (A_new + A_riv) > 0 else 1.0
        ventas = h["pob_k1"] * gasto * cuota
        margen = ventas * marg
        payback = inv / margen if margen > 0 else np.nan

        st.divider()
        m = st.columns(4)
        m[0].metric("Cuota de mercado", f"{100*cuota:.1f} %")
        m[1].metric("Ventas estimadas", f"S/ {ventas:,.0f}", "por mes")
        m[2].metric("Margen bruto", f"S/ {margen:,.0f}", "por mes")
        m[3].metric("Payback", f"{payback:.0f} meses" if margen > 0 else "—")

        st.divider()
        a, b = st.columns(2)
        with a:
            st.markdown("**Contexto de la ubicacion**")
            st.write(pd.DataFrame({"Indicador": [
                "Distrito", "Poblacion a 500 m", "Competencia a 500 m",
                "Tiendas Mass a 500 m", "Mass mas cercano", "POIs generadores",
                "Densidad de intersecciones", "Perfil ML", "Score final"],
                "Valor": [
                h["DIST"], f"{h['pob_k1']:,.0f} hab", f"{h['n_comp_osm_k1']:.0f}",
                f"{h['mass_k1_2026']:.0f}", f"{h['d_mass_2026']:,.0f} m",
                f"{h['n_poi_k1']:.0f}", f"{h['dens_intersec_km2']:.0f} /km²",
                f"{h['p_potencial']:.2f}", f"{h['SCORE']:.3f}"]}),
                hide_index=True, use_container_width=True)
        with b:
            st.markdown("**Alertas**")
            if h["d_mass_2026"] < 500:
                st.error(f"Mass a {h['d_mass_2026']:.0f} m. Competir en precio "
                         "contra un hard discount con marca propia es muy dificil.")
            elif h["d_mass_2026"] < 900:
                st.warning(f"Mass a {h['d_mass_2026']:.0f} m. Diferenciar por "
                           "surtido fresco, horario o credito de barrio.")
            else:
                st.success(f"Sin Mass en {h['d_mass_2026']:.0f} m a la redonda.")
            if h["n_comp_osm_k1"] >= 3:
                st.warning(f"{h['n_comp_osm_k1']:.0f} competidores registrados a 500 m.")
            if h["pob_k1"] < 2500:
                st.warning("Poblacion baja para el area de captacion.")
            if payback and payback > 36:
                st.error("Payback sobre 36 meses. Revisar inversion o formato.")

        st.pydeck_chart(pdk.Deck(
            layers=[
                pdk.Layer("H3HexagonLayer", pd.DataFrame([h]), get_hexagon="h3",
                          get_fill_color=[230, 60, 40, 170], extruded=False),
                pdk.Layer("ScatterplotLayer", mass, get_position=["lng", "lat"],
                          get_fill_color=[10, 40, 200, 220], get_radius=70,
                          radius_min_pixels=4),
                pdk.Layer("ScatterplotLayer", comp, get_position=["lon", "lat"],
                          get_fill_color=[120, 120, 130, 190], get_radius=50,
                          radius_min_pixels=3)],
            initial_view_state=pdk.ViewState(latitude=float(h["lat"]),
                                             longitude=float(h["lon"]), zoom=14.4),
            map_style="light"), height=330)

with t4:
    st.subheader("Validacion del modelo")
    st.markdown("""
**Diseno.** Sin acceso a datos de ventas, la variable objetivo es la *preferencia
revelada*: donde una cadena con equipo de geomarketing decidio efectivamente abrir.
El modelo se entrena con esas decisiones y se evalua contra aperturas posteriores
que no vio durante el entrenamiento.
""")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Validacion cruzada espacial** (bloques H3 r6, 5 folds)")
        st.dataframe(pd.DataFrame({
            "Modelo": ["Random Forest", "XGBoost", "Regresion logistica", "Ensamble"],
            "PR-AUC": [0.232, 0.247, 0.191, 0.249],
            "ROC-AUC": [0.929, 0.921, 0.876, 0.919]}),
            hide_index=True, use_container_width=True)
        st.caption("Tasa base 3.3 % → PR-AUC 0.249 equivale a 7.5x sobre el azar. "
                   "Los bloques espaciales evitan que hexagonos vecinos filtren "
                   "informacion entre entrenamiento y prueba.")
    with c2:
        st.markdown("**Backtesting temporal** (entrenar 2024 → predecir 2025-26)")
        st.dataframe(bt[["modelo", "PR_AUC", "ROC_AUC", "P@20", "Lift@10%"]].round(3),
                     hide_index=True, use_container_width=True)
        st.caption("39 aperturas reales entre 1 259 candidatos. El ensamble ubico "
                   "5 de ellas en su Top-20.")

    st.divider()
    st.markdown("**Variables mas influyentes**")
    st.bar_chart(pd.Series({
        "Poblacion del hexagono": 0.135, "Densidad poblacional": 0.128,
        "POIs de flujo (500 m)": 0.125, "Poblacion 500 m": 0.075,
        "Colegios (500 m)": 0.066, "Poblacion anillo externo": 0.064,
        "N.º de manzanas": 0.049, "Poblacion 1 km": 0.043,
        "Vias principales (m)": 0.036, "Densidad intersecciones": 0.034}))

    st.divider()
    st.markdown("""
**Limitaciones declaradas**

1. **Cobertura de la bodega tradicional.** El padron SUNAT no incluye el CIIU y la
   mayoria de bodegueros se inscriben como persona natural con su nombre propio, de
   modo que no son identificables por razon social. La competencia modelada es el
   retail moderno organizado; la bodega tradicional entra como contexto via densidad
   poblacional.
2. **Distancias euclidianas.** Las metricas de proximidad no usan la red peatonal.
   En un relieve como el del cono norte esto subestima la friccion real.
3. **Base censal 2017.** La poblacion proviene del ultimo censo con desagregacion a
   manzana disponible; las areas de expansion reciente estan subrepresentadas.
4. **Proxy de exito.** "Sigue operando" no equivale a "es rentable". Sin datos de
   ventas la validacion mide acierto locacional, no desempeno financiero.
""")

st.divider()
st.caption("Fuentes · Censo Nacional INEI 2017 (manzana) · OpenStreetMap (ODbL) · "
           "Padron Reducido RUC SUNAT · localizador publico Tiendas Mass · "
           "Internet Archive. Trabajo academico sin vinculo con las empresas citadas.")
