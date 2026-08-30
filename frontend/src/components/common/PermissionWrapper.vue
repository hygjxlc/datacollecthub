<script setup>
import { computed } from "vue";
import { useAuthStore } from "../../stores/auth";

// 按 role 与归属（本人上传/创建）条件渲染按钮，仅控制显隐，不是安全边界（SRS 3.2）
const props = defineProps({
  ownerId: { type: String, default: "" },
});

const auth = useAuthStore();
const can = computed(
  () => auth.isAdmin || (!!props.ownerId && props.ownerId === auth.user?.id)
);
</script>

<template>
  <slot v-if="can" />
</template>
