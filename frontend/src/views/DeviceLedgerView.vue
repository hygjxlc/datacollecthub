<script setup>
import { ref, watch } from "vue";
import { useRoute } from "vue-router";
import NameplateTab from "../components/device/NameplateTab.vue";
import PointDictTab from "../components/device/PointDictTab.vue";

// 设备台账：单页 2 Tab，支持 ?tab=point-dicts query 定位（SCADA 半约束「去配置」跳转）
const route = useRoute();
const TAB_NAMES = { "nameplate": "铭牌台账", "point-dicts": "测点字典" };
const activeTab = ref(TAB_NAMES[route.query.tab] || "铭牌台账");

watch(() => route.query.tab, (tab) => {
  if (TAB_NAMES[tab]) activeTab.value = TAB_NAMES[tab];
});
</script>

<template>
  <div class="page">
    <h3 class="title">设备台账</h3>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="铭牌台账" name="铭牌台账">
        <NameplateTab />
      </el-tab-pane>
      <el-tab-pane label="测点字典" name="测点字典">
        <PointDictTab />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.title {
  margin-bottom: 16px;
}
</style>
