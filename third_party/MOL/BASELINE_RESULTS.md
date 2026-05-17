# MOL baseline 运行结果

## 一句话结论

目前已经把 MOL 在本机完整跑通，并完成了 Hugging Face TIM20 数据包中可用的 3 个微表情子集 quick baseline：

- SAMM 风格子集：26 个 subject
- CASME2 风格子集：24 个 subject
- SMIC 风格子集：16 个 subject

这份结果可以作为“系统链路已跑通”的组会验收版本使用；但它不是论文中基于官方授权 SAMM/CASME2/SMIC 原始数据的严格复现。

## 数据来源和限制

数据来源：Hugging Face 数据集 `GriErik123/Micro-Expression-Recognition`。

该数据包包含微表情 TIM20 图像序列。本次为了在三天内跑通 baseline，使用其中的公开 TIM20 序列，转换为 MOL 可读取的目录结构：

```text
data/SAMM_data_3/
  surprise/
  positive/
  negative/

data/CASME2_data_3/
  surprise/
  positive/
  negative/

data/SMIC_data_3/
  surprise/
  positive/
  negative/
```

需要注意：

- 官方 SAMM/CASME2/SMIC 原始数据需要申请授权，本机当前没有这些官方原始数据。
- 现在的结果是“基于公开 TIM20 数据包的本地 MOL baseline”，适合用于组会展示系统流程、复现实验链路和后续消融实验准备。
- 训练步数设置为 `num_steps=2`，属于快速验收配置，不是最终高精度训练配置。
- SMIC 数据包中带有 `_left`、`rotate` 等增强序列；本次只使用原始序列，避免把增强样本混入 LOSO 测试口径。

## 本机环境

```text
torch==1.13.0+cu117
torchvision==0.14.0+cu117
dlib==19.24.1
opencv-contrib-python-headless==4.7.0.72
numpy==1.23.5
scikit-learn==1.2.2
```

由于这台 Windows 机器没有配置本地 CUDA toolkit，`spatial-correlation-sampler` 无法编译安装。因此 [modules/FlowNet.py](D:/PythonCode/TestAgent/third_party/MOL/modules/FlowNet.py) 中加入了纯 PyTorch fallback，使 MOL 可以在当前环境下继续运行。

SMIC 中个别小尺寸图像会让 dlib 默认人脸检测失败，因此 [dataset.py](D:/PythonCode/TestAgent/third_party/MOL/dataset.py) 中加入了二次检测 fallback：默认检测失败时，把 dlib upsample 从 1 提到 2 再检测。

## 主结果汇总

| 数据集 | subject 数 | Accuracy/WAR | UAR | WF1 | UF1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| SAMM 3 类 | 26 | 0.5678 | 0.3428 | 0.5188 | 0.3312 |
| CASME2 3 类 | 24 | 0.4830 | 0.2965 | 0.4464 | 0.2807 |
| SMIC 3 类 | 16 | 0.3780 | 0.3377 | 0.3234 | 0.2939 |

## SAMM 26 Subject Quick Baseline

运行命令：

```powershell
.\.venv\Scripts\python.exe run_selected_baseline.py --dataset SAMM --cls 3 --subjects 006 007 009 010 011 012 013 014 015 016 017 018 019 020 021 022 023 026 028 030 031 032 033 034 035 037 --num_steps 2 --batch_size 2 --neighbor_num 1 --of_weight 1 --ldm_weight 0.01 --version MOL_HF_TIM20_SAMM3_26subj_fullquick
```

最终指标：

```text
Accuracy / WAR: 0.5678
UAR: 0.3428
WF1: 0.5188
UF1: 0.3312
Confusion matrix: [[4, 8, 18], [0, 4, 48], [16, 12, 126]]
```

日志文件：

```text
logs/MOL_HF_TIM20_SAMM3_26subj_fullquick_train_log.txt
logs/MOL_HF_TIM20_SAMM3_26subj_fullquick_test_log.txt
```

