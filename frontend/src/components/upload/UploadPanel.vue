<script>
// 会话级缓存：deviceNo → "ok"（可上传，无需再查）| Promise<boolean>（在途查询/确认）
const pointDictChecked = new Map();
</script>

<script setup>
import { ref } from "vue";
import axios from "axios";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRouter } from "vue-router";
import api from "../../api";
import { useUploadStore } from "../../stores/upload";
import UploadTaskItem from "./UploadTaskItem.vue";

const PART_SIZE = 10 * 1024 * 1024;   // 与后端 PART_SIZE 一致（10MB/片）

const props = defineProps({
  batchId: { type: String, required: true },
  deviceNo: { type: String, default: "" },
});
const emit = defineEmits(["uploaded"]);

const uploadStore = useUploadStore();
const fileInput = ref(null);
const router = useRouter();

// 未完成任务列表（页面加载时从 localStorage 恢复，TC-UP-004）
const pendingTasks = uploadStore.forBatch(props.batchId);

// 与后端 EXT_TO_MODALITY 保持一致
const EXT_TO_MODALITY = { ".dat": "SCADA", ".bin": "VIB", ".wav": "AUD",
  ".flac": "AUD", ".mp3": "AUD", ".irx": "IR", ".png": "IR", ".jpg": "CAM",
  ".mp4": "VID", ".pdf": "TXT", ".doc": "TXT", ".docx": "TXT",
  ".csv": "SCADA", ".xlsx": "RPT" };

function inferModality(filename) {
  const dot = filename.lastIndexOf(".");
  const ext = dot >= 0 ? filename.slice(dot).toLowerCase() : "";
  return EXT_TO_MODALITY[ext] || "SCADA";
}

async function ensurePointDict(fileName) {
  // 半约束：SCADA 模态且该设备无测点字典 → 弹确认（可跳过）
  if (inferModality(fileName) !== "SCADA" || !props.deviceNo) return true;
  if (pointDictChecked.get(props.deviceNo) === "ok") return true;

  const inflight = pointDictChecked.get(props.deviceNo);
  if (inflight) return inflight;   // 复用同一次查询/确认，避免并发重复弹窗

  const p = (async () => {
    try {
      const { data } = await api.get("/point-dicts",
        { params: { device_no: props.deviceNo } });
      if (data.items.length > 0) {
        pointDictChecked.set(props.deviceNo, "ok");
        return true;
      }
    } catch { return true; }   // 查询失败放行上传（全局拦截器已提示错误）

    try {
      await ElMessageBox.confirm(
        `当前设备 ${props.deviceNo} 未配置测点字典，上传的 SCADA 通道号将无法被下游解释。是否继续上传？`,
        "提示", {
          confirmButtonText: "继续上传",
          cancelButtonText: "去配置",
          type: "warning",
          distinguishCancelAndClose: true,
        });
      pointDictChecked.set(props.deviceNo, "ok");   // 本次会话后续文件不再弹
      return true;
    } catch (action) {
      // 仅点「去配置」跳转；X/ESC 关闭与其他异常仅中断当前上传流程，不跳转
      if (action === "cancel") {
        router.push("/devices?tab=point-dicts");
      }
      pointDictChecked.delete(props.deviceNo);   // 取消不缓存，下次重新询问
      return false;
    }
  })();

  pointDictChecked.set(props.deviceNo, p);
  return p;
}

function pickFiles() {
  fileInput.value.click();
}

async function handleFiles(evt) {
  const files = Array.from(evt.target.files || []);
  evt.target.value = "";   // 允许重复选择同一文件
  for (const file of files) {
    if (!(await ensurePointDict(file.name))) return;
    await startUpload(file);
  }
  emit("uploaded");
}

async function startUpload(file) {
  const existing = uploadStore.forBatch(props.batchId)
    .find((t) => t.fileName === file.name && t.size === file.size);
  const { data } = await api.post(`/batches/${props.batchId}/files/upload/init`, {
    filename: file.name, file_size: file.size,
  });
  const task = existing
    ? { ...existing, uploadId: data.upload_id, parts: data.parts, objectKey: data.object_key }
    : { batchId: props.batchId, uploadId: data.upload_id, objectKey: data.object_key,
        parts: data.parts, done: [], fileName: file.name, size: file.size,
        status: "uploading" };
  uploadStore.save();
  const idx = uploadStore.tasks.findIndex((t) => t.uploadId === task.uploadId);
  if (idx === -1) uploadStore.add(task);

  try {
    for (const p of task.parts) {
      if (task.done.includes(p.part_number)) continue;   // 断点续传：跳过已完成分片
      const offset = (p.part_number - 1) * PART_SIZE;
      const blob = file.slice(offset, offset + PART_SIZE);
      await axios.put(p.url, blob);                      // 直传 MinIO，不挂拦截器
      task.done.push(p.part_number);
      uploadStore.save();                                // 每片完成即持久化
    }
    await api.post(`/batches/${props.batchId}/files/upload/${data.upload_id}/complete`, {
      object_key: data.object_key, filename: file.name, file_size: file.size,
      parts: data.parts.map((p) => ({ part_number: p.part_number, etag: "" })),
    });
    uploadStore.remove(data.upload_id);
    ElMessage.success(`${file.name} 上传完成`);
  } catch {
    uploadStore.updateStatus(task.uploadId, "paused");
    ElMessage.warning(`${file.name} 上传中断，可重新选择同一文件续传`);
  }
}

function cancelTask(task) {
  uploadStore.remove(task.uploadId);
}
</script>

<template>
  <div class="upload-panel">
    <el-upload drag multiple :show-file-list="false" :auto-upload="false"
               :on-change="(f) => handleFiles({ target: { files: [f.raw], value: '' } })">
      <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
      <template #tip>
        <div class="el-upload__tip">
          中断后重新选择同一文件可断点续传
        </div>
      </template>
    </el-upload>

    <div v-if="pendingTasks.length" class="pending">
      <h4>未完成任务（可续传）</h4>
      <UploadTaskItem
        v-for="t in pendingTasks"
        :key="t.uploadId"
        :task="t"
        @cancel="cancelTask"
      />
      <el-button type="primary" @click="pickFiles">选择文件续传</el-button>
      <input ref="fileInput" type="file" multiple class="hidden" @change="handleFiles" />
    </div>
  </div>
</template>

<style scoped>
.upload-panel {
  max-width: 720px;
}
.pending {
  margin-top: 16px;
}
.hidden {
  display: none;
}
</style>
