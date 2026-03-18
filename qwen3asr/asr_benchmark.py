"""
asr_benchmark.py — Qwen3-ASR 性能測試腳本
測試項目：
  1. 單筆推理速度（短音訊 / 長音訊）
  2. 批次推理速度（1 / 4 / 8 筆）
  3. VRAM 使用量
  4. 語言自動偵測準確性
  5. 可選：對比 0.6B vs 1.7B

用法：
  python3 asr_benchmark.py [--model 0.6b|1.7b|both] [--timestamps]
"""
import sys
import time
import argparse
import torch

# ── 解析參數 ─────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--model", default="1.7b", choices=["0.6b", "1.7b", "both"])
parser.add_argument("--timestamps", action="store_true")
args = parser.parse_args()

MODELS = {
    "0.6b": "Qwen/Qwen3-ASR-0.6B",
    "1.7b": "Qwen/Qwen3-ASR-1.7B",
}

# ── 測試音訊（官方範例，涵蓋中英文）────────────────────────────────────────
TEST_AUDIOS = [
    {
        "name": "中文短句",
        "url": "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-ASR-Repo/asr_zh.wav",
        "lang": "Chinese",
    },
    {
        "name": "英文短句",
        "url": "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-ASR-Repo/asr_en.wav",
        "lang": "English",
    },
]

def vram_used_mb():
    if torch.cuda.is_available():
        return torch.cuda.memory_allocated() / 1024 / 1024
    return 0

def vram_total_mb():
    if torch.cuda.is_available():
        return torch.cuda.get_device_properties(0).total_memory / 1024 / 1024
    return 0

def hr():
    print("─" * 60)

def benchmark_model(model_key: str):
    from qwen_asr import Qwen3ASRModel

    model_name = MODELS[model_key]
    print(f"\n{'═'*60}")
    print(f"  模型：{model_name}")
    print(f"{'═'*60}")

    # ── 載入模型 ──────────────────────────────────────────────────────────────
    print("\n[載入] 初始化模型...")
    torch.cuda.reset_peak_memory_stats()
    vram_before = vram_used_mb()
    t0 = time.perf_counter()

    kwargs = dict(
        dtype=torch.bfloat16,
        device_map="cuda:0",
        max_inference_batch_size=32,
        max_new_tokens=512,
    )
    if args.timestamps:
        kwargs["forced_aligner"] = "Qwen/Qwen3-ForcedAligner-0.6B"
        kwargs["forced_aligner_kwargs"] = dict(dtype=torch.bfloat16, device_map="cuda:0")

    model = Qwen3ASRModel.from_pretrained(model_name, **kwargs)
    load_time = time.perf_counter() - t0
    vram_model = torch.cuda.max_memory_allocated() / 1024 / 1024

    print(f"  載入時間：{load_time:.1f}s")
    print(f"  VRAM（模型）：{vram_model:.0f} MB / {vram_total_mb():.0f} MB")

    results_summary = []

    # ── 測試 1：單筆推理（預熱）──────────────────────────────────────────────
    hr()
    print("[測試 1] 單筆推理（含 GPU 預熱）")
    for audio in TEST_AUDIOS:
        torch.cuda.reset_peak_memory_stats()
        t0 = time.perf_counter()
        results = model.transcribe(
            audio=audio["url"],
            language=audio["lang"],
            return_time_stamps=args.timestamps,
        )
        elapsed = time.perf_counter() - t0
        vram_inf = torch.cuda.max_memory_allocated() / 1024 / 1024
        r = results[0]
        print(f"\n  [{audio['name']}]")
        print(f"  文字：{r.text[:80]}")
        print(f"  語言：{r.language}  耗時：{elapsed:.2f}s  VRAM峰值：{vram_inf:.0f} MB")
        if args.timestamps and r.segments:
            print(f"  時間戳記片段數：{len(r.segments)}")
        results_summary.append({
            "name": audio["name"],
            "time_s": elapsed,
            "vram_mb": vram_inf,
        })

    # ── 測試 2：自動語言偵測 ──────────────────────────────────────────────────
    hr()
    print("[測試 2] 自動語言偵測（不指定語言）")
    for audio in TEST_AUDIOS:
        t0 = time.perf_counter()
        results = model.transcribe(audio=audio["url"], language=None)
        elapsed = time.perf_counter() - t0
        r = results[0]
        ok = "✅" if r.language and audio["lang"].lower() in r.language.lower() else "⚠"
        print(f"  {ok} [{audio['name']}] 偵測語言：{r.language}  耗時：{elapsed:.2f}s")

    # ── 測試 3：批次推理 ──────────────────────────────────────────────────────
    hr()
    print("[測試 3] 批次推理速度")
    for batch_size in [2, 4]:
        urls   = [a["url"]  for a in TEST_AUDIOS] * (batch_size // 2)
        langs  = [a["lang"] for a in TEST_AUDIOS] * (batch_size // 2)
        urls  = urls[:batch_size]
        langs = langs[:batch_size]

        torch.cuda.reset_peak_memory_stats()
        t0 = time.perf_counter()
        results = model.transcribe(audio=urls, language=langs)
        elapsed = time.perf_counter() - t0
        vram_inf = torch.cuda.max_memory_allocated() / 1024 / 1024

        per_item = elapsed / batch_size
        print(f"  批次 {batch_size} 筆：總計 {elapsed:.2f}s  每筆 {per_item:.2f}s  VRAM峰值：{vram_inf:.0f} MB")

    # ── 摘要 ──────────────────────────────────────────────────────────────────
    hr()
    print(f"[摘要] {model_key.upper()}")
    print(f"  模型載入：{load_time:.1f}s")
    print(f"  VRAM（模型）：{vram_model:.0f} MB")
    for r in results_summary:
        print(f"  {r['name']}：{r['time_s']:.2f}s（VRAM峰值 {r['vram_mb']:.0f} MB）")

    # 釋放模型
    del model
    torch.cuda.empty_cache()
    return results_summary

# ── 主程式 ───────────────────────────────────────────────────────────────────
print(f"\nQwen3-ASR 性能基準測試")
print(f"GPU：{torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only'}")
print(f"VRAM：{vram_total_mb():.0f} MB")
print(f"模型：{args.model}  時間戳記：{args.timestamps}")

if args.model == "both":
    r06 = benchmark_model("0.6b")
    r17 = benchmark_model("1.7b")
    print(f"\n{'═'*60}")
    print("  0.6B vs 1.7B 對比")
    print(f"{'═'*60}")
    for i, audio in enumerate(TEST_AUDIOS):
        t06 = r06[i]["time_s"]
        t17 = r17[i]["time_s"]
        speedup = t17 / t06 if t06 > 0 else 0
        print(f"  {audio['name']}：0.6B {t06:.2f}s  1.7B {t17:.2f}s  （0.6B 快 {speedup:.1f}x）")
else:
    benchmark_model(args.model)

print("\n測試完成 ✅")
