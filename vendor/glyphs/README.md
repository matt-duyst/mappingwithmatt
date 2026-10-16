# Map label glyphs

Signed-distance-field glyph ranges for Noto Sans Regular, the font the map's place labels use, taken from the OpenFreeMap font server (https://tiles.openfreemap.org/fonts/) so that the labels never wait on a third party. Only the ranges the labels request are kept: 0-255, 512-767, 7680-7935 and 8192-8447, the ones fetched on the globe at zoom 1.4 and at rest at Visalia. A label needing another range renders without the missing characters until the range is added here.

Noto Sans is licensed under the SIL Open Font License, Version 1.1, as OpenFreeMap's LICENSE.md states; the license text is in OFL.txt.
