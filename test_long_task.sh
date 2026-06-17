#!/bin/bash
# 长时间测试任务 - 运行 30 秒

echo "=== 长时间测试任务开始 ==="
echo "时间: $(date)"
echo "主机: $(hostname)"
echo "GPU: $CUDA_VISIBLE_DEVICES"

for i in {1..30}; do
    echo "进度: $i/30 秒"
    sleep 1
done

echo "=== 测试任务完成 ==="
echo "时间: $(date)"
