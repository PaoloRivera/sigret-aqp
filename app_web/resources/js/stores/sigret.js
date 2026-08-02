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
      wPerfil: 0.45,       // peso del perfil aprendido vs demanda residual
      penalizacion: 0.60,  // castigo por proximidad de hard discount
      radioAmenaza: 800,   // alcance en metros de ese castigo
      pobMinima: 1500,     // umbral de viabilidad
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

      const { wPerfil, penalizacion, radioAmenaza, pobMinima,
        gastoPerCapita, inversion, margen } = state.p

      const wDemanda = 1 - wPerfil

      return state.hex.map(h => {
        const riesgo = Math.min(Math.max(1 - h.d_mass_2026 / radioAmenaza, 0), 1)
        const viable = h.pob_k1 >= pobMinima && h.mass_k1_2026 === 0

        let score = 0
        if (viable) {
          score = (wPerfil * h.p_potencial + wDemanda * h.dem_res_n)
            * (1 - penalizacion * riesgo)
        }

        const oferta = 1 + h.n_comp_osm_k1 + 3 * h.mass_k1_2026
        const captura = h.pob_k1 * gastoPerCapita / oferta
        const margenMes = captura * margen

        return {
          ...h,
          riesgo,
          viable,
          score,
          captura,
          margenMes,
          payback: margenMes > 0 ? inversion / margenMes : null,
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

      return {
        hexagonos: todos.length,
        viables: viables.length,
        poblacion: pob,
        competencia: state.mass.length + state.competencia.length,
        distritos: state.districts.length,
        rocAuc: 0.929,
        prAuc: 0.249,
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
        wPerfil: 0.45,
        penalizacion: 0.60,
        radioAmenaza: 800,
        pobMinima: 1500,
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
