# mappingwithmatt.com

Personal site for Matt Duyst: environmental data scientist, machine learning.

Single static page (`index.html`) with an interactive roadmap built on MapLibre GL JS 6.10.0 (ES module) over USGS National Map imagery (public domain), with EOX Sentinel-2 cloudless, an OpenFreeMap dark basemap and labels overlay, and AWS Terrain Tiles as switchable layers. Assets in `assets/`, the map engine vendored in `vendor/`.

## Deploy
1. Push to the `main` branch of a public repo.
2. Settings, Pages: deploy from `main`, root.
3. Keep `CNAME` (mappingwithmatt.com) and point the domain's DNS at GitHub Pages.

## Contact form
`#composer-form` opens the visitor's mail app. To send from the page, point the form at a Formspree (or similar) endpoint and remove the mailto handler in the script.

## Sources and licenses
Imagery: USGS The National Map, USGSImageryOnly (public domain; NAIP 2017 to 2021 for the lower 48). EOX Sentinel-2 cloudless 2024 (contains modified Copernicus Sentinel data; CC BY-NC-SA 4.0, suitable for this non-commercial site). Labels and dark basemap: OpenFreeMap (no key, no request cap), OpenMapTiles schema, OpenStreetMap contributors (ODbL). Terrain: Mapzen and AWS Terrain Tiles (see tilezen/joerd attribution). Engine: MapLibre GL JS 6 (BSD-3). Icons: Lucide (ISC) and Phosphor (MIT). Fonts: Inter, JetBrains Mono (OFL).

## Browser support and accessibility
MapLibre GL JS 6 requires WebGL 2; the map does not render on browsers without it, and the page's Experience section carries the same content as text. Flights and transitions are skipped when the operating system's reduce-motion setting is on. Cooperative gestures are enabled: on a phone the page scrolls over the map with one finger and the map pans with two; on desktop, scroll-zoom needs Ctrl or Cmd. Keyboard: Space plays, arrow keys step between stops, plus and minus zoom, 0 fits the route, P collapses the panel.
