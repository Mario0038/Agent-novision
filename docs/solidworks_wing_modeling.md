# SolidWorks 梯形机翼参数化建模

## 1. 功能概述

当前领域智能体已支持通过 `/design_task` 命令从自然语言中提取机翼设计参数，并自动调用 SolidWorks COM 接口生成梯形机翼实体（SLDPRT）和 STEP 通用交换格式文件。

完整流程：

```
用户自然语言输入
    ↓
/design_task 解析提取参数
    ↓
自动检索知识库文献
    ↓
输出结构化设计任务报告
    ↓
检测建模意图 → 调用 SolidWorks COM
    ↓
  ├─ simple_trapezoid: 梯形拉伸 → SLDPRT + STEP ✅
  └─ loft_airfoil:
       ├─ 尝试 true Loft (InsertProtrusionBlend)
       ├─ 成功 → TRUE_LOFT_PASS
       └─ 失败 → fallback_extrude_airfoil → GEOMETRY_PASS_WITH_FALLBACK
    ↓
验证 SLDPRT + STEP（文件大小 + STEP 几何关键词）
    ↓
返回 success / partial / failed + build_actual_mode
```

## 2. 支持的 /design_task 输入示例

```
/design_task 创建一个翼展1200mm、根弦220mm、尖弦130mm、厚度20mm的低速无人机梯形机翼，并导出STEP
```

触发建模的关键词包括：`导出STEP`、`SolidWorks`、`建模`、`生成模型`、`三维模型`、`自动建模` 等。

不包含建模关键词的 `/design_task` 仅输出设计分析报告，不调用 SolidWorks。

## 3. 当前支持的参数

| 参数 | 单位 | 说明 |
|------|------|------|
| `span_mm` | mm | 翼展（半展长 × 2） |
| `root_chord_mm` | mm | 根弦长 |
| `tip_chord_mm` | mm | 尖弦长（未指定时按根弦 × 0.6 估算） |
| `thickness_mm` | mm | 最大厚度 |
| `sweep_deg` | deg | 后掠角 |
| `dihedral_deg` | deg | 上反角（当前版本仅记录，不改变几何） |
| `twist_root_deg` | deg | 根部扭转角（当前版本仅记录，不改变几何） |
| `twist_tip_deg` | deg | 梢部扭转角（当前版本仅记录，不改变几何） |
| `airfoil_name` | — | 翼型标识，当前固定为 `simple_trapezoid` |
| `output_name` | — | 输出文件名（自动安全处理） |

必需参数：`span_mm`、`root_chord_mm`、`thickness_mm`。三者缺一时不会触发自动建模。

## 4. 当前建模方式

### 4.1 simple_trapezoid — 梯形实体（✅ 已稳定）

1. 在 SolidWorks Top Plane（上视基准面 / XY 平面）上绘制梯形草图
   - 根弦在前缘 X=0 处，弦向沿 Y 轴
   - 尖弦在前缘 X=span 处，含后掠偏移 `sweep_offset = span × tan(sweep_deg)`
2. 根据 `thickness_mm` 沿 +Z 方向单方向拉伸生成实体
3. 保存为 SLDPRT 零件文件
4. 导出 STEP 通用交换格式

**状态：** 已稳定可用，默认测试中显示 `PASS`。

### 4.2 loft_airfoil — NACA 翼型放样（⚠️ 部分实现）

当前 `loft_airfoil` 模式执行以下流程：

1. **尝试 true Loft** — 在 Right Plane 创建根部 NACA 翼型截面草图，创建偏移参考平面后在梢部截面绘制尖部翼型，选中双草图后调用 `InsertProtrusionBlend` 进行双截面放样
2. **自动回退** — 如果 true Loft 未生成 solid body（当前 SolidWorks COM 接口下 InsertProtrusionBlend 返回 None 或 body count = 0），自动切换为 `fallback_extrude_airfoil`
3. **fallback_extrude_airfoil** — 在 Right Plane 上绘制根部 NACA 翼型闭合轮廓，沿展向单方向拉伸生成等弦长机翼实体

**回退方案的局限性：**
- ✅ 生成有效 STEP 几何（`MANIFOLD_SOLID_BREP`）
- ❌ 不包含根梢翼型变化（等弦长，无 taper）
- ❌ 不包含后掠角几何效果
- ❌ 不包含上反角几何效果
- ❌ 不包含扭转角几何效果
- ❌ 不是真实双截面 Loft 放样

