# 评教调试助手（全自动版）

这个项目用于**自动化处理**评教页面任务：自动打开“待评价”课程、切换教师 tab、预选单选题、填入评语草稿，并**自动点击提交**及处理成功弹窗。

**注意：** 脚本现在是**全自动**模式。启动后会自动快速处理所有待评课程，无需人工逐个确认。请确保你的评教内容（如评语模板、默认评分）符合你的预期。

## 核心功能

- **全自动流程**：填表 -> 提交 -> 确认成功弹窗 -> 下一门。
- **极速模式**：已针对速度进行优化，去除人为延迟。
- **多教师支持**：自动识别并切换课程内的多个教师 Tab 页。
- **智能弹窗处理**：自动尝试点击“确定”按钮或按回车键关闭成功提示框。

## 环境准备

- Windows + Python 3.10+
- 安装依赖：

```powershell
cd pj_assistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install
```

## 配置指南

复制 `config.example.yaml` 为 `config.yaml`，关键配置如下：

```yaml
# 目标 URL
login_url: "..."
list_url: "..."

# 运行参数
delays_ms:
  min: 0   # 极速模式设为 0
  max: 20

# 选择器配置
selectors:
  submit_button: ".modal-footer button.sure" # 提交按钮
  success_confirm_button: ".layui-layer-btn0" # 成功弹窗的确定按钮
```

## 使用方法

### 1. 登录并保存状态（首次运行或Cookie过期时）

```powershell
python run_login.py --config config.yaml
```

- 脚本会打开浏览器。
- 请在浏览器中手动完成登录。
- 登录成功后，回到终端按 **Enter** 键，保存 `storage_state.json`。

**切换账号提示：**
如需切换账号，只需重新运行此命令并登录新账号，覆盖旧的 `storage_state.json` 即可。

### 2. 启动全自动评教

```powershell
python run_assist.py --config config.yaml
```

脚本将自动执行以下操作：
1.  打开评教列表页。
2.  依次进入每门课程的评价页。
3.  填写所有单选题和评语。
4.  **自动提交**并关闭提示框。
5.  完成后自动退出。

## 常见问题

- **提示框不关闭**：如果脚本提交后卡在“提交成功”弹窗，请检查页面源码，找到那个弹窗的“确定”按钮的选择器，更新到 `config.yaml` 的 `success_confirm_button` 字段中。
- **登录失效**：重新运行 `run_login.py`。
- **报错截图**：运行出错时，截图会自动保存在 `logs/screenshots/` 目录下。

## 产物

- 日志文件：`logs/run_*.log`