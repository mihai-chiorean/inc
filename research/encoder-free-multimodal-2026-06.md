# Encoder-free multimodal LLMs (the "connector is all you need" pattern)

**Source:** Maarten Grootendorst, *A Visual Guide to Gemma 4 12B* — Exploring Language Models (Substack), 2026-06-03.
**Why this note exists:** an architecture shift worth knowing when integrating multimodal models, especially on the edge. Pointed to from `ai-engineer` (multimodal LLM integration) and relevant to `video-analytics-engineer` (VLMs) and `vision-engineer` (vision embeddings). External-source reference, not a decision.

---

## The standard pattern: encoder + connector

To make a text LLM multimodal, the usual recipe is **two added components**:

1. **Encoder** — a small Transformer (attention-based) that processes the non-text input (image, audio) into embeddings. Not free: it has real parameter weight and it must *finish* before the LLM can start, adding latency.
   - Gemma 4 reference sizes: **vision encoder** 150M params (E2B/E4B) / 550M (26B A4B, 31B); **audio encoder** 305M (E2B/E4B).
2. **Connector** — a small linear projection that maps the encoder's output embeddings to the LLM's token-embedding dimension, so they can be interleaved with text tokens. (LLMs are mostly trained on text; the connector makes the other modalities "look like" tokens.)

This works well (Gemma 4, Qwen 3.5, most open multimodal LLMs) but costs **latency** (encoder runs first) and **parameters** (encoders are large), and complicates fine-tuning (you typically tune only the LLM, not the encoders — so the encoders don't grow with the model).

## The encoder-free approach (Gemma 4 12B)

Remove the encoders; keep the modalities. The LLM absorbs the work the encoder used to do (learned during training). "What if the connector is all you need?"

**Vision (encoder → lightweight embedder, ~550M → ~35M params):**
- Use **48×48 patches directly** (vs the encoder path's 16×16 patches pooled into 3×3 grids). No attention in the embedder — each patch is processed in isolation; **attention happens in the LLM**.
- The ~35M params are almost entirely the **pixel→model-dim projection**: each patch is 48×48×3 = 6,912 pixels projected to the model's 3,840 dims ≈ 26M params. So it didn't "shrink to 35M of clever weights" — there are just a lot of pixels to project.
- **Positional info** can't use the encoder's 2D-RoPE (embedder is attention-free) nor the LLM's 1D positions. Instead, inject spatial position before the LLM: two learned matrices (x and y, each 1120 × 3840) indexed by patch coordinate; the selected x- and y-embeddings are **added** to each patch embedding. Then a final **LayerNorm** for stability, then project to model dim.
- Token "budgets" (max patches): 70 / 140 / 280 / 560 / 1120 — more tokens = finer-grained image.

**Audio (encoder → direct projection, even simpler):**
- Split raw audio into **40 ms windows**; at 16 kHz that's **640 raw amplitude samples** per window. Linear-project those raw samples straight to model dim. That's it — no encoder, no extra positional embeddings (audio is already a 1-D sequence, handled like text).

## Tradeoffs (the load-bearing part)

- **+ Latency / TTFT:** vision/audio tokens reach the LLM much faster (no encoder stack to clear), so the LLM starts generating sooner.
- **+ Params:** ~35M embedder vs ~550M encoder.
- **+ Fine-tuning simplicity:** no separate encoder to co-train; the modality understanding lives in the LLM you're already tuning.
- **− Burden on the LLM:** the LLM must learn to make sense of near-raw inputs (lost the encoder's semantically-rich features); this is paid for in training. Pooling 16×16→48×48 patches loses little *because* there's no rich encoder to feed anyway.
- **Open question (flagged in the post's comments):** no published benchmarks of with- vs without-encoder quality. Unknown whether matching encoder-based quality needs more data / more training. Treat the quality parity as **unproven**, the latency/param wins as real.

## Practical takeaways for agents

- When choosing/integrating a multimodal model, know which architecture it is: **encoder+connector** (richer features, higher latency + params, encoder frozen during FT) vs **encoder-free / direct-projection** (faster TTFT, smaller, FT-simple, quality parity unproven).
- **Edge relevance (Jetson/WendyOS):** encoder-free is attractive where TTFT and VRAM matter — but verify quality on the actual task; don't assume parity. The 12B encoder-free model targets ~12–16 GB VRAM.
- The general lever to remember: a **connector (linear projection) interleaving modality embeddings with text tokens** is the minimum viable multimodal mechanism; the encoder is an optional (expensive) quality booster, not a requirement.
