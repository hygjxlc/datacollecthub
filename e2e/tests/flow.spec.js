// E2E 核心流程用例（《DataCollectHub_系统级E2E测试方案》第 4-7 章精选）
// 前置条件：仓库根目录 `docker compose up -d --build` 完成，seed 基线账号就绪。
// 覆盖：TC-AUTH-001 登录、TC-BATCH-001 建批次、TC-UP-001/003 分片上传、
//       TC-META-001 元数据补填（日历选时间/采样周期双栏/时区默认 +08:00）、
//       TC-PERM-002 同单位他人隔离、TC-DOWNLOAD 检索页批量下载、
//       TC-INT-001/006 集成接口（nginx 外部 404 / 容器内 200）
const { test, expect } = require("@playwright/test");
const { execSync } = require("child_process");
const path = require("path");

// 批次编号唯一（DB UNIQUE），后 8 位时间戳保证多次运行不冲突
const RUN_ID = String(Date.now()).slice(-8);
const BATCH_NO = `B2025-E2E-${RUN_ID}`;
// 文件名含时间戳：object_key 含 filename，且原始区永不覆盖（重跑同名会被 422 拒绝）
const FILENAME = `SCADA_F01_20250615_1423_${RUN_ID}.dat`;
const FILENAME2 = `SCADA_F01_20250615_1523_${RUN_ID}.dat`;
// 5MB 单分片（PART_SIZE=10MB），跳过跨片断言、加速用例
const FILE_BUFFER = Buffer.alloc(5 * 1024 * 1024, 0xab);

const state = {};   // 用例间共享：batchId / fileId

