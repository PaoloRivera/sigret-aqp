import { createRouter, createWebHashHistory, createWebHistory } from 'vue-router'
import { routes } from './routes'

const router = createRouter({
  // La compilación estática usa rutas con # para funcionar sin servidor propio
  history: import.meta.env.VITE_RUTAS === 'hash'
    ? createWebHashHistory()
    : createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default function (app) {
  app.use(router)
}
export { router }
