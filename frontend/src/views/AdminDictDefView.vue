<script setup>
import { ref } from "vue";
import FaultTypeDefTab from "../components/admin/FaultTypeDefTab.vue";
import ModalParamDefTab from "../components/admin/ModalParamDefTab.vue";

// 字典管理（admin，Phase 0）：故障类型字典 + 模态参数 Schema 字典
const activeTab = ref("故障类型");
</script>

<template>
  <div class="page">
    <h3 class="title">字典管理</h3>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="故障类型" name="故障类型">
        <FaultTypeDefTab />
      </el-tab-pane>
      <el-tab-pane label="模态参数" name="模态参数">
        <ModalParamDefTab />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.title {
  margin-bottom: 16px;
}
</style>