模型权重：`saved_models/MOL_HF_TIM20_SAMM3_26subj_fullquick_SAMM_*_3cls.pth`，共 26 个 LOSO fold。

## CASME2 24 Subject Quick Baseline

运行命令：

```powershell
.\.venv\Scripts\python.exe run_selected_baseline.py --dataset CASME2 --cls 3 --subjects 01 02 03 04 05 06 07 08 09 11 12 13 14 15 16 17 19 20 21 22 23 24 25 26 --num_steps 2 --batch_size 2 --neighbor_num 1 --of_weight 1 --ldm_weight 0.01 --version MOL_HF_TIM20_CASME2_24subj_fullquick
```

最终指标：

```text
Accuracy / WAR: 0.4830
UAR: 0.2965
WF1: 0.4464
UF1: 0.2807
Confusion matrix: [[0, 10, 40], [10, 10, 44], [18, 30, 132]]
```

日志文件：

```text
logs/MOL_HF_TIM20_CASME2_24subj_fullquick_train_log.txt
logs/MOL_HF_TIM20_CASME2_24subj_fullquick_test_log.txt
```

模型权重：`saved_models/MOL_HF_TIM20_CASME2_24subj_fullquick_CASME2_*_3cls.pth`，共 24 个 LOSO fold。

## SMIC 16 Subject Quick Baseline

运行命令：

```powershell
.\.venv\Scripts\python.exe run_selected_baseline.py --dataset SMIC --cls 3 --subjects s1 s2 s3 s4 s5 s6 s8 s9 s11 s12 s13 s14 s15 s18 s19 s20 --num_steps 2 --batch_size 2 --neighbor_num 1 --of_weight 1 --ldm_weight 0.01 --version MOL_HF_TIM20_SMIC3_16subj_fullquick
```

最终指标：

```text
Accuracy / WAR: 0.3780
UAR: 0.3377
WF1: 0.3234
UF1: 0.2939
Confusion matrix: [[26, 10, 50], [34, 4, 64], [44, 2, 94]]
```

日志文件：

```text
logs/MOL_HF_TIM20_SMIC3_16subj_fullquick_train_log.txt
logs/MOL_HF_TIM20_SMIC3_16subj_fullquick_test_log.txt
```

模型权重：`saved_models/MOL_HF_TIM20_SMIC3_16subj_fullquick_SMIC_*_3cls.pth`，共 16 个 LOSO fold。

## 阶段性实验记录

| 实验版本 | subject 数 | Accuracy/WAR | UAR | WF1 | UF1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `MOL_HF_TIM20_SAMM3_5subj_quick_v2` | 5 | 0.4000 | 0.3667 | 0.3571 | 0.2952 |
| `MOL_HF_TIM20_SAMM3_7subj_partial` | 7 | 0.6200 | 0.4444 | 0.5830 | 0.4116 |
| `MOL_HF_TIM20_SAMM3_10subj_partial` | 10 | 0.4925 | 0.3586 | 0.4537 | 0.3295 |
| `MOL_HF_TIM20_SAMM3_15subj_partial` | 15 | 0.5063 | 0.3504 | 0.4278 | 0.3136 |
| `MOL_HF_TIM20_SAMM3_19subj_partial` | 19 | 0.4167 | 0.3537 | 0.3918 | 0.2968 |
| `MOL_HF_TIM20_SAMM3_26subj_fullquick` | 26 | 0.5678 | 0.3428 | 0.5188 | 0.3312 |

## 后续可做的消融实验

当前已经具备完整运行链路，后续消融可以直接围绕以下变量展开：

- 去掉或调低光流损失：修改 `--of_weight`。
- 去掉或调低 landmark 约束：修改 `--ldm_weight`。
- 调整邻居数：修改 `--neighbor_num`。
- 增加训练步数：把 `--num_steps` 从 2 提高到 20、50 或更多。
- 分别在 SAMM/CASME2/SMIC 三个子集上重复同样设置，形成完整消融表。

