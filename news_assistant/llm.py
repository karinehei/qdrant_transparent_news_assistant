from __future__ import annotations
from typing import Optional
import requests

# Optional import for Mistral (only needed if using mistral provider)
try:
    from mistralai import Mistral
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False


class LLM:
    def __init__(self, provider: str, model: str, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize LLM client.
        
        Args:
            provider: "ollama", "vllm", or "mistral"
            model: Model name (e.g., "phi:latest" for Ollama, "microsoft/Phi-3-mini-4k-instruct" for vLLM)
            api_key: API key (required for Mistral, ignored for Ollama/vLLM)
            base_url: Base URL (default: http://localhost:11434 for Ollama, http://localhost:8001 for vLLM)
        """
        self.provider = provider
        self.model = model
        
        if provider == "ollama":
            self.base_url = base_url or "http://localhost:11434"
            self.api_key = None
        elif provider == "vllm":
            # vLLM uses OpenAI-compatible API
            self.base_url = base_url or "http://localhost:8001"
            self.api_key = api_key or "dummy"  # vLLM doesn't require real API key, but OpenAI client expects one
        elif provider == "mistral":
            if not MISTRAL_AVAILABLE:
                raise ImportError("mistralai package not installed. Install with: pip install mistralai")
            if not api_key:
                raise ValueError("Mistral requires an API key")
            self.client = Mistral(api_key=api_key)
            self.api_key = api_key
        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'ollama', 'vllm', or 'mistral'")

    def generate(self, prompt: str, max_tokens: int = 450) -> str:
        """Generate text from prompt."""
        if self.provider == "ollama":
            return self._generate_ollama(prompt, max_tokens)
        elif self.provider == "vllm":
            return self._generate_vllm(prompt, max_tokens)
        elif self.provider == "mistral":
            return self._generate_mistral(prompt, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def _generate_ollama(self, prompt: str, max_tokens: int) -> str:
        """Generate using Ollama API (free, local)."""
        url = f"{self.base_url}/api/generate"
        
        # Ollama models may have tags (e.g., "phi:latest")
        # Use the model name as-is (should include tag if needed)
        model_name = self.model
        
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.3,  # Slightly higher to reduce repetition
                "num_ctx": 2048,  # Reduced context window for faster processing
                "repeat_penalty": 1.2,  # Penalize repetition (1.0 = no penalty, higher = more penalty)
            }
        }
        
        try:
            # Use a session with connection pooling, retries, and keep-alive
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                max_retries=requests.adapters.Retry(
                    total=3,
                    backoff_factor=0.5,
                    status_forcelist=[500, 502, 503, 504],
                    allowed_methods=["POST", "GET"],
                ),
                pool_connections=1,
                pool_maxsize=1,
            )
            session.mount('http://', adapter)
            
            # Add keep-alive headers
            headers = {
                'Connection': 'keep-alive',
                'Content-Type': 'application/json',
            }
            
            # Increased timeout for slow models (Ollama can take time, especially on CPU)
            # Connect timeout: 10s, Read timeout: 180s (3 minutes)
            response = session.post(url, json=payload, headers=headers, timeout=(10, 180))
            response.raise_for_status()
            result = response.json()
            return result.get("response", "").strip()
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Error: {str(e)[:200]}. "
                "Make sure Ollama is running: https://ollama.ai"
            )
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Ollama API error: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error calling Ollama: {type(e).__name__}: {str(e)[:200]}")
    
    def _generate_vllm(self, prompt: str, max_tokens: int) -> str:
        """Generate using vLLM (OpenAI-compatible API, much faster than Ollama)."""
        # vLLM uses OpenAI-compatible chat completions API
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,  # Slightly higher to reduce repetition
            "frequency_penalty": 0.5,  # Penalize frequent tokens to reduce repetition
            "presence_penalty": 0.3,  # Penalize already present tokens
            "stop": ["\n\n\n", "KYSYMYS:", "KONTEKSTI:", "VASTAUSOHJE:"],  # Stop on obvious repetition patterns
        }
        
        try:
            # First, test if the server is reachable by checking /v1/models
            try:
                test_url = f"{self.base_url}/v1/models"
                test_response = requests.get(test_url, timeout=5)
                if test_response.status_code != 200:
                    raise ConnectionError(
                        f"vLLM server at {self.base_url} returned status {test_response.status_code}. "
                        f"Make sure vLLM is running and accessible."
                    )
            except requests.exceptions.ConnectionError:
                # If /v1/models fails, try the chat endpoint anyway
                # (in case there's a network issue that might resolve)
                pass
            
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                max_retries=requests.adapters.Retry(
                    total=3,
                    backoff_factor=0.5,
                    status_forcelist=[500, 502, 503, 504],
                    allowed_methods=["POST", "GET"],
                ),
                pool_connections=1,
                pool_maxsize=1,
            )
            session.mount('http://', adapter)
            
            headers = {
                'Connection': 'keep-alive',
                'Content-Type': 'application/json',
            }
            
            # vLLM is much faster, shorter timeout is fine
            response = session.post(url, json=payload, headers=headers, timeout=(10, 60))
            response.raise_for_status()
            result = response.json()
            
            # OpenAI-compatible response format
            return result["choices"][0]["message"]["content"].strip()
        except requests.exceptions.ConnectionError as e:
            # Provide more helpful error message
            error_msg = str(e)
            if "host.docker.internal" in self.base_url:
                suggestion = (
                    f"Cannot connect to vLLM at {self.base_url}. "
                    f"If running in Docker/WSL, ensure vLLM is accessible from the container. "
                    f"Try: 1) Use 'localhost' instead of 'host.docker.internal' if both are in WSL, "
                    f"2) Ensure vLLM is bound to 0.0.0.0 (not 127.0.0.1), "
                    f"3) Check firewall settings. Error: {error_msg[:200]}"
                )
            else:
                suggestion = (
                    f"Cannot connect to vLLM at {self.base_url}. "
                    f"Error: {error_msg[:200]}. "
                    f"Make sure vLLM is running and accessible. "
                    f"Test with: curl {self.base_url}/v1/models"
                )
            raise ConnectionError(suggestion)
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"vLLM API error: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error calling vLLM: {type(e).__name__}: {str(e)[:200]}")
    
    def _generate_mistral(self, prompt: str, max_tokens: int) -> str:
        """Generate using Mistral API (requires API key)."""
        # Mistral chat API expects messages
        resp = self.client.chat.complete(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return resp.choices[0].message.content
