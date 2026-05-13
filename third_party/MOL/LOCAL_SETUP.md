# MOL 本地 baseline 说明

本目录是在 Windows 上准备的 MOL 运行环境，使用 Python 3.9 虚拟环境 `.venv`。

## 环境

使用本地解释器：

```powershell
.\.venv\Scripts\python.exe
```

已安装的核心依赖：

- `torch==1.13.0+cu117`
- `torchvision==0.14.0+cu117`
- `dlib==19.24.1`
- `opencv-contrib-python-headless==4.7.0.72`
- `numpy==1.23.5`
- `scikit-learn==1.2.2`

Dlib 68 点人脸关键点预测模型已经下载到：

```text
utils/shape_predictor_68_face_landmarks.dat
```

`spatial-correlation-sampler` 没有安装成功，原因是这台 Windows 机器只有 NVIDIA 驱动，没有配置本地 CUDA toolkit，`CUDA_HOME` 未设置。现在 [modules/FlowNet.py](D:/PythonCode/TestAgent/third_party/MOL/modules/FlowNet.py) 中已经加入纯 PyTorch fallback，输出形状与原扩展保持一致，因此 MOL 仍然可以运行。这个 fallback 会比编译版 CUDA 扩展慢一些。

## 数据放置方式

MOL 需要按照类别整理好的帧序列文件夹。以 3 分类 baseline 为例，目录结构应如下：

```text
data/
  SAMM_data_3/
    surprise/
      006_1_2/
        006_05562.jpg
        006_05563.jpg
    positive/
    negative/
  CASME2_data_3/
    surprise/
    positive/
    negative/
  SMIC_data_3/
    surprise/
    positive/
    negative/
```

公开的 MOL 项目不包含原始数据集。CASME II、SAMM 和 SMIC 都需要向数据集所有者申请授权。常用官方申请入口：

- CASME II: `http://casme.psych.ac.cn/casme/e2` or `http://casme.psych.ac.cn/casme/c2`
- SAMM: `https://helward.mmu.ac.uk/STAFF/M.Yap/dataset.php`
- SMIC: `https://www.oulu.fi/cmvs/node/41319`

## 放好数据后的命令

生成 subject 级 processed 文件：

```powershell
.\.venv\Scripts\python.exe dataset.py --dataset SAMM --cls 3 --mode_train
.\.venv\Scripts\python.exe dataset.py --dataset SAMM --cls 3
```

运行一个短时间 smoke baseline：

```powershell
.\.venv\Scripts\python.exe main.py --lr 1e-4 --num_steps 20 --batch_size 4 --of_weight 10 --ldm_weight 0.1 --neighbor_num 4 --version MOL_SAMM3_smoke --seed 2024 --dataset SAMM --cls 3
```

运行更接近论文设置的长训练 baseline：

```powershell
.\.venv\Scripts\python.exe main.py --lr 1e-4 --num_steps 1000 --batch_size 32 --of_weight 10 --ldm_weight 0.1 --neighbor_num 4 --version MOL_SAMM3 --seed 2024 --dataset SAMM --cls 3
```
