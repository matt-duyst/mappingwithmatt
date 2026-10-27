# Notes on this MapLibre copy

The map's idle drift in index.html sets MapLibre's internal `_fadeDuration` to 0 while it turns and restores it when it stops; it feature-detects the field and leaves it alone when absent, but check that it still exists and still controls the label-placement fade on any MapLibre upgrade.
