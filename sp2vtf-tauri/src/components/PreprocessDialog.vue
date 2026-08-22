<script setup lang="ts">
import { ref, computed, watch } from "vue";

const show = defineModel<boolean>({ required: true });

const props = defineProps<{
  configBase: any;
  configNormal: any;
}>();

const emit = defineEmits<{
  save: [base: any, normal: any];
}>();

const currentSlot = ref<"base" | "normal">("base");
const baseConfig = ref<any>({ ...props.configBase });
const normalConfig = ref<any>({ ...props.configNormal });

const ALPHA_SOURCES = [
  { title: "R 通道", value: "r" },
  { title: "G 通道", value: "g" },
  { title: "B 通道", value: "b" },
  { title: "灰度", value: "gray" },
];

const cfg = computed(() => currentSlot.value === "base" ? baseConfig.value : normalConfig.value);

function switchSlot(slot: "base" | "normal") {
  currentSlot.value = slot;
}

function onSave() {
  emit("save", { ...baseConfig.value }, { ...normalConfig.value });
  show.value = false;
}

watch(() => props.configBase, (v) => { baseConfig.value = { ...v }; }, { deep: true });
watch(() => props.configNormal, (v) => { normalConfig.value = { ...v }; }, { deep: true });
</script>

<template>
  <v-dialog v-model="show" max-width="420" persistent>
    <v-card rounded="xl" variant="flat">
      <v-card-title class="d-flex align-center py-4 px-5 bg-primary text-white">
        <v-icon class="mr-2" color="white">mdi-layers-outline</v-icon>
        预处理设置
      </v-card-title>

      <v-card-text class="pa-5">
        <!-- 槽位切换 -->
        <div class="d-flex ga-2 mb-5">
          <v-btn
            :variant="currentSlot === 'base' ? 'flat' : 'outlined'"
            :color="currentSlot === 'base' ? 'primary' : undefined"
            size="small"
            @click="switchSlot('base')"
          >
            [base]
          </v-btn>
          <v-btn
            :variant="currentSlot === 'normal' ? 'flat' : 'outlined'"
            :color="currentSlot === 'normal' ? 'primary' : undefined"
            size="small"
            @click="switchSlot('normal')"
          >
            [normal]
          </v-btn>
        </div>

        <!-- 当前槽位配置 -->
        <div class="mb-4">
          <v-checkbox
            v-model="cfg.alpha_enabled"
            label="生成 Alpha 通道"
            hide-details
            density="compact"
            color="primary"
            class="mb-3"
          />

          <div class="ml-8 mb-3">
            <div class="text-body-2 text-medium-emphasis mb-1">来源</div>
            <v-select
              v-model="cfg.alpha_source"
              :items="ALPHA_SOURCES"
              :disabled="!cfg.alpha_enabled"
              hide-details
              density="compact"
            />
          </div>

          <v-checkbox
            v-model="cfg.levels_enabled"
            label="Alpha 色阶"
            hide-details
            density="compact"
            color="primary"
            class="mb-3"
          />

          <div class="ml-8 d-flex ga-4">
            <div>
              <div class="text-body-2 text-medium-emphasis mb-1">输出黑点</div>
              <v-text-field
                v-model.number="cfg.out_black"
                type="number"
                :disabled="!cfg.levels_enabled"
                hide-details
                density="compact"
                style="width: 80px"
              />
            </div>
            <div>
              <div class="text-body-2 text-medium-emphasis mb-1">输出白点</div>
              <v-text-field
                v-model.number="cfg.out_white"
                type="number"
                :disabled="!cfg.levels_enabled"
                hide-details
                density="compact"
                style="width: 80px"
              />
            </div>
          </div>
        </div>

        <!-- 提示 -->
        <v-alert
          v-if="currentSlot === 'base'"
          type="info"
          variant="tonal"
          density="compact"
          rounded="lg"
          class="mb-2"
        >
          当前默认输出格式为 DXT1 时 Alpha 通道将被丢弃
        </v-alert>

        <v-alert type="info" variant="tonal" density="compact" rounded="lg" class="mb-2">
          仅作用于 Alpha（灰度 · Gamma 2.2）通道
        </v-alert>

        <v-alert type="info" variant="tonal" density="compact" rounded="lg">
          做夜光选择「灰度」，调整夜光强度仅需要调整「输出白点」，建议值：45–75
        </v-alert>
      </v-card-text>

      <v-divider />
      <v-card-actions class="px-5 py-3">
        <v-spacer />
        <v-btn variant="tonal" @click="show = false">取消</v-btn>
        <v-btn color="primary" @click="onSave">确定</v-btn>
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
