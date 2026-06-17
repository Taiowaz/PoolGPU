#!/bin/bash
# 简单测试任务脚本
# 用于验证 PoolGPU 系统在真实服务器上工作

echo "=== 测试任务开始 ==="
echo "时间: $(date)"
echo "主机: $(hostname)"
echo "用户: $(whoami)"
echo "GPU: $CUDA_VISIBLE_DEVICES"
echo ""

# 检查 GPU
if command -v nvidia-smi &> /dev/null; then
    echo "GPU 状态:"
    nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv
else
    echo "未找到 nvidia-smi"
fi

echo ""

# 模拟训练任务
echo "模拟训练任务..."
for i in {1..5}; do
    echo "Epoch $i/5 - loss: $(echo "scale=4; 1.0 - $i * 0.1" | bc)"
    sleep 1
done

echo ""
echo "=== 测试任务完成 ==="
echo "时间: $(date)"
