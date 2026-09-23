# mappingwithmatt.com

mappingwithmatt.com is the personal site of Matt Duyst, an environmental data scientist working at the intersection of remote sensing, field measurement, and carbon accounting. The site is one static page. Its centerpiece, "At a glance," is an interactive roadmap that follows the route from a citrus farm in California's Central Valley through UCLA, Yale, a summer at a peatland flux tower in Minnesota, drone-based methane work in Texas, and current work on rangeland soil carbon: each stop a card, each study site an arc, the whole route playable. The map runs on MapLibre GL JS over USGS National Map imagery, with Sentinel-2, an OpenFreeMap dark basemap, and AWS terrain as switchable layers, and it is built to the standards this repository documents: pinned and vendored dependencies, open and attributed data, keyboard and reduced-motion support, and content that traces to the public record.

## Deploy
1. Push to the `main` branch of a public repo.
2. Settings, Pages: deploy from `main`, root.
3. Keep `CNAME` (mappingwithmatt.com) and point the domain's DNS at GitHub Pages.

## Local preview
```
python3 -m http.server 8000
```
Then open http://localhost:8000.

## Contact form
The form posts to Formspree (form mljdnobg) from the page's own script and shows a sent state without leaving the site. Submissions arrive at the site owner's email. Formspree's Formshield spam filter is on. The form is revealed by the chat control and requires JavaScript; without it, the email address beside the form remains the way to get in touch.

## Sources and licenses
Imagery: USGS The National Map, USGSImageryOnly (public domain; NAIP 2017 to 2021 for the lower 48). EOX Sentinel-2 cloudless 2024 (contains modified Copernicus Sentinel data; CC BY-NC-SA 4.0, suitable for this non-commercial site). Labels and dark basemap: OpenFreeMap (no key, no request cap), OpenMapTiles schema, OpenStreetMap contributors (ODbL). Terrain: Mapzen and AWS Terrain Tiles (see tilezen/joerd attribution). Engine: MapLibre GL JS 6 (BSD-3). Icons: Lucide (ISC) and Phosphor (MIT). Fonts: Inter, JetBrains Mono (OFL).

## Browser support and accessibility
MapLibre GL JS 6 requires WebGL 2; the map does not render on browsers without it, and the page's Experience section carries the same content as text. Flights and transitions are skipped when the operating system's reduce-motion setting is on. Cooperative gestures are enabled: on a phone the page scrolls over the map with one finger and the map pans with two; on desktop, scroll-zoom needs Ctrl or Cmd. Keyboard: Space plays, arrow keys step between stops, plus and minus zoom, 0 fits the route, P collapses the panel.
