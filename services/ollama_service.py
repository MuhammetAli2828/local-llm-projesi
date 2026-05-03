"""
ollama_service.py
=================
Ollama API istemcisi.
Chatbot + PDF analiz için kullanılır.
HF fine-tuned model yerine Ollama tercih edilir:
  - Kurulumu basit, hız makul, Türkçe desteği yeterli.
  - Fine-tuned model sadece çok özel alan sınıflandırması gerektiğinde eklenebilir.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import requests


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    def health(self) -> Dict[str, Any]:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            return {"ok": True, "models": models}
        except Exception as e:
            return {"ok": False, "models": [], "error": str(e)}

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: int = 60,
        options: Dict[str, Any] | None = None,
        keep_alive: str = "30m",
    ) -> str:
        """Ollama /api/chat endpoint'i ile sohbet.
        keep_alive: Model RAM/VRAM'de tutulma süresi (varsayılan 30dk).
        Bu sayede ardışık sorularda cold-start olmaz.
        """
        default_opts = {
            "num_ctx": 2048,
            "num_predict": 512,
            "num_thread": 8,
            "temperature": 0.5,
            "top_p": 0.9,
        }
        if options:
            default_opts.update(options)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": keep_alive,
            "options": default_opts,
        }

        try:
            r = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=timeout,
            )
            r.raise_for_status()
            data = r.json()
            return data.get("message", {}).get("content", "")
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Ollama bağlantısı kurulamadı. "
                "Ollama çalışıyor mu? → ollama serve"
            )
        except Exception as e:
            raise RuntimeError(f"Ollama hatası: {e}")

    def chat_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: int = 120,
        options: Dict[str, Any] | None = None,
        keep_alive: str = "30m",
    ):
        """Streaming chat — token-by-token yanıt için generator döndürür."""
        default_opts = {
            "num_ctx": 2048, "num_predict": 512, "num_thread": 8,
            "temperature": 0.5, "top_p": 0.9,
        }
        if options:
            default_opts.update(options)
        payload = {
            "model": model, "messages": messages, "stream": True,
            "keep_alive": keep_alive, "options": default_opts,
        }
        try:
            with requests.post(f"{self.base_url}/api/chat", json=payload,
                               timeout=timeout, stream=True) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line: continue
                    try:
                        data = json.loads(line.decode("utf-8"))
                        msg = data.get("message", {}).get("content", "")
                        if msg: yield msg
                        if data.get("done"): break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            yield f"\n\n❌ Hata: {e}"

    def warmup(self, model: str) -> bool:
        """Modeli RAM/VRAM'e önceden yükle (cold start önler)."""
        try:
            requests.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": "30m"},
                timeout=30,
            )
            return True
        except Exception:
            return False

    def available_model(self, preferred: str) -> str:
        """
        Tercih edilen modeli döner; yoksa mevcut listeden ilkini seçer.
        """
        info = self.health()
        models = info.get("models", [])
        if preferred in models:
            return preferred
        # En yakın eşleşmeyi bul
        pref_base = preferred.split(":")[0]
        for m in models:
            if m.startswith(pref_base):
                return m
        # Fallback: ilk model
        return models[0] if models else preferred