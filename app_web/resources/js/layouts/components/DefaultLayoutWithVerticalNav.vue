<script setup>
import NavItems from '@/layouts/components/NavItems.vue'
import logo from '@images/logo.svg?raw'
import VerticalNavLayout from '@layouts/components/VerticalNavLayout.vue'
import Footer from '@/layouts/components/Footer.vue'
import NavbarThemeSwitcher from '@/layouts/components/NavbarThemeSwitcher.vue'
import { useSigret } from '@/stores/sigret'

const store = useSigret()
const route = useRoute()

const seccion = computed(() => route.meta?.titulo ?? '')

const fechaDatos = computed(() => {
  const f = store.meta?.generado
  if (!f)
    return null

  return new Date(`${f}T12:00:00`).toLocaleDateString('es-PE', { day: 'numeric', month: 'short', year: 'numeric' })
})
</script>

<template>
  <VerticalNavLayout>
    <!-- 👉 navbar -->
    <template #navbar="{ toggleVerticalOverlayNavActive }">
      <div class="d-flex h-100 align-center">
        <!-- 👉 Vertical nav toggle in overlay mode -->
        <IconBtn
          class="ms-n3 d-lg-none"
          @click="toggleVerticalOverlayNavActive(true)"
        >
          <VIcon icon="bx-menu" />
        </IconBtn>

        <div class="navbar-ctx d-flex align-center ms-lg-n2">
          <span class="navbar-proy">SIGRET-AQP</span>
          <span v-if="seccion" class="navbar-sep">/</span>
          <span class="navbar-seccion">{{ seccion }}</span>
        </div>

        <VSpacer />

        <VChip
          v-if="fechaDatos"
          size="small" variant="tonal" color="secondary" label
          class="me-2 d-none d-sm-flex"
          prepend-icon="bx-data"
        >
          Datos al {{ fechaDatos }}
        </VChip>

        <NavbarThemeSwitcher />
      </div>
    </template>

    <template #vertical-nav-header="{ toggleIsOverlayNavActive }">
      <RouterLink
        to="/"
        class="app-logo app-title-wrapper"
      >
        <!-- eslint-disable vue/no-v-html -->
        <div
          class="d-flex"
          v-html="logo"
        />
        <!-- eslint-enable -->

        <div class="app-brand">
          <h1 class="app-logo-title">SIGRET</h1>
          <span class="app-logo-sub">Arequipa</span>
        </div>
      </RouterLink>

      <IconBtn
        class="d-block d-lg-none"
        @click="toggleIsOverlayNavActive(false)"
      >
        <VIcon icon="bx-x" />
      </IconBtn>
    </template>

    <template #vertical-nav-content>
      <NavItems />
    </template>

    <!-- 👉 Pages -->
    <slot />

    <!-- 👉 Footer -->
    <template #footer>
      <Footer />
    </template>
  </VerticalNavLayout>
</template>

<style lang="scss" scoped>
.navbar-ctx {
  gap: 8px;
  font-size: 0.875rem;
}

.navbar-proy {
  color: rgb(var(--v-theme-primary));
  font-weight: 700;
  letter-spacing: 0.04em;
}

.navbar-sep {
  color: rgba(var(--v-theme-on-surface), 0.3);
}

.navbar-seccion {
  color: rgba(var(--v-theme-on-surface), 0.72);
  font-weight: 500;
}

.app-brand {
  display: flex;
  flex-direction: column;
  line-height: 1.05;
}

.app-logo-sub {
  color: rgba(var(--v-theme-on-surface), 52%);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}

.app-logo {
  display: flex;
  align-items: center;
  column-gap: 0.75rem;

  .app-logo-title {
    font-size: 1.25rem;
    font-weight: 500;
    line-height: 1.75rem;
    text-transform: uppercase;
  }
}
</style>
