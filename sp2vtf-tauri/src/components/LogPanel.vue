<script setup lang="ts">
import { ref, watch, nextTick } from "vue";

const props = defineProps<{
  logs: string[];
}>();

const logEl = ref<HTMLElement>();

function logClass(line: string): string {
  if (line.includes("[错误]") || line.includes("[失败]")) return "text-error font-weight-bold";
  if (line.includes("[警告]")) return "text-warning";
  if (line.includes("[成功]")) return "text-success";
  if (line.startsWith("====")) return "text-primary font-weight-bold";
  if (line.startsWith("===")) return "text-primary";
  return "";
}

function logIcon(line: string): string {
  if (line.includes("[错误]") || line.includes("[失败]")) return "mdi-close-circle";
  if (line.includes("[警告]")) return "mdi-alert";
  if (line.includes("[成功]")) return "mdi-check-circle";
  if (line.startsWith("====")) return "mdi-flag-checkered";
  return "";
}

watch(
  () => props.logs.length,
  async () => {
    await nextTick();
    if (logEl.value) {
      logEl.value.scrollTop = logEl.value.scrollHeight;
    }
  }
);
</script>

<template>
  <div
    ref="logEl"
    class="log-container"
  >
    <div v-if="logs.length === 0" class="d-flex align-center justify-center h-100 text-medium-emphasis">
      <v-icon class="mr-2" size="small">mdi-clock-outline</v-icon>
      等待操作...
    </div>
    <div
      v-for="(line, i) in logs"
      :key="i"
      class="log-line d-flex align-start ga-2"
      :class="logClass(line)"
    >
      <v-icon v-if="logIcon(line)" size="x-small" class="mt-1 flex-shrink-0">{{ logIcon(line) }}</v-icon>
      <span>{{ line }}</span>
    </div>
  </div>
</template>

<style scoped>
.log-container {
  height: 300px;
  overflow-y: auto;
  background: #FAFAFA;
  border: 1px solid #E0E0E0;
  border-radius: 12px;
  padding: 12px 16px;
  font-family: "Cascadia Code", "Fira Code", Consolas, monospace;
  font-size: 12px;
  line-height: 1.8;
}
.log-line {
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