**根因：** SolidWorks 2024 COM `InsertProtrusionBlend(17 params)` 在中文版环境下，即使双草图正确选中且在不同平面上，API 返回 None 且不生成 solid body。下一步将通过手动录制 VBA 宏反推正确的 COM 调用参数。

## 5. 输出文件位置

```
generated_models/solidworks/wing/parts/<output_name>.SLDPRT
generated_models/solidworks/wing/step/<output_name>.STEP
```

`<output_name>` 为经安全处理后的英文文件名。

测试专用输出固定为：

```
generated_models/solidworks/wing/parts/test_wing_pipeline.SLDPRT
generated_models/solidworks/wing/step/test_wing_pipeline.STEP
```

## 6. 文件名安全处理规则

`sanitize_output_name()` 函数确保输出文件名为纯 ASCII 安全字符，避免后续 ANSYS、Fluent、HyperMesh 等软件出现路径编码问题。

**处理步骤：**

1. **中文关键词映射** — 将常见中文设计对象映射为英文片段

   | 中文 | 英文 | 中文 | 英文 |
   |------|------|------|------|
   | 机翼 | wing | 尾翼 | tail |
   | 机身 | fuselage | 弹身 | body |
   | 进气道 | inlet | 喷管 | nozzle |
   | 飞行器 | vehicle | 无人机 | uav |
   | 翼型 | airfoil | 螺旋桨 | propeller |

2. **去除不安全字符** — 仅保留 `A-Z a-z 0-9 _ -`
3. **合并连续分隔符** — 多个连续 `_` 或 `-` 合并为单个
4. **去除首尾符号** — 去除开头和结尾的 `_` `-`
5. **数字开头加前缀** — 如 `1200mm_220mm` → `wing_1200mm_220mm`
6. **空值兜底** — 结果为空的默认 `wing_design`

**示例：**

| 输入 | 输出 |
|------|------|
| `design_task_机翼` | `design_task_wing` |
| `低速无人机机翼 第一版` | `uavwing` |
| `test_wing_v2.0 (final)` | `test_wing_v2_0_final` |
| `我的设计!!!` | `wing_design` |

## 7. 状态说明

### 7.1 建模执行状态（`build_trapezoidal_wing` 返回）

`build_actual_mode` 字段记录实际执行的建模方式：

| build_actual_mode | 含义 |
|-------------------|------|
| `simple_trapezoid` | 梯形实体建模（simple_trapezoid 模式） |
| `true_loft` | 真实双截面 NACA 翼型 Loft 放样成功 |
| `fallback_extrude` | Loft 失败，已回退为 NACA 等弦长拉伸 |

### 7.2 `/design_task` 第 11 节状态

| 状态 | 含义 |
|------|------|
| `success` | 建模正常完成，文件已验证（含 fallback 情况，会说明回退详情） |
| `partial` | 文件已生成但进程异常/超时 |
| `failed` | 建模失败，文件未生成或大小为 0 |

当 `build_actual_mode == "fallback_extrude"` 时，第 11 节会明确提示：

> ⚠️ Loft 放样未成功，已回退为 NACA 等弦长拉伸实体。
> 当前模型为有效 STEP 几何，但未包含根梢翼型变化、后掠、上反和扭转的真实放样效果。

### 7.3 回归测试判定

| 判定 | 含义 | 适用模式 |
|------|------|----------|
| `PASS` | 建模正常完成，所有输出文件验证通过 | simple_trapezoid |
| `TRUE_LOFT_PASS` | 真实双截面 Loft 放样成功，solid body > 0 | loft_airfoil（严格模式期望此结果） |
| `GEOMETRY_PASS_WITH_FALLBACK` | Loft 失败但 fallback 生成了有效 STEP 几何 | loft_airfoil（当前实际状态） |
| `FAIL` | 任意文件不存在、大小为 0 或 STEP 无几何实体 | 任何模式 |

## 8. 测试方式

### 8.1 回归测试（默认模式，推荐）

```bash
python scripts/test_wing_model_pipeline.py
```

同时测试 `simple_trapezoid` 和 `loft_airfoil` 双模式。

**退出码：** 
- `0` — 所有模式通过（loft fallback 视为 geometry OK，终端显示 WARNING）
- `1` — 任意模式 FAIL（文件缺失或无几何实体）

### 8.2 回归测试（严格 Loft 模式）

```bash
python scripts/test_wing_model_pipeline.py --strict-loft
```

