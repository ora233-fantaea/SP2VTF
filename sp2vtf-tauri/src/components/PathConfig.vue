<script setup lang="ts">
import { open } from "@tauri-apps/plugin-dialog";

const config = defineModel<any>({ required: true });

async function browseFile(key: string) {
  const path = await open({
    title: "选择 VTFCmd.exe",
    multiple: false,
    filters: [{ name: "可执行文件", extensions: ["exe"] }],
  });
  if (typeof path === "string" && path.toLowerCase().endsWith(".exe")) {
    config.value[key] = path;
  }
}

async function browseDir(key: string) {
  const path = await open({ title: "选择文件夹", directory: true, multiple: false });
  if (path) config.value[key] = path;
}

const fields = [
  { key: "vtfcmd", label: "VTFCmd.exe 路径", icon: "mdi-cog", browse: "file" },
  { key: "png_dir", label: "SP PNG 文件夹", icon: "mdi-image-multiple", browse: "dir" },
  { key: "vmt_dir", label: "VMT 文件夹", icon: "mdi-file-document-multiple", browse: "dir" },
] as const;
</script>

<template>
  <v-card rounded="xl">
    <v-card-title class="d-flex align-center py-3 px-5 bg-surface-bright">
      <v-icon color="primary" class="mr-2">mdi-folder-cog</v-icon>
      <span class="text-subtitle-1 font-weight-bold">路径配置</span>
    </v-card-title>
    <v-divider />
    <v-card-text class="pa-5">
      <v-row>
        <v-col v-for="field in fields" :key="field.key" cols="12" sm="4">
          <div class="text-body-2 font-weight-medium text-medium-emphasis mb-1">
            <v-icon size="small" class="mr-1">{{ field.icon }}</v-icon>
            {{ field.label }}
          </div>
          <v-text-field
            v-model="config[field.key]"
            placeholder="点击浏览选择…"
            hide-details
            readonly
            class="path-input"
          >
            <template #append-inner>
              <v-btn
                icon="mdi-folder-open"
                variant="text"
                size="small"
                color="primary"
                @click="field.browse === 'file' ? browseFile(field.key) : browseDir(field.key)"
              />
            </template>
          </v-text-field>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>
