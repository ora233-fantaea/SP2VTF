<script setup lang="ts">
defineProps<{
  converting: boolean;
}>();

const emit = defineEmits<{
  scan: [];
  convert: [];
  saveConfig: [];
  clearLogs: [];
  exportNormal: [];
  preprocess: [];
}>();
</script>

<template>
  <v-card rounded="xl">
    <v-card-text class="py-3 px-5">
      <div class="d-flex align-center flex-wrap ga-3">
        <!-- 操作区 -->
        <v-chip color="primary" variant="tonal" size="small" class="font-weight-bold">操作</v-chip>

        <v-btn
          prepend-icon="mdi-file-find"
          color="primary"
          @click="emit('scan')"
        >
          载入 VMT
        </v-btn>

        <v-btn
          prepend-icon="mdi-play"
          color="success"
          :loading="converting"
          @click="emit('convert')"
        >
          开始转换
        </v-btn>

        <v-divider vertical class="mx-2" />

        <!-- 工具区 -->
        <v-chip color="secondary" variant="tonal" size="small" class="font-weight-bold">工具</v-chip>

        <v-btn
          prepend-icon="mdi-content-save"
          variant="tonal"
          @click="emit('saveConfig')"
        >
          保存配置
        </v-btn>

        <v-btn
          prepend-icon="mdi-delete-sweep"
          variant="tonal"
          @click="emit('clearLogs')"
        >
          清空日志
        </v-btn>

        <v-btn
          prepend-icon="mdi-layers-outline"
          variant="tonal"
          @click="emit('preprocess')"
        >
          预处理设置
          <v-chip size="x-small" color="warning" class="ml-1" label>beta</v-chip>
        </v-btn>

        <v-btn
          prepend-icon="mdi-export"
          variant="tonal"
          @click="emit('exportNormal')"
        >
          导出法线 TGA
        </v-btn>
      </div>
    </v-card-text>
  </v-card>
</template>
