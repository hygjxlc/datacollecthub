// 批次增强 E2E 用例（四需求合并实现：状态类型/涵盖模态、编号规则、批量导入）
// 文件名 z- 前缀：必须晚于 flow.spec.js 执行（编号规则为全局单行且不可清空，
// 本套用例配置规则后 flow.spec.js 的建批次流程依赖兼容模式）。
// 全部场景兼容「规则已启用/未启用」两种基线：建批次编号按需动态读取，重跑安全。
const { test, expect } = require("@playwright/test");
const path = require("path");

// 批次编号唯一（DB UNIQUE），后 8 位时间戳保证多次运行不冲突
const RUN_ID = String(Date.now()).slice(-8);
const STATE_BATCH_NO = `B2026-E2E2-${RUN_ID}`;
const FILE_BUFFER = Buffer.alloc(5 * 1024 * 1024, 0xab);
const MANIFEST_HEADER = "目录,batch_no,device_no,device_model,station,license," +
  "sensitivity,owner_contact,is_synthetic,operating_condition,weather,数据对应设备:状态类型\n";

const state = {};
let originalRuleTemplate = null;   // NORULE 用例结束时恢复生产原规则

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// 按编号规则模板渲染期望正则（{YYYY}/{DEVICE_NO}/{SEQ:n} 占位符）
function expectedBatchNoPattern(template, deviceNo) {
  const year = new Date().getFullYear();
  const literal = template
    .replace("{YYYY}", "\u0001")
    .replace("{DEVICE_NO}", "\u0002")
    .replace(/\{SEQ:(\d+)\}/g, (_, n) => "\u0003" + n + "\u0004");
  return new RegExp("^" + escapeRegex(literal)
    .replace("\u0001", String(year))
    .replace("\u0002", deviceNo)
    .replace(/\u0003(\d+)\u0004/g, (_, n) => `\\d{${n}}`) + "$");
}

async function login(page, username, password) {
  await page.goto("/login");
  // 同一 test 内二次 login 时路由守卫会重定向到 /batches：清 token 后重回登录页
  if (!/\/login$/.test(page.url())) {
    await page.evaluate(() => localStorage.clear());
    await page.goto("/login");
  }
  await page.fill("[name=username]", username);
  await page.fill("[name=password]", password);
  await page.click("button:has-text('登录')");
  await page.waitForURL(/\/batches$/);
}

async function apiToken(request, username, password) {
  const resp = await request.post("/api/v1/auth/login", {
    data: { username, password },
  });
  expect(resp.status()).toBe(200);
  return (await resp.json()).access_token;
}

// 选择 数据对应设备:状态类型 下拉（任务 1 新增必填）
async function pickStateType(page, text) {
  await page.locator(".el-form-item", { hasText: "数据对应设备:状态类型" })
    .locator(".el-select").click();
  await page.locator(".el-select-dropdown__item:visible", { hasText: text }).first().click();
}

