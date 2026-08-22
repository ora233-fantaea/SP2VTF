<script setup lang="ts">
const config = defineModel<any>({ required: true });
const props = defineProps<{ items: any[] }>();

function applyDefault() {
  const w = Number(config.value?.resize_width) || 1024;
  const h = Number(config.value?.resize_height) || 1024;
  for (const it of props.items ?? []) {
    if (it.base?.enabled) {
      it.base.target_w = w;
      it.base.target_h = h;
    }
    if (it.normal?.enabled) {
      it.normal.target_w = w;
      it.normal.target_h = h;
    }
  }
}

const VTF_VERSIONS = ["7.0", "7.1", "7.2", "7.3", "7.4", "7.5"];
const VTF_FORMATS = [
  "RGBA8888", "ABGR8888", "RGB888", "BGR888", "RGB565",
  "I8", "IA88", "A8",
  "RGB888_BLUESCREEN", "BGR888_BLUESCREEN",
  "ARGB8888", "BGRA8888",
  "DXT1", "DXT3", "DXT5",
  "BGRX8888", "BGR565", "BGRX5551", "BGRA4444",
  "DXT1_ONEBITALPHA", "BGRA5551",
  "UV88", "UVWQ8888",
  "RGBA16161616F", "RGBA16161616", "UVLX8888",
];
const RESIZE_METHODS = ["nearest", "bell", "bspline", "blackman", "catrom", "gaussian", "hanning", "hamming", "kaiser", "lanczos3", "mitchell", "point", "quadratic", "sinc", "triangle"];
const RESIZE_FILTERS = ["point", "box", "triangle", "cubic", "catrom", "mitchell", "gaussian", "sinc", "bessel", "hanning", "hamming", "blackman", "kaiser"];
</script>

<template>
  <v-card rounded="xl">
    <v-card-title class="d-flex align-center py-3 px-5 bg-surface-bright">
      <v-icon color="secondary" class="mr-2">mdi-tune</v-icon>
      <span class="text-subtitle-1 font-weight-bold">输出设置</span>
    </v-card-title>
    <v-divider />
    <v-card-text class="pa-5">
      <!-- VTF 参数行 -->
      <div class="d-flex align-center flex-wrap ga-4 mb-4">
        <v-chip color="primary" variant="tonal" size="small" class="font-weight-bold">VTF</v-chip>

        <div class="d-flex align-center ga-2">
          <span class="text-body-2 text-medium-emphasis">版本</span>
          <v-select
            v-model="config.vtf_version"
            :items="VTF_VERSIONS"
            hide-details
            style="width: 110px"
          />
        </div>

        <div class="d-flex align-center ga-2">
          <span class="text-body-2 text-medium-emphasis">Color</span>
          <v-select
            v-model="config.color_format"
            :items="VTF_FORMATS"
            hide-details
            class="format-select"
          />
        </div>

        <div class="d-flex align-center ga-2">
          <span class="text-body-2 text-medium-emphasis">Alpha</span>
          <v-select
            v-model="config.alpha_format"
            :items="VTF_FORMATS"
            hide-details
            class="format-select"
          />
        </div>
      </div>

      <v-divider class="mb-4" />

      <!-- 分辨率 + Resize 行 -->
      <div class="d-flex align-center flex-wrap ga-4">
        <div class="d-flex align-center ga-3">
          <v-checkbox
            v-model="config.size_enabled"
            label="分辨率"
            hide-details
            density="compact"
          />
          <v-text-field
            v-model.number="config.resize_width"
            type="number"
            :disabled="!config.size_enabled"
            hide-details
            style="width: 110px"
          />
          <span class="text-medium-emphasis">×</span>
          <v-text-field
            v-model.number="config.resize_height"
            type="number"
            :disabled="!config.size_enabled"
            hide-details
            style="width: 110px"
          />
          <v-btn
            prepend-icon="mdi-check-decagram"
            color="primary"
            size="small"
            :disabled="!config.size_enabled"
            title="将当前分辨率应用到所有已载入贴图"
            @click="applyDefault"
          >
            应用默认
          </v-btn>
        </div>

        <v-divider vertical class="mx-2" />

        <div class="d-flex align-center ga-3">
          <v-checkbox
            v-model="config.resize_enabled"
            label="Resize"
            hide-details
            density="compact"
          />
          <v-select
            v-model="config.resize_method"
            :items="RESIZE_METHODS"
            :disabled="!config.resize_enabled"
            hide-details
            style="width: 140px"
          />
          <v-select
            v-model="config.resize_filter"
            :items="RESIZE_FILTERS"
            :disabled="!config.resize_enabled"
            hide-details
            style="width: 140px"
          />
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.format-select {
  flex: 0 1 auto;
  width: max-content;
  min-width: 120px;
}
</style>
