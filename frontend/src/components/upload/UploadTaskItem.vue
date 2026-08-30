<script setup>
import { computed } from "vue";

const props = defineProps({
  task: { type: Object, required: true },
});
const emit = defineEmits(["cancel"]);

const progress = computed(() =>
  props.task.parts.length
    ? Math.round((props.task.done.length / props.task.parts.length) * 100)
    : 0
);
</script>

<template>
  <div class="task-item">
    <span class="name">{{ task.fileName }}</span>
    <el-progress class="bar" :percentage="progress"
                 :status="task.status === 'paused' ? 'warning' : undefined" />
    <span class="status">{{ task.status === "paused" ? "已中断" : `${task.done.length}/${task.parts.length} 片` }}</span>
    <el-button link type="danger" @click="emit('cancel')">移除</el-button>
  </div>
</template>

<style scoped>
.task-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 0;
}
.name {
  width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bar {
  flex: 1;
}
.status {
  width: 90px;
  color: #909399;
  font-size: 12px;
}
</style>
