<script setup lang="ts">
import { ref } from "vue";

const items = defineModel<any[]>("items", { required: true });

function toggleCheck(item: any, slot: "base" | "normal") {
  if (!item[slot]?.enabled) return;
  item[slot].checked = !item[slot].checked;
}

const editDialog = ref(false);
const editing = ref<any>(null);
const editW = ref(128);
const editH = ref(128);

function openEdit(item: any, slot: "base" | "normal") {
  if (!item[slot]?.enabled) return;
  editing.value = { item, slot };
  editW.value = item[slot].target_w;
  editH.value = item[slot].target_h;
  editDialog.value = true;
}

function saveEdit() {
  const s = editing.value.item[editing.value.slot];
  const w = parseInt(String(editW.value), 10);
  const h = parseInt(String(editH.value), 10);
  if (!Number.isNaN(w) && w >= 128 && w <= 4096) s.target_w = w;
  if (!Number.isNaN(h) && h >= 128 && h <= 4096) s.target_h = h;
  editDialog.value = false;
}

function sizeInfo(slot: any): string {
  if (!slot?.enabled) {
    if (!slot?.rel) return "VMT 未定义";
    return "缺少 PNG";
  }
  const sfx = (slot.suffix || "").replace(/^_/, "");
  const src = slot.size ? `${slot.size[0]}x${slot.size[1]}` : "?";
  const tgt = `${slot.target_w}x${slot.target_h}`;
  return sfx ? `${sfx}  ${src} → ${tgt}` : `${src} → ${tgt}`;
}

function slotColor(slot: any): string {
  if (!slot?.enabled) return "grey";
  return slot.checked ? "primary" : "grey";
}
</script>

<template>
  <v-data-table
    v-if="items.length"
    :items="items"
    item-value="vmt_name"
    density="compact"
    hover
    :headers="[
      { title: 'VMT 文件', key: 'vmt_name', width: '22%' },
      { title: 'base', key: 'baseMark', width: '6%', align: 'center' },
      { title: 'basetexture 源 → 目标', key: 'baseInfo', width: '32%' },
      { title: 'normal', key: 'normalMark', width: '6%', align: 'center' },
      { title: 'bumpmap 源 → 目标', key: 'normalInfo', width: '32%' },
    ]"
    class="rounded-lg"
  >
    <template #[`item.vmt_name`]="{ item }">
      <div class="d-flex align-center ga-2">
        <v-icon size="small" color="amber-darken-2">mdi-file-document</v-icon>
        <span class="text-body-2 font-weight-medium">{{ item.vmt_name }}</span>
      </div>
    </template>
    <template #[`item.baseMark`]="{ item }">
      <v-icon
        :color="slotColor(item.base)"
        size="small"
        style="cursor: pointer"
        @click="toggleCheck(item, 'base')"
      >
        {{ item.base?.enabled ? (item.base?.checked ? "mdi-checkbox-marked" : "mdi-checkbox-blank-outline") : "mdi-minus-box" }}
      </v-icon>
    </template>
    <template #[`item.baseInfo`]="{ item }">
      <span
        class="text-body-2"
        :class="item.base?.enabled ? 'resize-cell' : 'text-medium-emphasis'"
        :title="item.base?.enabled ? '双击修改目标分辨率' : ''"
        @dblclick="openEdit(item, 'base')"
      >
        {{ sizeInfo(item.base) }}
      </span>
    </template>
    <template #[`item.normalMark`]="{ item }">
      <v-icon
        :color="slotColor(item.normal)"
        size="small"
        style="cursor: pointer"
        @click="toggleCheck(item, 'normal')"
      >
        {{ item.normal?.enabled ? (item.normal?.checked ? "mdi-checkbox-marked" : "mdi-checkbox-blank-outline") : "mdi-minus-box" }}
      </v-icon>
    </template>
    <template #[`item.normalInfo`]="{ item }">
      <span
        class="text-body-2"
        :class="item.normal?.enabled ? 'resize-cell' : 'text-medium-emphasis'"
        :title="item.normal?.enabled ? '双击修改目标分辨率' : ''"
        @dblclick="openEdit(item, 'normal')"
      >
        {{ sizeInfo(item.normal) }}
      </span>
    </template>
  </v-data-table>
  <v-alert
    v-else
    type="info"
    variant="tonal"
    density="compact"
    rounded="lg"
    prepend-icon="mdi-information-outline"
  >
     点击「载入 VMT」开始扫描
  </v-alert>

  <v-dialog v-model="editDialog" max-width="340" persistent>
    <v-card rounded="xl" variant="flat">
      <v-card-title class="d-flex align-center py-3 px-5 bg-surface-bright">
        <v-icon color="primary" class="mr-2">mdi-resize</v-icon>
        <span class="text-subtitle-1 font-weight-bold">修改目标分辨率</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-5">
        <v-row dense>
          <v-col cols="6">
            <v-text-field
              v-model="editW"
              label="宽 (px)"
              type="number"
              density="compact"
              hide-details
              min="128"
              max="4096"
            />
          </v-col>
          <v-col cols="6">
            <v-text-field
              v-model="editH"
              label="高 (px)"
              type="number"
              density="compact"
              hide-details
              min="128"
              max="4096"
            />
          </v-col>
        </v-row>
        <div class="text-caption text-medium-emphasis mt-2">范围 128 ~ 4096</div>
      </v-card-text>
      <v-card-actions class="px-5 pb-4">
        <v-spacer />
        <v-btn variant="text" color="grey" @click="editDialog = false">取消</v-btn>
        <v-btn variant="flat" color="primary" @click="saveEdit">确定</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.resize-cell {
  cursor: pointer;
}

.resize-cell:hover {
  text-decoration: underline;
  text-decoration-style: dotted;
}
</style>
