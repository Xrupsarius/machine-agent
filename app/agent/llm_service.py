import logging
import ollama

log = logging.getLogger("agent")


class OllamaConnectionError(Exception):
    pass


class LLMService:
    """
    Single gateway for all LLM calls. ADR-002: no other module may import ollama.
    """

    def __init__(self, model: str, host: str) -> None:
        self._model = model
        self._client = ollama.Client(host=host)
        log.info(f"LLMService created (model={model}, host={host})")

    def generate(
        self,
        prompt: str,
        system: str = "",
        *,
        json_output: bool = False,
        think: bool = False,
    ) -> str:
        try:
            resp = self._client.generate(
                model=self._model,
                prompt=prompt,
                system=system if system else None,
                format="json" if json_output else None,
                think=think,
                keep_alive="30m",
            )
            return resp.response
        except Exception as e:
            raise OllamaConnectionError(f"Ollama unavailable: {e}") from e

    def chat(
        self,
        messages: list[dict],
        *,
        json_output: bool = False,
        think: bool = False,
    ) -> str:
        try:
            resp = self._client.chat(
                model=self._model,
                messages=messages,
                format="json" if json_output else None,
                think=think,
                keep_alive="30m",
            )
            return resp.message.content
        except Exception as e:
            raise OllamaConnectionError(f"Ollama unavailable: {e}") from e

    def is_available(self) -> bool:
        try:
            self._client.list()
            return True
        except Exception:
            return False

    @property
    def model(self) -> str:
        return self._model
