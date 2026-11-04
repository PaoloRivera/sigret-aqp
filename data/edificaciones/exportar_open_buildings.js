// exportar_open_buildings.js
// Google Earth Engine (Code Editor): exporta a Google Drive las edificaciones
// detectadas por Google Open Buildings 2.5D Temporal (Sirko et al., 2023) en
// Arequipa Metropolitana, capas de 2017 y 2023, a 50 m (UTM 19S).
// Bandas por anio: cnt_ (numero de edificaciones), area_ (m2 construidos) y
// vol_ (m3 construidos = superficie x altura estimada).
// El archivo resultante (ob_temporal_aqp_50m.tif) va en data/edificaciones/.
// Nota: en el archivo exportado cada pixel de 50 m guarda el valor MEDIO por
// pixel de 4 m (comprobado contra sumas a 4 m con reduceRegion); por eso
// poblacion_actualizada.py multiplica por (50/4)^2 = 156,25 para obtener el
// total del pixel. La banda area_ sale redondeada a enteros (imagen entera) y
// no se usa; los indicadores usados son cnt_ y vol_.
var col = ee.ImageCollection('GOOGLE/Research/open-buildings-temporal/v1');
var region = ee.Geometry.Rectangle([-71.91, -16.56, -71.235, -15.92], null, false);
var p4 = ee.Projection('EPSG:32719').atScale(4);
var p50 = ee.Projection('EPSG:32719').atScale(50);
// Capas anuales con fecha de inferencia al 30 de junio
var T = {2017: 1498806000, 2023: 1688108400};
function capas(anio) {
  var m = col.filter(ee.Filter.eq('inference_time_epoch_s', T[anio])).filterBounds(region).mosaic();
  // building_fractional_count esta definido por pixel de 0,5 m: x64 = conteo por pixel de 4 m
  var cnt = m.select('building_fractional_count').multiply(64);
  var pres = m.select('building_presence').gt(0.5);
  var area = pres.multiply(16);
  var vol = pres.multiply(m.select('building_height')).multiply(16);
  return ee.Image.cat([cnt, area, vol]).rename(['cnt_' + anio, 'area_' + anio, 'vol_' + anio])
    .reproject(p4).reduceResolution({reducer: ee.Reducer.sum(), maxPixels: 1024}).reproject(p50);
}
var img = capas(2017).addBands(capas(2023)).toFloat();
Export.image.toDrive({image: img, description: 'ob_temporal_aqp_50m', folder: 'sigret_aqp',
  fileNamePrefix: 'ob_temporal_aqp_50m', region: region, crs: 'EPSG:32719', scale: 50,
  maxPixels: 1e10, fileFormat: 'GeoTIFF'});
