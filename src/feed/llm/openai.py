"""OpenAI implementation of the LLM client interface."""

from openai import OpenAI
from pydantic import BaseModel

from .base import LLMError, LLMResponse


class OpenAIClient:
    """OpenAI LLM provider."""

    def __init__(
        self,
        api_key: str,
        model: str,
        reasoning_effort: str = "xhigh",
        timeout: float = 120,
    ):
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.model = model
        self.reasoning_effort = reasoning_effort

    def generate(
        self,
        prompt: str,
        system: str,
        response_schema: type[BaseModel],
    ) -> LLMResponse:
        """Generate structured output with OpenAI Responses and normalize it."""
        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=system,
                input=prompt,
                text_format=response_schema,
                reasoning={"effort": self.reasoning_effort},
            )
        except Exception as exc:  # pragma: no cover - provider SDK behavior
            raise LLMError(f"OpenAI API call failed: {exc}") from exc

        parsed_output = getattr(response, "output_parsed", None)
        if parsed_output is None:
            raise LLMError("OpenAI response did not contain structured output")
        if isinstance(parsed_output, BaseModel):
            parsed = parsed_output.model_dump()
        elif isinstance(parsed_output, dict):
            parsed = parsed_output
        else:
            raise LLMError("OpenAI response contained an unsupported structured output type")

        raw_text = str(getattr(response, "output_text", "") or "")

        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
        output_details = getattr(usage, "output_tokens_details", None) if usage else None
        reasoning_tokens = int(getattr(output_details, "reasoning_tokens", 0) or 0)

        return LLMResponse(
            parsed=parsed,
            raw_text=raw_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
        )