test.describe.serial("批次增强功能", () => {
  test("TC-BATCH-STATE：状态类型必填与涵盖模态展示", async ({ page, request }) => {
    // 1. 建批次（规则可能已启用：编号输入只读，编号由系统生成）
    await login(page, "zhang", "pass123");
    await page.click("button:has-text('新建批次')");
    await page.waitForURL(/\/batches\/new$/);
    const autoNo = await page.locator("[name=batch_no]").isDisabled();
    if (!autoNo) await page.fill("[name=batch_no]", STATE_BATCH_NO);
    await page.fill("[name=device_no]", "F02");
    await pickStateType(page, "光伏");
    await page.click("button:has-text('创建批次')");
    await expect(page.locator(".el-message--success", { hasText: "创建成功" })).toBeVisible();
    await page.waitForURL(/\/batches\/[0-9a-f-]+$/);
    state.batchId = page.url().split("/").pop();
    const token = await apiToken(request, "zhang", "pass123");
    const bResp = await request.get(`/api/v1/batches/${state.batchId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(bResp.status()).toBe(200);
    const batch = await bResp.json();
    state.batchNo = batch.batch_no;
    expect(batch.equipment_state_type).toBe("光伏");
    // 详情说明表出现状态类型「光伏」
    await expect(page.locator(".el-descriptions").getByText("光伏")).toBeVisible();

    // 2. 上传一个 .dat 文件（SCADA 模态）
    await page.click("button:has-text('上传文件')");
    await page.waitForURL(/\/batches\/.+\/upload$/);
    const FILENAME = `SCADA_F02_20250901_${RUN_ID}.dat`;
    await page.locator(".el-upload input[type='file']").setInputFiles({
      name: FILENAME, mimeType: "application/octet-stream", buffer: FILE_BUFFER,
    });
    const confirmBox = page.locator(".el-message-box");
    const uploadDone = page.locator(".el-message--success", { hasText: `${FILENAME} 上传完成` });
    const boxFirst = await Promise.race([
      confirmBox.waitFor({ state: "visible", timeout: 60000 }).then(() => true),
      uploadDone.waitFor({ state: "visible", timeout: 60000 }).then(() => false),
    ]);
    if (boxFirst) {
      await confirmBox.getByRole("button", { name: "继续上传" }).click();
    }
    await expect(uploadDone).toBeVisible();

    // 3. 详情页「涵盖模态数据」显示 SCADA（前端按 MODALITY_LABELS 译为「工艺参数」）
    await page.waitForURL(/\/batches\/[0-9a-f-]+$/);
    await expect(page.locator(".el-descriptions").getByText("工艺参数")).toBeVisible();

    // 4. 列表页该行显示状态类型「光伏」与模态标签「工艺参数」
    await page.goto("/batches");
    const row = page.locator(".el-table__body tr", { hasText: state.batchNo });
    await expect(row.getByText("光伏")).toBeVisible();
    await expect(row.getByText("工艺参数")).toBeVisible();
  });

  test("TC-BATCH-NORULE：编号规则配置与自动编号只读", async ({ page, request }) => {
    // 0. 记录生产原规则（管理员可能已配置），用例末尾恢复避免覆盖
    const adminToken = await apiToken(request, "admin", "admin123");
    const origResp = await request.get("/api/v1/batch-no-rule", {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    originalRuleTemplate = origResp.status() === 200
      ? ((await origResp.json()).template || null) : null;

    // 1. admin 配置规则（重跑时覆盖保存，幂等）
    await login(page, "admin", "admin123");
    await page.goto("/admin/batch-no-rule");
    await page.fill("[name=batch_no_template]", "B-{YYYY}-{SEQ:3}");
    await page.click("button:has-text('保存规则')");
    await expect(page.locator(".el-message--success", { hasText: "批次编号规则已保存" })).toBeVisible();
    // 实时预览渲染示例编号
    await expect(page.locator(".el-tag", { hasText: /^B-\d{4}-001$/ })).toBeVisible();

    // 2. 普通用户建批次：编号输入框禁用（只读），提交后编号自动生成
    await login(page, "zhang", "pass123");
    await page.click("button:has-text('新建批次')");
    await page.waitForURL(/\/batches\/new$/);
    await expect(page.locator("[name=batch_no]")).toBeDisabled();
    await page.fill("[name=device_no]", "F03");
    await pickStateType(page, "风电");
    await page.click("button:has-text('创建批次')");
    await expect(page.locator(".el-message--success", { hasText: "创建成功" })).toBeVisible();
    await page.waitForURL(/\/batches\/[0-9a-f-]+$/);
    const batchId = page.url().split("/").pop();
    const token = await apiToken(request, "zhang", "pass123");
    const bResp = await request.get(`/api/v1/batches/${batchId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(bResp.status()).toBe(200);
    const batch = await bResp.json();
    const year = new Date().getFullYear();
    expect(batch.batch_no).toMatch(new RegExp(`^B-${year}-\\d{3}$`));
    state.autoBatchNo = batch.batch_no;

    // 3. 列表页出现自动编号批次
    await page.goto("/batches");
    await expect(page.locator(".el-table__body").getByText(state.autoBatchNo)).toBeVisible();

    // 4. 恢复生产原规则（E2E 不覆盖管理员配置；原无规则时保留本用例配置）
    if (originalRuleTemplate) {
      const restoreResp = await request.put("/api/v1/admin/batch-no-rule", {
        data: { template: originalRuleTemplate },
        headers: { Authorization: `Bearer ${adminToken}` },
      });
      expect(restoreResp.status()).toBe(200);
    }
  });

  test("TC-BATCH-IMP：批量导入成功（模板下载+zip 直传+异步导入）", async ({ page, request }) => {
    await login(page, "zhang", "pass123");
    await page.click("button:has-text('批量导入')");
    await page.waitForURL(/\/batch-imports$/);

    // 1. 下载模板：manifest.csv（UTF-8 BOM）
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.click("button:has-text('下载模板')"),
    ]);
    expect(download.suggestedFilename()).toBe("manifest.csv");

    // 2. 构造 zip：manifest.csv + 1 批次目录（规则已启用，batch_no 留空自动生成；
    //    附加列「采集时长」验证扩展字段 extras 入库与详情页展示）
    const JSZip = require("jszip");
    const zip = new JSZip();
    const dir = `E2E_IMP_${RUN_ID}`;
    zip.file("manifest.csv", "\uFEFF" + MANIFEST_HEADER.trimEnd() + ",采集时长\n" +
      `${dir},,F03,,wind,内部专用,内部,,0,正常,晴,风电,2小时\n`);
    zip.file(`${dir}/imp1_${RUN_ID}.dat`, "import-payload");
    const zipBuf = await zip.generateAsync({ type: "nodebuffer" });

    // 3. 上传 zip（分片直传 MinIO）→ 自动提交导入任务 → 轮询终态
    await page.locator(".el-upload input[type='file']").setInputFiles({
      name: `batch-import-${RUN_ID}.zip`,
      mimeType: "application/zip",
      buffer: zipBuf,
    });
    await expect(page.locator(".el-message--success", { hasText: "上传完成" })).toBeVisible();
    await expect(page.locator(".el-message--success", { hasText: "导入任务已提交" })).toBeVisible();
    const progressCard = page.locator(".el-card", { hasText: "导入进度" });
    await expect(progressCard.getByText("succeeded")).toBeVisible({ timeout: 60000 });
    await expect(page.locator(".el-table__body").getByText(/1 \/ 1 批次/).first()).toBeVisible();

    // 4. 报告含自动生成的批次编号（按当前生效规则渲染期望），批次列表出现该批次
    const importNo = (await progressCard.locator(".el-tag--success").first().textContent()).trim();
    const zhangToken = await apiToken(request, "zhang", "pass123");
    const ruleResp = await request.get("/api/v1/batch-no-rule", {
      headers: { Authorization: `Bearer ${zhangToken}` },
    });
    const ruleTemplate = ruleResp.status() === 200
      ? ((await ruleResp.json()).template || "B-{YYYY}-{SEQ:3}")
      : "B-{YYYY}-{SEQ:3}";
    expect(importNo).toMatch(expectedBatchNoPattern(ruleTemplate, "F03"));
    await page.goto("/batches");
    await expect(page.locator(".el-table__body").getByText(importNo)).toBeVisible();

    // 5. 详情页展示扩展字段「采集时长」（附加列入库 extras）
    const row = page.locator(".el-table__body tr", { hasText: importNo });
    await row.getByRole("button", { name: "详情" }).click();
    await page.waitForURL(/\/batches\/[0-9a-f-]+$/);
    await expect(page.locator(".el-descriptions").getByText("采集时长: 2小时")).toBeVisible();
  });

  test("TC-BATCH-IMP-FAIL：批量导入预检失败（全有或全无）", async ({ page, request }) => {
    await login(page, "zhang", "pass123");
    await page.goto("/batch-imports");

    // manifest 缺 device_no 列 → 解析阶段报错，任务 failed，不创建任何批次
    const JSZip = require("jszip");
    const zip = new JSZip();
    const dir = `E2E_BAD_${RUN_ID}`;
    const badNo = `B2026-BAD-${RUN_ID}`;
    zip.file("manifest.csv",
      "\uFEFF目录,batch_no,license,sensitivity,is_synthetic,数据对应设备:状态类型\n" +
      `${dir},${badNo},内部专用,内部,0,风电\n`);
    zip.file(`${dir}/bad.dat`, "x");
    const zipBuf = await zip.generateAsync({ type: "nodebuffer" });

    await page.locator(".el-upload input[type='file']").setInputFiles({
      name: `bad-import-${RUN_ID}.zip`,
      mimeType: "application/zip",
      buffer: zipBuf,
    });
    await expect(page.locator(".el-message--success", { hasText: "上传完成" })).toBeVisible();
    const progressCard = page.locator(".el-card", { hasText: "导入进度" });
    await expect(progressCard.getByText("failed")).toBeVisible({ timeout: 60000 });
    await expect(progressCard).toContainText("预检错误");
    await expect(progressCard).toContainText("device_no");

    // 全有或全无：批次列表无该编号批次
    const token = await apiToken(request, "zhang", "pass123");
    const listResp = await request.get("/api/v1/batches?page_size=100", {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(listResp.status()).toBe(200);
    const items = (await listResp.json()).items;
    expect(items.some((b) => b.batch_no === badNo)).toBe(false);
  });
});
