// ─────────────────────────────────────────────────────────────────────────────
// Compilación estática de la aplicación (sin Laravel ni PHP)
//
// Sirve para publicar la aplicación en un alojamiento estático gratuito, por
// ejemplo GitHub Pages (.github/workflows/sitio.yml), y que los participantes
// de la evaluación la abran desde su celular con un enlace. Usa la misma
// configuración que vite.config.js sin el plugin de Laravel, rutas con # y
// direcciones relativas, y arma index.html a partir de la vista Blade.
//
// Uso, desde app_web/:  pnpm build:sitio   →  dist-sitio/
// ─────────────────────────────────────────────────────────────────────────────
import { cpSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { defineConfig } from 'vite'
import base from './vite.config.js'

const SALIDA = 'dist-sitio'
const ENTRADA = 'resources/js/main.js'

function sitioEstatico() {
  return {
    name: 'sigret-sitio-estatico',
    apply: 'build',
    closeBundle() {
      const manifiesto = JSON.parse(readFileSync(join(SALIDA, '.vite', 'manifest.json'), 'utf-8'))
      const e = manifiesto[ENTRADA]
      const etiquetas = (e.css ?? []).map(c => `<link rel="stylesheet" href="./${c}" />`).join('')
        + `<script type="module" src="./${e.file}"></script>`

      const html = readFileSync('resources/views/application.blade.php', 'utf-8')
        .replace("{{ asset('favicon.svg') }}", './favicon.svg')
        .replace("{{ asset('loader.css') }}", './loader.css')
        .replace(/@vite\(\[[^\]]*\]\)/, etiquetas)

      writeFileSync(join(SALIDA, 'index.html'), html)
      for (const f of ['favicon.svg', 'loader.css', 'robots.txt'])
        cpSync(join('public', f), join(SALIDA, f))
      cpSync(join('public', 'data'), join(SALIDA, 'data'), { recursive: true })

      // GitHub Pages no publica archivos que empiezan con guion bajo si pasa por Jekyll
      writeFileSync(join(SALIDA, '.nojekyll'), '')
    },
  }
}

export default defineConfig({
  ...base,
  base: './',
  plugins: base.plugins
    .flat(Infinity)
    .filter(p => p && !String(p.name ?? '').startsWith('laravel'))
    .concat(sitioEstatico()),
  define: {
    ...base.define,
    'import.meta.env.VITE_DATOS': JSON.stringify('./data'),
    'import.meta.env.VITE_RUTAS': JSON.stringify('hash'),
  },
  publicDir: false,
  build: {
    ...base.build,
    outDir: SALIDA,
    emptyOutDir: true,
    manifest: true,
    rollupOptions: { input: ENTRADA },
  },
})
