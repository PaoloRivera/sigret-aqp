// ─────────────────────────────────────────────────────────────────────────────
// SIGRET-AQP · Modo comerciante
//
// Textos en lenguaje simple para el propietario de minimarket. Las cifras son
// las mismas de la versión técnica (store y modelo de Huff); aquí solo cambia
// cómo se dicen. Lo usan la página del modo comerciante y su ficha imprimible.
// ─────────────────────────────────────────────────────────────────────────────
import { PARAMS_PANEL, UMBRAL_ENTRADA_CADENA, huff } from '@/stores/sigret'

const NOMBRES = { JLBR: 'José Luis Bustamante y Rivero' }

export function nombreDistrito(d) {
  if (!d)
    return ''
  if (NOMBRES[d])
    return NOMBRES[d]

  return d.toLowerCase().replace(/(^|\s)\S/g, c => c.toUpperCase())
}

const fEntero = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 0 })
const fSoles = new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN', maximumFractionDigits: 0 })

export const entero = n => fEntero.format(Math.round(n))

// Montos redondeados a la centena: son estimaciones, no cifras exactas
export const soles = n => fSoles.format(Math.round(n / 100) * 100)

export function distancia(m) {
  if (m < 1000)
    return `${entero(Math.round(m / 10) * 10)} m`

  return `${(m / 1000).toFixed(1).replace('.', ',')} km`
}

// Nivel de oportunidad según la parte de zonas viables que la superan
export function nivel(h) {
  if (h.superado < 0.05)
    return { texto: 'Muy buena', color: 'success', detalle: 'está entre el 5 % mejor de las zonas evaluadas' }
  if (h.superado < 0.20)
    return { texto: 'Buena', color: 'primary', detalle: 'está entre el 20 % mejor de las zonas evaluadas' }
  if (h.superado < 0.50)
    return { texto: 'Regular', color: 'warning', detalle: 'está en la mitad mejor de las zonas evaluadas' }

  return { texto: 'Baja', color: 'secondary', detalle: 'está en la mitad de abajo de las zonas evaluadas' }
}

export function cadena(h) {
  const d = h.d_mass_2026
  if (d < 500)
    return { color: 'error', texto: `Hay una tienda de descuento a ${distancia(d)}` }
  if (d < 900)
    return { color: 'warning', texto: `La tienda de descuento más cercana está a ${distancia(d)}` }

  return { color: 'success', texto: `La tienda de descuento más cercana está a ${distancia(d)}` }
}

export const enlaceMapa = h => `https://www.google.com/maps/search/?api=1&query=${h.lat},${h.lon}`

// Números del negocio con los supuestos que elige el comerciante.
// gastos: gastos fijos al mes (alquiler, sueldos, servicios); opcional.
export function numeros(h, { inversion, superficie, margen, gastos }, hCampo = null) {
  const p = {
    ...PARAMS_PANEL,
    hCampo,
    habPorBodega: hCampo ?? PARAMS_PANEL.habPorBodega,
    inversion,
    superficie,
    margen: margen / 100,
  }
  const e = huff(h, p)
  const neto = gastos ? e.bruto - gastos : null
  const recupera = gastos
    ? (neto > 0 ? inversion / neto : null)
    : e.payback

  return { ventas: e.ventas, bruto: e.bruto, neto, recupera, bodegas: e.bodegas, conGastos: !!gastos }
}

// Avisos en lenguaje simple, del más grave al más leve
export function avisos(h, n) {
  const a = []
  const d = h.d_mass_2026

  if (d < 500) {
    a.push({
      t: 'error',
      txt: `Hay una tienda de descuento a ${distancia(d)}. Competir en precio con ella es muy difícil para una tienda independiente.`,
    })
  }
  else if (d < 900) {
    a.push({
      t: 'warning',
      txt: `Hay una tienda de descuento a ${distancia(d)}. Conviene diferenciarse: productos frescos, horario más largo o fiado a clientes conocidos.`,
    })
  }
  if (h.p_potencial >= UMBRAL_ENTRADA_CADENA) {
    a.push({
      t: 'warning',
      txt: 'Zonas como esta atraen a las cadenas: de las 50 mejores zonas de 2024, en 7 de cada 10 abrió una tienda de descuento a menos de 750 m en los dos años siguientes.',
    })
  }
  if (h.pob_k1 < 2500) {
    a.push({
      t: 'warning',
      txt: 'Vive poca gente alrededor. Antes de decidir, mira si pasa mucha gente por la calle: paraderos, colegios o mercados.',
    })
  }
  if (n.conGastos && n.neto <= 0) {
    a.push({ t: 'error', txt: 'Con esos gastos fijos, lo que te queda de las ventas no alcanza para cubrirlos.' })
  }
  else if (n.recupera && n.recupera > 36) {
    a.push({ t: 'error', txt: 'Con estos números tardarías más de 3 años en recuperar lo que inviertes.' })
  }
  if (!a.length)
    a.push({ t: 'success', txt: 'No encontramos alertas para esta zona con los datos disponibles.' })

  return a
}

export const TAMANOS = [
  { m2: 60, texto: 'Pequeña', detalle: '60 m²' },
  { m2: 100, texto: 'Mediana', detalle: '100 m²' },
  { m2: 150, texto: 'Grande', detalle: '150 m²' },
]

export const ANTES_DE_DECIDIR = [
  'Visita la zona en la mañana, al mediodía y en la noche, y mira cuánta gente pasa.',
  'Pregunta cuánto cuesta el alquiler de un local de ese tamaño.',
  'Cuenta las bodegas y tiendas de las cuadras de alrededor.',
  'Pregunta a dos o tres vecinos dónde compran y qué les falta.',
]
