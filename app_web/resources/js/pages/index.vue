<script setup>
const router = useRouter()

onMounted(() => router.replace('/panel'))
</script>

<template>
  <div class="d-flex align-center justify-center" style="min-block-size: 60vh">
    <VProgressCircular indeterminate color="primary" size="42" />
  </div>
</template>
