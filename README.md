# DataCollectHub 原始数据采集入库系统

面向风电场/光伏站数据对接人与 FDL 引擎的原始数据采集入库系统：对接人创建批次、分片直传 MinIO、补填元数据、导出登记表；FDL 引擎经内网集成接口无认证拉取元数据与原始对象。

> 规格依据：`docs/spec/原始数据采集入库系统_软件需求规格说明书_SRS.md`（V1.1）
> 架构依据：`docs/design/DataCollectHub_系统架构设计.md`
> E2E 方案：`docs/test/DataCollectHub_系统级E2E测试方案.md`

## 功能清单（SRS F1~F8）

| 编号 | 功能 | 说明 |
|------|------|------|
| F1 | 认证与权限 | 登录/JWT/修改密码；停用即时失效（每次请求校验 is_active） |
| F2 | 单位与用户管理 | admin 专属：单位/用户 CRUD、重置密码、停用启用、审计查询 |
| F3 | 批次管理 | 批次说明表 10 字段；org 过滤、归属校验（创建者可编辑/删除）、审计 |
| F4 | 分片上传 | presigned 分片直传 MinIO（10MB/片）+ compose 合并；断点续传（localStorage 任务队列） |
| F5/F6 | 元数据 | 手动补填（时区必填联动校验）；批次字段快照自动继承（修改批次不追溯） |
| F7 | 检索与导出 | 7 条件组合检索；登记表 Excel 导出（批次说明表 + 文件清单两 sheet） |
| F8 | 集成接口 | `/api/v1/integration/*` 无认证只读：按上传时间/发生时间/模态/分页查 ID、按 ID 取元数据+下载 URL；调用审计 |

## 架构与部署拓扑

```
浏览器 ──:80──▶ frontend(nginx) ──/api/*──▶ backend(FastAPI :8080，不对外) ──▶ SQLite(./data)
   │ 分片直传/presigned 下载（:9000）                    │ 内网 client（minio:9000）
   └────────────────────▶ minio(:9000) ◀─────────────────┘
FDL 引擎 ── docker network connect back ──▶ backend:8080/api/v1/integration/*
```

- **frontend**：nginx 唯一对外入口，SPA fallback；`/api/v1/integration/` 返回 404（内网隔离第一层）
- **backend**：仅 `expose 8080`，不发布端口；启动时先跑 `seed.py`（幂等基线）再启动 uvicorn
- **minio**：9000 对外（浏览器分片直传与 presigned 下载的硬依赖，架构 7.1）；9001 Console 仅容器网络内

## 快速开始

```bash
docker compose up -d --build
# 健康检查
curl http://localhost/healthz        # → {"status":"ok"}
```

首次启动自动建表并 seed 基线数据（幂等，重启不重复）。访问 http://localhost 登录。

**基线账号**（`backend/seed.py`，与测试基线一致）：

| 账号 | 密码 | 角色 | 单位 |
|------|------|------|------|
| admin | admin123 | 系统管理员 | — |
| zhang | pass123 | 对接人 | 辉腾梁风电场 |
| li | pass123 | 对接人 | 辉腾梁风电场 |
| wang | pass123 | 对接人 | 大丰光伏电站 |

**数据与备份**：SQLite 与上传元数据落在 `./data/datacollecthub.db`（MinIO 对象在 `minio-data` volume）。备份只需拷贝 `./data` 目录（`.backup` 目录已 gitignore，可直接放入）。删除 `./data` 后重启容器可完全重置基线。

**环境变量**（可选覆盖）：`JWT_SECRET_KEY`、`MINIO_ACCESS_KEY/MINIO_SECRET_KEY`（与 MinIO root 凭据一致）、`MINIO_PUBLIC_ENDPOINT`（presigned URL 的对外地址，生产环境换成 HTTPS 反代域名）。

## 本地开发

```bash
# 后端（Python 3.11，venv）
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload            # 默认 SQLite ./datacollecthub.db

# 前端（Node 20）
cd frontend
npm install
npm run dev                              # 开发模式，/api 由 vite 反代

# 后端测试（66 个）
cd backend
pytest                                   # 或 .venv\Scripts\python.exe -m pytest tests/

# 前端构建
cd frontend
npm run build
```

