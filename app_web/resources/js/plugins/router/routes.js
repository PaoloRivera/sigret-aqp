export const routes = [
  { path: '/', redirect: '/panel' },
  {
    path: '/',
    component: () => import('@/layouts/default.vue'),
    children: [
      {
        path: 'panel',
        name: 'panel',
        component: () => import('@/pages/panel.vue'),
        meta: { titulo: 'Resumen' },
      },
      {
        path: 'mapa',
        name: 'mapa',
        component: () => import('@/pages/mapa.vue'),
        meta: { titulo: 'Mapa de oportunidad' },
      },
      {
        path: 'ranking',
        name: 'ranking',
        component: () => import('@/pages/ranking.vue'),
        meta: { titulo: 'Ranking de ubicaciones' },
      },
      {
        path: 'simulador',
        name: 'simulador',
        component: () => import('@/pages/simulador.vue'),
        meta: { titulo: 'Simulador de apertura' },
      },
      {
        path: 'modelo',
        name: 'modelo',
        component: () => import('@/pages/modelo.vue'),
        meta: { titulo: 'Validación del modelo' },
      },
      {
        path: 'fuentes',
        name: 'fuentes',
        component: () => import('@/pages/fuentes.vue'),
        meta: { titulo: 'Fuentes de datos' },
      },
    ],
  },
  {
    path: '/',
    component: () => import('@/layouts/blank.vue'),
    children: [
      {
        path: 'comerciante',
        name: 'comerciante',
        component: () => import('@/pages/comerciante.vue'),
        meta: { titulo: 'Para comerciantes' },
      },
      {
        path: 'comerciante/ficha/:h3',
        name: 'ficha',
        component: () => import('@/pages/ficha.vue'),
        meta: { titulo: 'Ficha de ubicación' },
      },
      {
        path: '/:pathMatch(.*)*',
        component: () => import('@/pages/[...error].vue'),
      },
    ],
  },
]
