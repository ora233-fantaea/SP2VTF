<script setup lang="ts">
import { ref, onMounted } from "vue";
import { invoke } from "@tauri-apps/api/core";
import PathConfig from "./components/PathConfig.vue";
import OutputSettings from "./components/OutputSettings.vue";
import ButtonBar from "./components/ButtonBar.vue";
import VmtTree from "./components/VmtTree.vue";
import LogPanel from "./components/LogPanel.vue";
import ExportNormalDialog from "./components/ExportNormalDialog.vue";
import PreprocessDialog from "./components/PreprocessDialog.vue";

const configPath = ref("");
const config = ref<any>({});
const items = ref<any[]>([]);
const logs = ref<string[]>([]);
const converting = ref(false);
const showExportDialog = ref(false);
const showPreprocessDialog = ref(false);

onMounted(async () => {
  try {
    configPath.value = await invoke("get_config_path");
  } catch (e) {
    configPath.value = "config.json";
  }
  try {
    config.value = await invoke("load_config", { configPath: configPath.value });
  } catch (e) {
    console.error("load config failed:", e);
  }
});

function addLog(msg: string) {
  logs.value.push(msg);
}

async function handleScan() {
  try {
    addLog("扫描 VMT...");
    const result = await invoke("scan_vmts", {
      vmtDir: config.value.vmt_dir || "",
      pngDir: config.value.png_dir || "",
      defaultW: config.value.resize_width || 1024,
      defaultH: config.value.resize_height || 1024,
    });
    items.value = result as any[];
    const baseCount = items.value.filter((i: any) => i.base?.enabled).length;
    const normalCount = items.value.filter((i: any) => i.normal?.enabled).length;
    addLog(`已载入 ${items.value.length} 个 VMT（可替换 basetexture: ${baseCount}，bumpmap: ${normalCount}）`);
  } catch (e: any) {
    addLog(`[错误] ${e}`);
  }
}

async function handleConvert() {
  if (items.value.length === 0) {
    addLog("[错误] 请先载入 VMT");
    return;
  }
  converting.value = true;
  try {
    const settings = { ...config.value };
    const result = await invoke("convert_items", { items: items.value, settings });
    const r = result as any;
    for (const line of r.log || []) addLog(line);
  } catch (e: any) {
    addLog(`[错误] ${e}`);
  } finally {
    converting.value = false;
  }
}

async function handleSaveConfig() {
  try {
    await invoke("save_config", { configPath: configPath.value, data: config.value });
    addLog("配置已保存");
  } catch (e: any) {
    addLog(`[错误] 保存配置失败: ${e}`);
  }
}

function handlePreprocessSave(base: any, normal: any) {
  config.value.preprocess_base = base;
  config.value.preprocess_normal = normal;
  addLog("预处理配置已更新");
}
</script>

<template>
  <v-app :class="{ 'dialog-open': showExportDialog || showPreprocessDialog }">
    <v-app-bar flat color="primary" density="comfortable">
      <v-app-bar-title class="font-weight-bold">
        <v-icon class="mr-2">mdi-texture</v-icon>
        SP2VTF 贴图转换工具
      </v-app-bar-title>
    </v-app-bar>

    <v-main class="bg-background">
      <v-container fluid class="pa-6">
        <PathConfig v-model="config" class="mb-5" />

        <OutputSettings v-model="config" :items="items" class="mb-5" />

        <ButtonBar
          :converting="converting"
          @scan="handleScan"
          @convert="handleConvert"
          @save-config="handleSaveConfig"
          @clear-logs="logs = []"
          @export-normal="showExportDialog = true"
          @preprocess="showPreprocessDialog = true"
          class="mb-5"
        />

        <v-row>
          <v-col cols="12" md="7">
            <v-card rounded="xl" class="h-100">
              <v-card-title class="d-flex align-center py-3 px-5 bg-surface-bright">
                <v-icon color="primary" class="mr-2">mdi-file-tree</v-icon>
                <span class="text-subtitle-1 font-weight-bold">VMT 列表</span>
              </v-card-title>
              <v-divider />
              <v-card-text class="pa-4">
                <VmtTree v-model:items="items" />
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" md="5">
            <v-card rounded="xl" class="h-100">
              <v-card-title class="d-flex align-center py-3 px-5 bg-surface-bright">
                <v-icon color="success" class="mr-2">mdi-console</v-icon>
                <span class="text-subtitle-1 font-weight-bold">运行日志</span>
              </v-card-title>
              <v-divider />
              <v-card-text class="pa-4">
                <LogPanel :logs="logs" />
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </v-main>

    <ExportNormalDialog
      v-model="showExportDialog"
      :vtfcmd="config.vtfcmd || ''"
    />

    <PreprocessDialog
      v-model="showPreprocessDialog"
      :config-base="config.preprocess_base || {}"
      :config-normal="config.preprocess_normal || {}"
      @save="handlePreprocessSave"
    />
  </v-app>
</template>

<style>
/* Vuetify teleports dialogs outside v-app, so blur the app layer itself. */
.v-application.dialog-open {
  filter: blur(6px);
}
</style>
