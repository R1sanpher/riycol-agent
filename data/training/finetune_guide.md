# Qwen2.5 微调指南

## 硬件情况
- **本地**: RTX 5060 Ti 16GB (Blackwell sm_120)
- **问题**: PyTorch 稳定版暂不支持 Blackwell (需 2.13+)
- **方案**: 云 GPU 微调 → GGUF 导出 → 本地推理

## 路线图

### 阶段 1: 数据准备（本地完成）
```bash
# 生成训练数据（Agent Swarm 自动生成）
python data/training/generate_data.py 100 all

# 导出并清洗
python data/training/train.py all
```

### 阶段 2: 云 GPU 微调
推荐平台: AutoDL (autodl.com) 或 Google Colab Pro

**AutoDL 配置建议**:
- GPU: RTX 4090 或 A5000 (≥24GB VRAM)
- 镜像: LLaMA-Factory 预装镜像
- 数据: 上传 `data/training/output/` 目录

**LLaMA-Factory LoRA 快速命令**:
```bash
llamafactory-cli train \
    --model_name_or_path Qwen/Qwen2.5-1.5B-Instruct \
    --dataset_dir data \
    --dataset riycol_train \
    --template qwen \
    --finetuning_type lora \
    --lora_rank 8 \
    --lora_target q_proj,v_proj \
    --output_dir output/qwen2.5-1.5b-riycol-lora \
    --per_device_train_batch_size 2 \
    --gradient_accumulation_steps 8 \
    --lr_scheduler_type cosine \
    --logging_steps 10 \
    --save_steps 100 \
    --learning_rate 5e-5 \
    --num_train_epochs 3 \
    --bf16
```

### 阶段 3: 合并 & 导出 GGUF
```bash
# 合并 LoRA
llamafactory-cli export \
    --model_name_or_path Qwen/Qwen2.5-1.5B-Instruct \
    --adapter_name_or_path output/qwen2.5-1.5b-riycol-lora \
    --template qwen \
    --finetuning_type lora \
    --export_dir models/qwen2.5-1.5b-riycol-merged \
    --export_size 2 \
    --export_device cpu

# 转换为 GGUF (需 llama.cpp)
python llama.cpp/convert_hf_to_gguf.py models/qwen2.5-1.5b-riycol-merged \
    --outfile models/qwen2.5-1.5b-riycol-q4_k_m.gguf \
    --outtype q4_k_m

# 或使用 quantize 直接量化
llama.cpp/quantize models/qwen2.5-1.5b-riycol-merged.gguf q4_k_m
```

### 阶段 4: 本地部署
```bash
# 更新 .env
MODEL_PATH=models/qwen2.5-1.5b-riycol-q4_k_m.gguf

# 重启服务
python main.py run all
```

## 数据量建议

| 阶段 | 最少 | 推荐 | 当前 |
|------|------|------|------|
| 可用 LoRA | 100 | 500 | ~32 |
| 明显提升 | 500 | 2000 | - |
| 全量微调 | 5000 | 10000+ | - |

当前优先：用 `generate_data.py` 批量生成 200-500 条高质量样本。