## E2E 测试（Playwright）

前置条件：`docker compose up -d --build` 完成（基线账号就绪）。

```bash
cd e2e
npm install
npx playwright install chromium         # 首次
npx playwright test                     # 4 个用例，串行执行
```

| 用例 | 覆盖 | 说明 |
|------|------|------|
| 1 对接人完整流程 | TC-AUTH-002 / BATCH-001 / UP-001 / META-002 | 登录→建批次→5MB 真实分片上传→时区校验→元数据保存 |
| 2 同单位他人隔离 | TC-PERM-002 / META-004 / META-006 | UI 无编辑/删除按钮；API 直调 PUT 403 |
| 3 集成接口外部隔离 | TC-INT-001 | 经 nginx 访问 integration 返回 404 |
| 4 容器内集成可达 | TC-INT-001 / INT-006 | `docker compose exec` 容器内 200（无认证只读） |

测试自清洗：每轮批次编号/文件名带时间戳，重跑不冲突（原始区永不覆盖设计下可无限重跑）。

## E2E 测试方案 47 用例覆盖报告

> ✅ = 已自动化（pytest 66 个 / Playwright 4 个）；🔶 = 部分自动化，需人工复核；⭕ = 未自动化（手动验证）

| 用例 | 状态 | 覆盖位置 |
|------|------|----------|
| TC-AUTH-001 管理员登录 | ✅ | pytest `test_login_ok` |
| TC-AUTH-002 普通用户登录 | ✅ | E2E 用例 1；管理入口不可见由路由守卫保证 |
| TC-AUTH-003 错误密码 | ✅ | pytest `test_login_wrong_password_401` |
| TC-AUTH-004 停用即时失效 | ✅ | pytest `test_deactivate_user_old_token_rejected`、`test_stale_token_rejected_after_deactivate` |
| TC-AUTH-005 无 Token 401 | ✅ | pytest `test_me_requires_token` |
| TC-BATCH-001 创建批次 | ✅ | pytest `test_create_batch_ok`；E2E 用例 1 |
| TC-BATCH-002 必填校验 | 🔶 | pytest 422（`test_create_duplicate_batch_no_422`）；前端表单拦截 |
| TC-BATCH-003 同单位他人批次只读 | ✅ | pytest `test_edit_only_creator_403`、`test_delete_batch_by_non_creator_403` |
| TC-BATCH-004 创建者编辑+审计 | ✅ | pytest `test_update_writes_audit_field_changes` |
| TC-BATCH-005 跨单位不可见 | ✅ | pytest `test_cross_org_detail_404`、`test_list_only_own_org` |
| TC-BATCH-006 删除批次规则 | ✅ | pytest `test_delete_empty_batch_by_creator_ok`、`test_delete_nonempty_batch_rejected` |
| TC-BATCH-007 管理员跨单位 | ✅ | pytest `test_admin_can_edit_any`、`test_admin_list_all` |
| TC-UP-001 上传与模态推断 | 🔶 | E2E 用例 1（真实 MinIO，.dat→SCADA）；全 8 类模态推断需人工复核 |
| TC-UP-002 大文件分片（≥1GB） | 🔶 | pytest `test_init_large_file_multi_parts`（init 层）；真实 1.2GB 上传手动 |
| TC-UP-003 断点续传 | ⭕ | 前端 localStorage 任务队列已实现，网络中断场景手动 |
| TC-UP-004 刷新恢复上传 | ⭕ | 前端已实现（上传页恢复未完成任务），手动 |
| TC-UP-005 MinIO 路径组织 | 🔶 | E2E 用例 1 真实上传（路径 `场站/设备/模态/年/月/文件`）；mc 列出人工核对 |
| TC-UP-006 原始文件不修改 | 🔶 | pytest `test_init_duplicate_object_key_422`（永不覆盖）；SHA256 比对手动 |
| TC-UP-007 上传到本单位他人批次 | ⭕ | 权限允许（uploader 记上传者），未自动化 |
| TC-META-001 批次字段自动继承 | ✅ | pytest `test_complete_creates_datafile_with_inherited_batch` |
| TC-META-002 文件级填写与时区校验 | ✅ | pytest `test_update_metadata_requires_timezone`；E2E 用例 1 |
| TC-META-003 编辑自己文件+审计 | ✅ | pytest `test_update_own_file_writes_audit` |
| TC-META-004 编辑他人 403 | ✅ | pytest `test_update_others_file_403`；E2E 用例 2 |
| TC-META-005 批次修改不追溯 | ✅ | 快照继承设计，pytest `test_complete_creates_datafile_with_inherited_batch` |
| TC-META-006 删除他人 403 | ✅ | pytest `test_delete_others_file_403_and_object_kept`；E2E 用例 2 |
| TC-SEARCH-001 组合筛选 | ✅ | pytest `test_search_filters` |
| TC-SEARCH-002 单位隔离检索 | ✅ | pytest `test_search_hides_other_org` |
| TC-EXPORT-001 导出登记表结构 | ✅ | pytest `test_export_two_sheets` |
| TC-EXPORT-002 跨单位导出被拒 | ✅ | 导出走批次权限，pytest `test_cross_org_detail_404` |
| TC-PERM-001 权限矩阵参数化 | ✅ | pytest 分散于 batch/metadata/upload/admin 归属校验测试 |
| TC-PERM-002 前端按钮可见性 | ✅ | E2E 用例 2 |
| TC-PERM-003 删除联动 MinIO | 🔶 | pytest `test_delete_own_file_removes_object`（FakeStorage 语义）；真实 MinIO 联动手动 |
| TC-PERM-004 下载链接过期 | 🔶 | pytest `test_presign_get_uses_public_endpoint`（URL 生成）；真实过期访问手动 |
| TC-INT-001 无认证访问 | ✅ | E2E 用例 3/4（nginx 404 + 容器内 200）；pytest `test_no_auth_required` |
| TC-INT-002 上传时间范围 | ✅ | pytest `test_filter_by_uploaded_time` |
| TC-INT-003 发生时间范围 | ✅ | pytest `test_filter_by_occurred_time` |
| TC-INT-004 模态多选 | ✅ | pytest `test_modalities_multi` |
| TC-INT-005 组合+分页 | ✅ | pytest `test_pagination_no_dup` |
| TC-INT-006 按 ID 读元数据 | ✅ | pytest `test_get_by_id_returns_metadata_and_url`；E2E 用例 4 |
| TC-INT-007 下载原始数据 | 🔶 | pytest 校验 download_url 返回；SHA256 比对手动 |
| TC-INT-008 不存在 ID 404 | ✅ | pytest `test_get_missing_404` |
| TC-INT-009 只读性 | ✅ | pytest `test_write_methods_not_allowed` |
| TC-INT-010 调用审计 | ✅ | pytest `test_integration_call_audited` |
| TC-ADMIN-001 创建单位与用户 | ✅ | pytest `test_admin_create_org`、`test_admin_create_user` |
| TC-ADMIN-002 重置密码 | ✅ | pytest `test_reset_password_then_old_fails` |
| TC-ADMIN-003 停用/启用 | ✅ | pytest `test_deactivate_user_old_token_rejected` |
| TC-ADMIN-004 管理员特权操作 | ✅ | pytest `test_admin_can_edit_any` |

**统计**：47 用例中 ✅ 36、🔶 8、⭕ 3（⭕ 为断点续传/刷新恢复/他人批次上传三个需真实网络中断或人工操作确认的场景，功能均已实现）。

## 设计决策与已知限制

- **minio 9000 对外发布**：浏览器分片直传/presigned 下载要求对象存储对外可达（架构 7.1 front 网络语义）；集成接口的双层隔离（nginx 404 + backend 不发布端口）与对象存储隔离互不干扰。
- **SQLite（MVP）**：WAL 模式 + 外键开启；单机部署场景足够，迁移 PostgreSQL 时 `DATABASE_URL` 切换 + `Base.metadata` 建表即可（ORM 无方言依赖）。
- **上传状态无服务端**：multipart 采用「分片独立对象 + compose 合并」，无服务端上传状态表；中断恢复完全由前端 localStorage 驱动，后端零状态。
- **presigned URL 公共端点**：签名 host 用 `MINIO_PUBLIC_ENDPOINT`（默认 http://localhost:9000），生产需改为 HTTPS 反代域名，否则浏览器直传/下载不可用。