**退出码：**
- `0` — `TRUE_LOFT_PASS`（真实 Loft 成功，当前尚未实现）
- `2` — `GEOMETRY_PASS_WITH_FALLBACK`（fallback 在严格模式下视为未通过）
- `1` — FAIL

### 8.3 单次建模

```bash
python scripts/create_wing_model.py
```

读取 `examples/wing_params.json` 中的参数并建模。参数文件中的 `build_mode` 决定使用哪种建模策略。

### 8.4 Agent 内触发

```
/design_task 创建一个翼展1200mm、根弦220mm、尖弦130mm、厚度20mm的低速无人机梯形机翼，并导出STEP
```

## 9. 常见问题

### 9.1 pywin32 缺失

**现象：** `ImportError: No module named 'win32com'`

**解决：**

```bash
pip install pywin32
```

### 9.2 SolidWorks 未安装或未打开

**现象：** `建模函数返回 None（连接 SolidWorks 失败）`

**解决：** 手动打开 SolidWorks 后重试。COM 连接会自动附加到已运行的实例。

### 9.3 COM 调用超时

**现象：** 建模过程长时间无响应

**解决：**
- 确认 SolidWorks 窗口未弹出对话框（如"重建模型"提示）
- 关闭其他占用 COM 的应用程序
- 重启 SolidWorks 后重试

### 9.4 文件已生成但返回 partial

**现象：** 报告显示 `partial`，但 SLDPRT/STEP 文件存在且可打开

**说明：** 建模函数可能在保存完成后、返回结果前触发了 COM 异常。文件通常完整可用，建议在 SolidWorks 中打开验证。

### 9.5 STEP 文件未生成

**现象：** SLDPRT 存在但 STEP 不存在

**解决：**
- 手动在 SolidWorks 中打开 SLDPRT，执行 `文件 → 另存为 → STEP`
- 检查磁盘空间是否充足

### 9.6 中文路径或中文文件名导致后处理异常

**说明：** 当前版本已通过 `sanitize_output_name()` 自动处理，输出文件名均为 ASCII 安全字符。如仍遇到路径问题，请确认项目根目录路径不包含中文或空格。

## 10. 后续升级计划

| 优先级 | 功能 | 说明 |
|--------|------|------|
| **P0** | **修复 true Loft COM 调用** | 通过 SolidWorks 手动录制 VBA 宏，反推 `InsertProtrusionBlend` 的正确 COM 参数组合；验证双截面放样生成 solid body |
| P0 | true_loft_airfoil 上线 | 确保 root_airfoil→tip_airfoil 双截面放样成功；后掠/上反/扭转几何生效 |
| P0 | 保留 fallback 兜底 | `fallback_extrude_airfoil` 作为 Loft 失败时的可靠回退，继续生成有效 STEP |
| P1 | 多截面机翼 | 支持 3+ 截面的变弦长/变厚度/变扭转机翼 |
| P1 | NACA 5 位数翼型 | 支持 NACA 5-digit 系列翼型坐标生成 |
| P2 | 翼梁/翼肋参数化 | 在 loft 实体上增加内部结构特征 |
| P2 | 对接 ANSYS Fluent | 从 STEP 文件自动生成 CFD 网格和边界条件 |
| P2 | 对接 HyperMesh | 自动导出适用于结构分析的几何 |
| P2 | 螺旋桨参数化建模 | 新增 `/design_task` 螺旋桨参数提取 |
| P3 | 弹翼参数化建模 | 扩展到战术导弹弹翼（需遵守安全边界） |
| P3 | 机身参数化建模 | 截面形状 + 纵向轮廓的放样建模 |
| P3 | ANSYS Mechanical 对接 | 自动生成静力/模态分析模板 |

### 当前实际状态

- ✅ `simple_trapezoid` — 稳定可用，PASS
- ✅ NACA 4 位数翼型生成器 — 数学层已就绪
- ✅ `fallback_extrude_airfoil` — 兜底方案，生成有效 STEP 几何
- ⚠️ `true_loft_airfoil` — 草图创建和选择已通，但 `InsertProtrusionBlend` 返回 None 且无 solid body
- ❌ 真实双截面放样效果 — 尚未实现

---

> **文档版本:** v2.0  
> **最后更新:** 2026-05-13  
> **适用范围:** 领域智能体 SolidWorks 机翼建模模块  
> **当前测试状态:** SIMPLE_TRAPEZOID=PASS, LOFT_AIRFOIL=GEOMETRY_PASS_WITH_FALLBACK
