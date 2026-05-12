# Scaffold — Vue / Angular (delta from React)

`@deck.gl/carto` and `@carto/api-client` are framework-agnostic. The integration story is the same in any framework: instantiate `Deck` (or use a wrapper), feed it layers, sync MapLibre.

There are no first-party Vue/Angular wrappers from deck.gl, so the pattern is **`@deck.gl/core` directly inside a component lifecycle hook**.

## Vue 3 + Vite

`package.json` deltas vs the React scaffold (drop `react`, `react-dom`, `@deck.gl/react`, `react-map-gl`; add Vue + the Vue plugin):

```json
{
  "dependencies": {
    "vue": "^3.4.0",
    "@deck.gl/core": "^9.2.2",
    "@deck.gl/carto": "^9.2.2",
    "@carto/api-client": "^0.5.24",
    "maplibre-gl": "^5.12.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "typescript": "~5.8.3",
    "vite": "^6.0.0",
    "vue-tsc": "^2.0.0"
  }
}
```

`Map.vue`:

```vue
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import { Deck } from '@deck.gl/core';
import { VectorTileLayer, BASEMAP } from '@deck.gl/carto';
import { vectorTableSource } from '@carto/api-client';
import maplibregl from 'maplibre-gl';

const props = defineProps<{ accessToken: string }>();
const mapEl = ref<HTMLDivElement>();
const canvasEl = ref<HTMLCanvasElement>();
let deck: Deck | undefined;
let map: maplibregl.Map | undefined;

const INITIAL_VIEW_STATE = { longitude: -73.97, latitude: 40.75, zoom: 12, pitch: 0, bearing: 0 };

onMounted(() => {
  map = new maplibregl.Map({
    container: mapEl.value!,
    style: BASEMAP.POSITRON,
    interactive: false,
    ...INITIAL_VIEW_STATE,
  });

  const dataSource = vectorTableSource({
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
    accessToken: props.accessToken,
    connectionName: import.meta.env.VITE_CONNECTION_NAME,
    tableName: 'my_project.demo.points',
  });

  deck = new Deck({
    canvas: canvasEl.value!,
    initialViewState: INITIAL_VIEW_STATE,
    controller: true,
    layers: [new VectorTileLayer({ id: 'points', data: dataSource, getFillColor: [200, 0, 80] })],
    onViewStateChange: ({ viewState }) => {
      const { longitude, latitude, ...rest } = viewState;
      map?.jumpTo({ center: [longitude, latitude], ...rest });
    },
  });
});

onUnmounted(() => { deck?.finalize(); map?.remove(); });
</script>

<template>
  <div class="app">
    <div ref="mapEl" class="map"></div>
    <canvas ref="canvasEl" class="deck-canvas"></canvas>
  </div>
</template>

<style scoped>
.app { position: relative; height: 100vh; width: 100vw; }
.map, .deck-canvas { position: absolute; inset: 0; }
</style>
```

For reactive state (filters, view state), use `ref()` / `reactive()` and call `deck.setProps({ layers })` from a `watchEffect`. Don't recreate the `Deck` on every change.

## Angular 17+ (standalone components)

Same shape, different lifecycle. `package.json` adds `@angular/core`, `@angular/common`, `@angular/platform-browser`, drops the React deps.

`map.component.ts`:

```ts
import { Component, ElementRef, Input, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { Deck } from '@deck.gl/core';
import { VectorTileLayer, BASEMAP } from '@deck.gl/carto';
import { vectorTableSource } from '@carto/api-client';
import maplibregl from 'maplibre-gl';

@Component({
  selector: 'app-map',
  standalone: true,
  template: `
    <div class="app">
      <div #mapEl class="map"></div>
      <canvas #canvasEl class="deck-canvas"></canvas>
    </div>
  `,
  styles: [`
    .app { position: relative; height: 100vh; width: 100vw; }
    .map, .deck-canvas { position: absolute; inset: 0; }
  `],
})
export class MapComponent implements OnInit, OnDestroy {
  @Input({ required: true }) accessToken!: string;
  @ViewChild('mapEl', { static: true }) mapEl!: ElementRef<HTMLDivElement>;
  @ViewChild('canvasEl', { static: true }) canvasEl!: ElementRef<HTMLCanvasElement>;

  private deck?: Deck;
  private map?: maplibregl.Map;

  ngOnInit() {
    const INITIAL_VIEW_STATE = { longitude: -73.97, latitude: 40.75, zoom: 12, pitch: 0, bearing: 0 };

    this.map = new maplibregl.Map({
      container: this.mapEl.nativeElement,
      style: BASEMAP.POSITRON, interactive: false, ...INITIAL_VIEW_STATE,
    });

    const dataSource = vectorTableSource({
      apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
      accessToken: this.accessToken,
      connectionName: import.meta.env.VITE_CONNECTION_NAME,
      tableName: 'my_project.demo.points',
    });

    this.deck = new Deck({
      canvas: this.canvasEl.nativeElement,
      initialViewState: INITIAL_VIEW_STATE,
      controller: true,
      layers: [new VectorTileLayer({ id: 'points', data: dataSource, getFillColor: [200, 0, 80] })],
      onViewStateChange: ({ viewState }) => {
        const { longitude, latitude, ...rest } = viewState;
        this.map?.jumpTo({ center: [longitude, latitude], ...rest });
      },
    });
  }

  ngOnDestroy() { this.deck?.finalize(); this.map?.remove(); }
}
```

For reactive updates, store filters/view state in a `signal()` and call `this.deck.setProps({ layers })` from an `effect()`.

## What stays the same

- All references in this skill (`data-sources.md`, `widgets.md`, `filters.md`, …) work unchanged. They're about the data layer, not the view layer.
- Auth references work unchanged — `@auth0/auth0-spa-js` is framework-agnostic.

## What's missing

- Hot module reload of `Deck` instances is brittle in both frameworks. Full reload on edit is fine for development.
- No first-party hooks/composables/services. If the user wants `useCartoMap()` ergonomics, that's a wrapper they own.