async function login(page, username, password) {
  await page.goto("/login");
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

test.describe.serial("DataCollectHub 核心流程", () => {
  test("TC-AUTH/BATCH/UP/META：对接人完整流程（登录→建批次→上传→补填元数据）", async ({ page, request }) => {
    // 1. 登录（TC-AUTH-001）
    await login(page, "zhang", "pass123");
    await expect(page.getByText("新建批次")).toBeVisible();

    // 2. 新建批次（TC-BATCH-001）
    await page.click("button:has-text('新建批次')");
    await page.waitForURL(/\/batches\/new$/);
    await page.fill("[name=batch_no]", BATCH_NO);
    await page.fill("[name=device_no]", "F01");
    await page.fill("[name=station]", "辉腾梁风电场");
    await page.click("button:has-text('创建批次')");
    await expect(page.locator(".el-message--success", { hasText: "创建成功" })).toBeVisible();
    await page.waitForURL(/\/batches\/[0-9a-f-]+$/);
    state.batchId = page.url().split("/").pop();
    // 批次说明表内出现批次编号（避免与标题/提示消息重复匹配）
    await expect(page.locator(".el-descriptions").getByText(BATCH_NO)).toBeVisible();

    // 3. 上传 5MB 文件（TC-UP-001/003 分片直传）
    await page.click("button:has-text('上传文件')");
    await page.waitForURL(/\/batches\/.+\/upload$/);
    await page.locator(".el-upload input[type='file']").setInputFiles({
      name: FILENAME,
      mimeType: "application/octet-stream",
      buffer: FILE_BUFFER,
    });
    // 半约束：无测点字典时弹确认框（历史数据已有字典则不弹）
    // 两个等待竞速：弹窗先出现 → 点"继续上传"；上传成功消息先出现 → 无弹窗，直接继续
    const confirmBox = page.locator(".el-message-box");
    const uploadDone = page.locator(".el-message--success", { hasText: `${FILENAME} 上传完成` });
    const boxFirst = await Promise.race([
      confirmBox.waitFor({ state: "visible", timeout: 30000 }).then(() => true),
      uploadDone.waitFor({ state: "visible", timeout: 30000 }).then(() => false),
    ]);
    if (boxFirst) {
      await confirmBox.getByRole("button", { name: "继续上传" }).click();
    }
    await expect(uploadDone).toBeVisible();
    // 上传完成自动回批次详情页并刷新文件清单
    await page.waitForURL(/\/batches\/[0-9a-f-]+$/);
    await expect(page.locator(".el-table__body").getByText(FILENAME)).toBeVisible();

    // 4. 补填元数据：日历选择采集时间 + 采样周期双栏（时区由系统默认 +08:00，TC-META-001）
    const rowEdit = page.locator(".el-table__body").getByRole("button", { name: "编辑" });
    await rowEdit.click();
    const dialog = page.locator(".el-dialog");
    await expect(dialog).toBeVisible();
    await dialog.locator("[name=start_time]").fill("2025-06-15 14:23:08");
    await dialog.locator("[name=start_time]").press("Enter");
    await dialog.locator("[name=sample_value]").fill("1");
    // el-select 输入框被 placeholder 覆盖，force 点击仍触发下拉（元素本身可见）
    await dialog.locator("[name=sample_unit]").click({ force: true });
    await page.locator(".el-select-dropdown__item", { hasText: /^s$/ }).click();
    await dialog.locator("button:has-text('保存')").click();
    await expect(page.locator(".el-message--success", { hasText: "元数据已保存" })).toBeVisible();
    await expect(page.locator(".el-table__body")).toContainText("2025-06-15 14:23:08");

    // 取 file_id 供权限用例使用
    const token = await apiToken(request, "zhang", "pass123");
    const listResp = await request.get(`/api/v1/files?batch_no=${encodeURIComponent(BATCH_NO)}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(listResp.status()).toBe(200);
    const files = (await listResp.json()).items;
    expect(files.length).toBe(1);
    state.fileId = files[0].id;
  });

  test("TC-PERM-002：同单位他人文件不可编辑删除，后端 API 强制 403", async ({ page, request }) => {
    // li 与 zhang 同属辉腾梁风电场，但非文件归属人
    await login(page, "li", "pass123");
    await page.goto(`/batches/${state.batchId}`);
    await expect(page.locator(".el-descriptions").getByText(BATCH_NO)).toBeVisible();

    const body = page.locator(".el-table__body");
    await expect(body.getByText(FILENAME)).toBeVisible();
    // 操作列仅剩"下载"，无"编辑/删除"
    await expect(body.getByRole("button", { name: "编辑" })).toHaveCount(0);
    await expect(body.getByRole("button", { name: "删除" })).toHaveCount(0);

    // 绕过前端直接调 API，后端仍强制 403（不泄露归属）
    const token = await apiToken(request, "li", "pass123");
    const resp = await request.put(`/api/v1/files/${state.fileId}`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { sample_period: "1s" },
    });
    expect(resp.status()).toBe(403);
  });

  test("TC-INT-001：集成接口经 nginx 对外 404（内网隔离第一层）", async ({ request }) => {
    const resp = await request.get("/api/v1/integration/files/ids");
    expect(resp.status()).toBe(404);
  });

  test("TC-INT-006：集成接口容器内直连可达（无认证只读）", async () => {
    test.skip(!dockerReady(), "docker 未运行，跳过容器内验证");
    // backend 镜像为 python:3.11-slim（无 curl），用 urllib 验证容器内可达性
    const out = execSync(
      "docker compose exec -T backend python -c " +
      "\"import urllib.request;print(urllib.request.urlopen(" +
      "'http://localhost:8080/api/v1/integration/files/ids').status)\"",
      { cwd: path.resolve(__dirname, "../.."), encoding: "utf-8", timeout: 60000 }
    );
    expect(out.trim()).toBe("200");
  });

  test("TC-BATCH-COPY/META-COPY：批次复制新建预填 + 同批次文件元数据复制", async ({ page, request }) => {
    const COPY_BATCH_NO = `${BATCH_NO}-C`;

    // 1. 列表行内"复制新建"→ 跳转预填新建页（batch_no 清空，其余字段带入）
    await login(page, "zhang", "pass123");
    const body = page.locator(".el-table__body");
    await body.locator("tr", { hasText: BATCH_NO }).getByRole("button", { name: "复制新建" }).click();
    await page.waitForURL((url) =>
      url.pathname === "/batches/new" && !!url.searchParams.get("copy_from"));
    await expect(page.locator(".el-alert")).toContainText("已从批次");
    await expect(page.locator("[name=batch_no]")).toHaveValue("");
    await expect(page.locator("[name=device_no]")).toHaveValue("F01");
    await expect(page.locator("[name=station]")).toHaveValue("辉腾梁风电场");

    // 2. 改 batch_no 提交（新批次唯一编号）
    await page.fill("[name=batch_no]", COPY_BATCH_NO);
    await page.click("button:has-text('创建批次')");
    await expect(page.locator(".el-message--success", { hasText: "创建成功" })).toBeVisible();
    await page.waitForURL(/\/batches\/[0-9a-f-]+$/);

    // 3. 回原批次（用例 1 已含元数据文件）上传第二个文件
    await page.goto(`/batches/${state.batchId}`);
    await expect(body.getByText(FILENAME)).toBeVisible();
    await page.click("button:has-text('上传文件')");
    await page.waitForURL(/\/batches\/.+\/upload$/);
    await page.locator(".el-upload input[type='file']").setInputFiles({
      name: FILENAME2, mimeType: "application/octet-stream", buffer: FILE_BUFFER,
    });
    // 半约束：无测点字典时弹确认框（与用例 1 同竞速处理）
    const confirmBox2 = page.locator(".el-message-box");
    const uploadDone2 = page.locator(".el-message--success", { hasText: `${FILENAME2} 上传完成` });
    const boxFirst2 = await Promise.race([
      confirmBox2.waitFor({ state: "visible", timeout: 60000 }).then(() => true),
      uploadDone2.waitFor({ state: "visible", timeout: 60000 }).then(() => false),
    ]);
    if (boxFirst2) {
      await confirmBox2.getByRole("button", { name: "继续上传" }).click();
    }
    await expect(uploadDone2).toBeVisible();
    await page.waitForURL(/\/batches\/[0-9a-f-]+$/);
    await expect(body.getByText(FILENAME2)).toBeVisible();

    // 4. 编辑新文件 → "复制自同批次文件"下拉选源（用例 1 已填元数据的文件）
    await body.locator("tr", { hasText: FILENAME2 }).getByRole("button", { name: "编辑" }).click();
    const dialog = page.locator(".el-dialog");
    await expect(dialog).toBeVisible();
    await dialog.locator(".el-select").first().click();
    await page.locator(".el-select-dropdown__item", { hasText: FILENAME }).click();
    await expect(dialog.locator("[name=start_time]")).toHaveValue("2025-06-15 14:23:08");
    await expect(dialog.locator("[name=sample_value]")).toHaveValue("1");
    // element-plus 2.14 select 输入框值异步渲染，断言选中文本更稳健
    await expect(dialog.locator(".el-select__selected-item", { hasText: /^s$/ })).toBeVisible();

    // 5. 微调后保存（表格仅展示开始时间列，end_time 落库用 API 验证）
    await dialog.locator("[name=end_time]").fill("2025-06-15 15:23:08");
    await dialog.locator("[name=end_time]").press("Enter");
    await dialog.locator("button:has-text('保存')").click();
    await expect(page.locator(".el-message--success", { hasText: "元数据已保存" })).toBeVisible();
    await expect(body).toContainText("2025-06-15 14:23:08");
    const token = await apiToken(request, "zhang", "pass123");
    const listResp = await request.get(`/api/v1/files?batch_no=${encodeURIComponent(BATCH_NO)}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(listResp.status()).toBe(200);
    const f2 = (await listResp.json()).items.find((f) => f.filename === FILENAME2);
    expect(f2.end_time).toBe("2025-06-15 15:23:08");

    // 6. 文件详情页"补填元数据"入口同样支持复制（同批次源）
    await page.goto(`/files/${f2.id}`);
    await page.click("button:has-text('补填元数据')");
    await expect(dialog).toBeVisible();
    await dialog.locator(".el-select").first().click();
    await page.locator(".el-select-dropdown__item", { hasText: FILENAME }).click();
    await expect(dialog.locator("[name=start_time]")).toHaveValue("2025-06-15 14:23:08");
    await dialog.locator("button:has-text('取消')").click();
  });

  test("TC-DOWNLOAD：检索页勾选多个文件，打包下载与逐个下载", async ({ page, context }) => {
    await login(page, "zhang", "pass123");
    await page.goto("/files");

    // 1. 按批次检索到用例 1/5 上传的 2 个文件
    await page.fill("[name=batch_no]", BATCH_NO);
    await page.click("button:has-text('查询')");
    const body = page.locator(".el-table__body");
    await expect(body.getByText(FILENAME)).toBeVisible();
    await expect(body.getByText(FILENAME2)).toBeVisible();

    // 2. 表头全选 2 行（定位表头 wrapper 内 checkbox，避免 fixed 列双渲染干扰）
    await page.locator(".el-table__header-wrapper .el-checkbox").first().click();
    await expect(page.locator(".selected")).toContainText("已选 2 项");

    // 3. 打包下载：zip 文件名 datacollecthub-YYYYMMDD.zip
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.click("button:has-text('打包下载')"),
    ]);
    expect(download.suggestedFilename()).toMatch(/^datacollecthub-\d{8}\.zip$/);
    await expect(page.locator(".el-message--success", { hasText: "已打包下载" })).toBeVisible();

    // 4. 逐个下载：2 个单文件打包（原始数据+元数据）依次触发，zip 名 = 文件名去扩展名
    const downloads = [];
    page.on("download", (d) => downloads.push(d));
    await page.click("button:has-text('逐个下载')");
    // 公网下载速度波动，先等 download 事件（事件驱动最可靠），再断言成功消息
    await expect.poll(() => downloads.length, { timeout: 60000 }).toBe(2);
    await expect(page.locator(".el-message--success", { hasText: "已下载 2 个文件（含元数据）" })).toBeVisible();
    expect(downloads.map((d) => d.suggestedFilename()).sort()).toEqual([
      `${FILENAME.replace(/\.dat$/, "")}.zip`,
      `${FILENAME2.replace(/\.dat$/, "")}.zip`,
    ].sort());
  });

  test("TC-DEVICES：设备台账录入三类信息 + 半约束 + 打包下载元数据联动", async ({ page, request }) => {
    // 1. 清理 F01 测点字典（保证半约束弹窗场景可重现）与已有铭牌（保证用例可重复运行）
    const token = await apiToken(request, "zhang", "pass123");
    const pdResp = await request.get("/api/v1/point-dicts?device_no=F01", {
      headers: { Authorization: `Bearer ${token}` },
    });
    for (const p of (await pdResp.json()).items) {
      await request.delete(`/api/v1/point-dicts/${p.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    }
    const npResp = await request.get("/api/v1/nameplates/by-device/F01", {
      headers: { Authorization: `Bearer ${token}` },
    });
    for (const n of (await npResp.json()).items) {
      await request.delete(`/api/v1/nameplates/${n.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    }
    const evResp = await request.get("/api/v1/events?device_no=F01", {
      headers: { Authorization: `Bearer ${token}` },
    });
    for (const e of (await evResp.json()).items) {
      await request.delete(`/api/v1/events/${e.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    }

    // 2. 登录 → 上传 SCADA 文件（无测点字典 → 半约束弹窗 → 去配置）
    await login(page, "zhang", "pass123");
    await page.goto(`/batches/${state.batchId}/upload`);
    // 等待批次详情加载完成（device_no 就绪后 UploadPanel 才会触发半约束检查）
    await expect(page.locator(".el-page-header")).toContainText("F01");
    const FILENAME3 = `SCADA_F01_20250615_1623_${RUN_ID}.dat`;
    await page.locator(".el-upload input[type='file']").setInputFiles({
      name: FILENAME3, mimeType: "application/octet-stream", buffer: FILE_BUFFER,
    });
    const box = page.locator(".el-message-box");
    await expect(box).toBeVisible();
    await expect(box).toContainText("未配置测点字典");
    await box.getByRole("button", { name: "去配置" }).click();
    await page.waitForURL(/\/devices\?tab=point-dicts/);

    // 3. Tab2 录入测点字典
    // 顶部过滤默认取 sorted(device-nos)[0]（生产库可能有 B001 等设备），显式切到 F01
    await page.locator(".toolbar .el-select").click();
    await page.locator(".el-select-dropdown__item:visible", { hasText: /^F01$/ }).click();
    await page.click("button:has-text('新增测点')");
    // Element Plus dialog 关闭后 DOM 残留（非 destroy-on-close），用 :visible 定位当前对话框
    let dialog = page.locator(".el-dialog:visible");
    await expect(dialog).toBeVisible();
    // 表单设备号默认继承过滤设备，再显式选择 F01 保证联动断言确定性
    await dialog.locator(".el-select").first().click();
    await page.locator(".el-select-dropdown__item:visible", { hasText: /^F01$/ }).click();
    await dialog.locator("[name=channel_no]").fill("CH1");
    await dialog.locator("[name=pd_name]").fill("齿轮箱轴承温度");
    await dialog.locator("[name=unit]").fill("℃");
    await dialog.locator("button:has-text('保存')").click();
    await expect(page.locator(".el-message--success", { hasText: "测点已创建" })).toBeVisible();
    await expect(page.locator(".el-table__body").getByText("CH1")).toBeVisible();

    // 4. Tab1 录入铭牌
    await page.click(".el-tabs__item:has-text('铭牌台账')");
    await page.click("button:has-text('新增铭牌')");
    dialog = page.locator(".el-dialog:visible");
    await expect(dialog).toBeVisible();
    await dialog.locator("[name=device_no]").fill("F01");
    await dialog.locator("[name=device_model]").fill("金风 GW82/1500");
    await dialog.locator("[name=bearing_model]").fill("SKF 240/600");
    await dialog.locator("button:has-text('保存')").click();
    await expect(page.locator(".el-message--success", { hasText: "铭牌已创建" })).toBeVisible();

    // 5. 左侧菜单进入事件记录页录入事件（关联用例 1 的文件）
    await page.click(".el-menu-item:has-text('事件记录')");
    await page.waitForURL(/\/events/);
    await page.click("button:has-text('新增事件')");
    dialog = page.locator(".el-dialog:visible");
    await expect(dialog).toBeVisible();
    await dialog.locator("[name=ev_device_no]").click({ force: true });
    await page.locator(".el-select-dropdown__item:visible", { hasText: /^F01$/ }).click();
    await dialog.locator("[name=event_time]").fill("2025-06-15 14:23:08");
    await dialog.locator("[name=event_time]").press("Enter");
    await dialog.locator("[name=event_type]").fill("齿轮箱/轴承/磨损");
    await dialog.locator("[name=ev_form_severity]").click({ force: true });
    await page.locator(".el-select-dropdown__item:visible", { hasText: /^报警$/ }).click();
    await dialog.locator("[name=ev_description]").fill("齿轮箱轴承温度持续升高至 85℃，触发报警停机");
    await dialog.locator("[name=related_files]").click({ force: true });
    await page.locator(".el-select-dropdown__item:visible", { hasText: FILENAME }).first().click();
    await dialog.locator("button:has-text('保存')").click();
    await expect(page.locator(".el-message--success", { hasText: "事件已创建" })).toBeVisible();
    await expect(page.locator(".el-table__body").getByText("齿轮箱/轴承/磨损")).toBeVisible();

    // 6. 打包下载：解压断言元数据 JSON 含三类台账
    const JSZip = require("jszip");
    const resp = await request.post("/api/v1/files/batch-download", {
      headers: { Authorization: `Bearer ${token}` },
      data: { ids: [state.fileId] },
    });
    expect(resp.status()).toBe(200);
    const zip = await JSZip.loadAsync(await resp.body());
    const meta = JSON.parse(await zip
      .file(`${FILENAME.replace(/\.dat$/, "")}/${FILENAME}.json`).async("string"));
    expect(meta.nameplate.device_no).toBe("F01");
    expect(meta.nameplate.bearing_model).toBe("SKF 240/600");
    expect(meta.point_dicts.length).toBeGreaterThan(0);
    expect(meta.point_dicts[0].channel_no).toBe("CH1");
    expect(meta.related_events.length).toBe(1);
    expect(meta.related_events[0].severity).toBe("报警");
    expect(meta.related_events[0].related_files).toEqual([]);
  });
});

function dockerReady() {
  try {
    const out = execSync("docker compose ps --status running backend", {
      cwd: path.resolve(__dirname, "../.."), encoding: "utf-8", timeout: 15000,
    });
    // 新版 docker：backend 未运行也返回 exit 0 并打印 "service backend is not running"，
    // 必须解析输出判断，否则 TC-INT-006 不会按设计跳过
    return /backend/.test(out) && !/is not running/i.test(out);
  } catch {
    return false;
  }
}
