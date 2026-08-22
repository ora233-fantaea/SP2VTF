<script setup lang="ts">
import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

const show = defineModel<boolean>({ required: true });

const props = defineProps<{
  vtfcmd: string;
}>();

const materialsRoot = ref("");
const outputDir = ref("");
const items = ref<any[]>([]);
const exporting = ref(false);
const logs = ref<string[]>([]);

async function browseRoot() {
  const path = await open({ title: "选择 materials 根目录", directory: true, multiple: false });
  if (path) materialsRoot.value = path;
}

async function browseOutput() {
  const path = await open({ title: "选择 TGA 输出目录", directory: true, multiple: false });
  if (path) outputDir.value = path;
}

async function scanBumpmaps() {
  if (!materialsRoot.value) return;
  logs.value.push("扫描功能待实现");
}

async function exportTga() {
  if (!items.value.length) return;
  exporting.value = true;
  try {
    const queue = items.value
      .filter((i) => i.checked && i.vtf)
      .map((i) => ({ vmt_name: i.vmt_name, vtf_path: i.vtf, rel: i.rel }));
    const result = await invoke("export_vtf_to_tga", {
      queue,
      vtfcmd: props.vtfcmd,
      outputDir: outputDir.value,
    });
    const r = result as any;
    for (const line of r.log || []) logs.value.push(line);
  } catch (e: any) {
    logs.value.push(`[错误] ${e}`);
  } finally {
    exporting.value = false;
  }
}
</script>

<template>
  <v-dialog v-model="show" max-width="900" persistent>
    <v-card rounded="xl" variant="flat">
      <v-card-title class="d-flex align-center py-4 px-6 bg-primary text-white">
        <v-icon class="mr-2" color="white">mdi-export</v-icon>
        导出法线贴图 TGA
      </v-card-title>

      <v-card-text class="pa-6">
        <v-row>
          <v-col cols="12" sm="6">
            <div class="text-body-2 font-weight-medium text-medium-emphasis mb-1">
              <v-icon size="small" class="mr-1">mdi-folder</v-icon>
              materials 根目录
            </div>
            <v-text-field
              v-model="materialsRoot"
              placeholder="选择 L4D2 addon 的 materials 目录…"
              hide-details
              readonly
            >
              <template #append-inner>
                <v-btn icon="mdi-folder-open" variant="text" size="small" color="primary" @click="browseRoot" />
              </template>
            </v-text-field>
          </v-col>
          <v-col cols="12" sm="6">
            <div class="text-body-2 font-weight-medium text-medium-emphasis mb-1">
              <v-icon size="small" class="mr-1">mdi-folder-export</v-icon>
              输出文件夹
            </div>
            <v-text-field
              v-model="outputDir"
              placeholder="选择 TGA 输出目录…"
              hide-details
              readonly
            >
              <template #append-inner>
                <v-btn icon="mdi-folder-open" variant="text" size="small" color="primary" @click="browseOutput" />
              </template>
            </v-text-field>
          </v-col>
        </v-row>

        <div class="d-flex ga-3 mt-4">
          <v-btn prepend-icon="mdi-magnify" @click="scanBumpmaps">扫描 VMT</v-btn>
          <v-btn prepend-icon="mdi-export" color="success" :loading="exporting" @click="exportTga">开始导出</v-btn>
        </div>

        <v-card
          variant="outlined"
          rounded="lg"
          class="mt-4"
        >
          <v-card-text class="log-area">
            <div v-if="logs.length === 0" class="d-flex align-center justify-center h-100 text-medium-emphasis">
              等待操作...
            </div>
            <div v-for="(line, i) in logs" :key="i" class="text-body-2">{{ line }}</div>
          </v-card-text>
        </v-card>
      </v-card-text>

      <v-divider />
      <v-card-actions class="px-6 py-3">
        <v-spacer />
        <v-btn variant="tonal" @click="show = false">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style>
.v-overlay .v-overlay__scrim {
  backdrop-filter: blur(6px) saturate(120%);
  background-color: rgba(0, 0, 0, 0.35) !important;
}
</style>

<style scoped>
.log-area {
  height: 200px;
  overflow-y: auto;
  font-family: "Cascadia Code", "Fira Code", Consolas, monospace;
  font-size: 12px;
  line-height: 1.8;
}
</style>
