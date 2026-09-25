import { defineStore } from 'pinia'

// ─────────────────────────────────────────────────────────────────────────────
// SIGRET-AQP · Núcleo de estado
//
// Concentra la carga de datos y el recálculo del score. Toda la aritmética es
// vectorizada sobre arreglos planos: recalcular las 3,717 celdas al mover un
// control toma menos de 10 ms, de modo que la interfaz responde en tiempo real
// sin necesidad de ir al servidor.
// ─────────────────────────────────────────────────────────────────────────────

const BASE = '/data'

// ── Modelo de interacción espacial de Huff ───────────────────────────────────
// La cuota es la atractividad propia sobre la atractividad total del área de
// captación. OpenStreetMap registra muy pocas bodegas, así que la oferta
// informal se estima por densidad poblacional y se toma el máximo frente al
// conteo observado, para no contar dos veces el mismo competidor.
// Superficies asumidas: bodega tradicional 45 m², hard discount 175 m².
export const M2_BODEGA = 45
export const M2_MASS = 175
export const ALPHA = 1.0

export function huff(h, p, superficie = p.superficie) {
  const bodegas = Math.max(h.n_comp_osm_k1, h.pob_k1 / p.habPorBodega)
  const aNueva = superficie ** ALPHA
  const aRival = bodegas * M2_BODEGA ** ALPHA + h.mass_k1_2026 * M2_MASS ** ALPHA
  const cuota = aNueva + aRival > 0 ? aNueva / (aNueva + aRival) : 1
  const ventas = h.pob_k1 * p.gastoPerCapita * cuota
  const bruto = ventas * p.margen
  const payback = bruto > 0 ? p.inversion / bruto : null

  return { bodegas, cuota, ventas, bruto, payback, aNueva, aRival }
}

export const useSigret = defineStore('sigret', {
  state: () => ({
    ready: false,
    loading: false,
    error: null,

    cols: [],
    districts: [],
    rows: [],
    hex: [],
    mass: [],
    competencia: [],
    meta: null,

    // Parámetros del modelo de decisión
    p: {
      wPerfil: 0.344,      // peso del perfil aprendido vs demanda residual (AHP)
      penalizacion: 0.261, // castigo por proximidad de hard discount (AHP)
      radioAmenaza: 750,   // alcance en metros de ese castigo (mediana del panel)
      pobMinima: 1500,     // umbral de viabilidad
      habPorBodega: 120,   // densidad de oferta informal estimada
      gastoPerCapita: 180, // S/ mensuales en canal bodega
      inversion: 160000,   // S/ de inversión inicial
      margen: 0.22,        // margen bruto del canal
      superficie: 100,     // m² de sala de venta
    },

    filtros: {
      distritos: [],
      soloViables: true,
    },

    seleccion: null,
  }),

  getters: {
    // Aplica el score y los filtros activos
    hexesCalculados(state) {
      if (!state.ready)
        return []

      const { wPerfil, penalizacion, radioAmenaza, pobMinima } = state.p

      const wDemanda = 1 - wPerfil

      return state.hex.map(h => {
        const riesgo = Math.min(Math.max(1 - h.d_mass_2026 / radioAmenaza, 0), 1)
        const viable = h.pob_k1 >= pobMinima && h.mass_2026 === 0

        let score = 0
        if (viable) {
          score = (wPerfil * h.p_potencial + wDemanda * h.dem_res_n)
            * (1 - penalizacion * riesgo)
        }

        const e = huff(h, state.p)

        return {
          ...h,
          riesgo,
          viable,
          score,
          bodegas: e.bodegas,
          captura: e.ventas,
          margenMes: e.bruto,
          payback: e.payback,
        }
      })
    },

    hexesVisibles(state) {
      const ds = state.filtros.distritos
      let out = this.hexesCalculados

      if (ds.length && ds.length !== state.districts.length)
        out = out.filter(h => ds.includes(h.dist))
      if (state.filtros.soloViables)
        out = out.filter(h => h.viable)

      return out
    },

    ranking() {
      return [...this.hexesVisibles].sort((a, b) => b.score - a.score)
    },

    kpis(state) {
      const todos = this.hexesCalculados
      const viables = todos.filter(h => h.viable)
      const pob = todos.reduce((s, h) => s + h.pob_2017, 0)
      const cv = state.meta?.cv_espacial ?? []
      const ens = (state.meta?.backtesting ?? []).find(r => r.modelo.startsWith('Ensamble'))
      const tasaBaseCv = state.meta?.tasa_base_cv ?? 0
      const prAuc = cv.find(r => r.modelo === 'Ensamble')?.pr_auc ?? 0

      return {
        hexagonos: todos.length,
        viables: viables.length,
        poblacion: pob,
        competencia: state.mass.length + state.competencia.length,
        distritos: state.districts.length,
        rocAuc: Math.max(0, ...cv.map(r => r.roc_auc)),
        prAuc,
        tasaBaseCv,
        prSobreBase: tasaBaseCv ? prAuc / tasaBaseCv : 0,
        aciertos20: ens?.['acierto@20'] ?? 0,
        lift: ens?.['Lift@10%'] ?? 0,
      }
    },

    // Conteo del top-N agrupado por distrito, para el gráfico de barras
    topPorDistrito() {
      const top = this.ranking.slice(0, 50)
      const acc = {}

      top.forEach(h => { acc[h.dist] = (acc[h.dist] || 0) + 1 })

      return Object.entries(acc)
        .map(([d, n]) => ({ distrito: d, n }))
        .sort((a, b) => b.n - a.n)
    },

    seleccionado() {
      if (!this.seleccion)
        return null

      return this.hexesCalculados.find(h => h.h3 === this.seleccion) || null
    },
  },

  actions: {
    async cargar() {
      if (this.ready || this.loading)
        return

      this.loading = true
      this.error = null

      try {
        const [hx, ms, cp, mt] = await Promise.all([
          fetch(`${BASE}/hexes.json`).then(r => r.json()),
          fetch(`${BASE}/mass.json`).then(r => r.json()),
          fetch(`${BASE}/competencia.json`).then(r => r.json()),
          fetch(`${BASE}/meta.json`).then(r => r.json()),
        ])

        this.cols = hx.cols
        this.districts = hx.districts
        this.rows = hx.rows

        // El JSON viene como matriz para reducir peso: se hidrata a objetos
        const idx = {}

        hx.cols.forEach((c, i) => { idx[c] = i })

        this.hex = hx.rows.map(r => {
          const o = {}

          hx.cols.forEach((c, i) => { o[c] = r[i] })
          o.dist = hx.districts[r[idx.dist]]

          return o
        })

        this.mass = ms
        this.competencia = cp
        this.meta = mt
        this.filtros.distritos = [...hx.districts]
        this.ready = true
      }
      catch (e) {
        this.error = e?.message ?? 'No se pudieron cargar los datos'
        console.error('[sigret]', e)
      }
      finally {
        this.loading = false
      }
    },

    reset() {
      this.p = {
        wPerfil: 0.344,
        penalizacion: 0.261,
        radioAmenaza: 750,
        pobMinima: 1500,
        habPorBodega: 120,
        gastoPerCapita: 180,
        inversion: 160000,
        margen: 0.22,
        superficie: 100,
      }
    },

    seleccionar(h3) {
      this.seleccion = h3
    },
  },
})
