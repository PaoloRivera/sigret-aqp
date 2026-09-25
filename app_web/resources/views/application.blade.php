<!DOCTYPE html>
<html lang="es">

<head>
  <meta charset="UTF-8" />
  <link rel="icon" type="image/svg+xml" href="{{ asset('favicon.svg') }}" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="Sistema de soporte a la decisión para la localización de minimarkets independientes en Arequipa Metropolitana" />
  <title>SIGRET-AQP</title>
  <link rel="stylesheet" type="text/css" href="{{ asset('loader.css') }}" />
  @vite(['resources/js/main.js'])
</head>

<body>
  <div id="app">
    <div id="loading-bg">
      <div class="loading-logo">
        <svg width="60" height="64" viewBox="0 0 30 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M15 1.6 L26.3 8.2 L26.3 21.4 L15 28 L3.7 21.4 L3.7 8.2 Z"
            stroke="var(--initial-loader-color)" stroke-width="1.9" stroke-linejoin="round" opacity=".34" />
          <path d="M15 8.4 L21.1 12 L21.1 19.2 L15 22.8 L8.9 19.2 L8.9 12 Z"
            fill="var(--initial-loader-color)" opacity=".2" />
          <path d="M15 8.4 L21.1 12 L21.1 19.2 L15 22.8 L8.9 19.2 L8.9 12 Z"
            stroke="var(--initial-loader-color)" stroke-width="1.9" stroke-linejoin="round" />
          <circle cx="15" cy="15.6" r="2.6" fill="var(--initial-loader-color)" />
        </svg>
      </div>
      <div class="loading">
        <div class="effect-1 effects"></div>
        <div class="effect-2 effects"></div>
        <div class="effect-3 effects"></div>
      </div>
    </div>
  </div>

  <script>
    const loaderColor = localStorage.getItem('sneat-initial-loader-bg') || '#F4F6F7'
    const primaryColor = localStorage.getItem('sneat-initial-loader-color') || '#0E7C86'

    document.documentElement.style.setProperty('--initial-loader-bg', loaderColor)
    document.documentElement.style.setProperty('--initial-loader-color', primaryColor)
  </script>
</body>

</html>
