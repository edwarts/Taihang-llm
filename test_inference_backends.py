# -*- coding: utf-8 -*-
"""
vLLM & Ollama 连接测试脚本
用于验证后端配置是否正确
"""

import requests
import sys
import os
from datetime import datetime

# 配置
VLLM_URL = "http://172.31.194.125:8000"
OLLAMA_URL = "http://localhost:11434"
TIMEOUT = 5

def test_vllm():
    """测试vLLM连接"""
    print("\n" + "="*50)
    print("测试 vLLM (WSL2)")
    print("="*50)
    
    try:
        print(f"[INFO] 连接 {VLLM_URL}...", end="")
        response = requests.get(f"{VLLM_URL}/v1/models", timeout=TIMEOUT)
        
        if response.status_code == 200:
            models = response.json().get('data', [])
            print(" ✓")
            print(f"[OK] vLLM 已连接！")
            print(f"[INFO] 可用模型:")
            for model in models:
                print(f"  - {model['id']}")
            return True
        else:
            print(f" ✗ (HTTP {response.status_code})")
            print(f"[ERROR] vLLM 返回状态码 {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError as e:
        print(" ✗")
        print(f"[ERROR] 无法连接 vLLM")
        print(f"[HINT] 检查:")
        print(f"  1. WSL2 IP 是否正确 (当前: {VLLM_URL})")
        print(f"  2. vLLM 是否已启动: bash vllm_startup.sh")
        print(f"  3. 防火墙设置")
        return False
        
    except requests.exceptions.Timeout:
        print(" ✗")
        print(f"[ERROR] 连接超时 ({TIMEOUT}s)")
        return False
        
    except Exception as e:
        print(f" ✗")
        print(f"[ERROR] {e}")
        return False

def test_ollama():
    """测试Ollama连接"""
    print("\n" + "="*50)
    print("测试 Ollama (Windows)")
    print("="*50)
    
    try:
        print(f"[INFO] 连接 {OLLAMA_URL}...", end="")
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=TIMEOUT)
        
        if response.status_code == 200:
            models = response.json().get('models', [])
            print(" ✓")
            print(f"[OK] Ollama 已连接！")
            print(f"[INFO] 可用模型:")
            for model in models:
                print(f"  - {model['name']}")
            return True
        else:
            print(f" ✗ (HTTP {response.status_code})")
            print(f"[ERROR] Ollama 返回状态码 {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(" ✗")
        print(f"[ERROR] 无法连接 Ollama")
        print(f"[HINT] 检查: ollama serve 是否运行")
        return False
        
    except requests.exceptions.Timeout:
        print(" ✗")
        print(f"[ERROR] 连接超时 ({TIMEOUT}s)")
        return False
        
    except Exception as e:
        print(f" ✗")
        print(f"[ERROR] {e}")
        return False

def test_inference(backend="vllm"):
    """测试推理功能"""
    print("\n" + "="*50)
    print(f"测试 {backend.upper()} 推理")
    print("="*50)
    
    try:
        if backend.lower() == "vllm":
            url = f"{VLLM_URL}/v1/chat/completions"
            payload = {
                "model": "deepseek-ai/deepseek-r1-distill-qwen-70b",
                "messages": [
                    {"role": "user", "content": "What is 2+2? Answer in one sentence."}
                ],
                "max_tokens": 100,
                "temperature": 0.7
            }
        else:
            url = f"{OLLAMA_URL}/api/generate"
            payload = {
                "model": "deepseek-r1:70b",
                "prompt": "What is 2+2? Answer in one sentence.",
                "stream": False
            }
        
        print(f"[INFO] 发送测试prompt...", end="")
        start_time = datetime.now()
        response = requests.post(url, json=payload, timeout=60)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if response.status_code == 200:
            print(" ✓")
            
            if backend.lower() == "vllm":
                result = response.json()
                answer = result['choices'][0]['message']['content']
                print(f"[OK] 推理成功！")
                print(f"[RESPONSE] {answer[:200]}")
                print(f"[TIMING] 耗时 {elapsed:.1f} 秒")
            else:
                result = response.json()
                answer = result.get('response', '')
                print(f"[OK] 推理成功！")
                print(f"[RESPONSE] {answer[:200]}")
                print(f"[TIMING] 耗时 {elapsed:.1f} 秒")
            
            return True
        else:
            print(f" ✗ (HTTP {response.status_code})")
            print(f"[ERROR] 推理请求失败")
            return False
            
    except requests.exceptions.Timeout:
        print(" ✗")
        print(f"[ERROR] 推理超时 (>60s)")
        print(f"[HINT] 可能在下载模型，请等待...")
        return False
        
    except Exception as e:
        print(f" ✗")
        print(f"[ERROR] {e}")
        return False

def main():
    """主测试流程"""
    print("\n")
    print("╔════════════════════════════════════════════╗")
    print("║   推理后端连接测试                        ║")
    print("║   Testing Inference Backends              ║")
    print("╚════════════════════════════════════════════╝")
    
    # 测试vLLM
    vllm_ok = test_vllm()
    
    # 测试Ollama
    ollama_ok = test_ollama()
    
    # 功能测试
    if vllm_ok:
        print("\n[INFO] vLLM 已连接，进行推理测试...")
        inference_ok = test_inference("vllm")
    elif ollama_ok:
        print("\n[INFO] Ollama 已连接，进行推理测试...")
        inference_ok = test_inference("ollama")
    else:
        inference_ok = False
    
    # 总结
    print("\n" + "="*50)
    print("测试总结")
    print("="*50)
    
    print(f"vLLM:      {'✓ 可用' if vllm_ok else '✗ 不可用'}")
    print(f"Ollama:    {'✓ 可用' if ollama_ok else '✗ 不可用'}")
    print(f"推理:      {'✓ 正常' if inference_ok else '✗ 失败'}")
    
    if vllm_ok and inference_ok:
        print("\n[SUCCESS] vLLM 已准备好！可以开始推理。")
        print("[HINT] 运行: python src/local_data_pipeline_inference.py -s AAPL")
        return 0
    elif ollama_ok and inference_ok:
        print("\n[SUCCESS] Ollama 已准备好！可以开始推理。")
        print("[HINT] 运行: python src/local_data_pipeline_inference.py -s AAPL")
        return 0
    else:
        print("\n[ERROR] 没有可用的推理后端！")
        print("[ACTION] 请检查:")
        if not vllm_ok:
            print("  1. vLLM: 运行 'bash vllm_startup.sh' 在WSL2内")
            print("  2. 确保WSL2 IP地址正确")
        if not ollama_ok:
            print("  3. Ollama: 运行 'ollama serve' 在Windows内")
        return 1

if __name__ == "__main__":
    sys.exit(main())
