"""Generation step: send the retrieval-grounded system prompt + conversation
history to whichever provider the user picked in the UI, using each
provider's official SDK. The API key comes from the request body (entered
by the user in the frontend) and is never persisted server-side.

Model choice: Claude Opus 5 (`claude-opus-5`) is Anthropic's current
default per this project's tooling guidance. `gpt-5` is used for OpenAI as
the current flagship at the time this was written — since model lineups
move fast, double-check it's still current and adjust OPENAI_MODEL below
if not.

Both ANTHROPIC_MODEL and OPENAI_MODEL are current-generation reasoning
models: some of MAX_TOKENS is spent on invisible reasoning/thinking before
any visible answer text is produced. MAX_TOKENS is set well above the
~200-300 word answers these prompts ask for specifically to leave that
headroom — if it's set too low, the model can spend its entire budget on
reasoning and return empty visible text with finish_reason/stop_reason
"length"/"max_tokens", which is caught below and raised as a ProviderError
rather than silently shown as "couldn't generate a response."
"""
import anthropic
import openai

ANTHROPIC_MODEL = "claude-opus-5"
OPENAI_MODEL = "gpt-5"
MAX_TOKENS = 55000


class ProviderError(Exception):
    pass


def call_anthropic(api_key, system_prompt, messages, max_tokens=MAX_TOKENS):
    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
    except anthropic.AuthenticationError:
        raise ProviderError("Anthropic rejected the API key — check it's correct.")
    except anthropic.NotFoundError:
        raise ProviderError(f"Anthropic model '{ANTHROPIC_MODEL}' was not found.")
    except anthropic.RateLimitError:
        raise ProviderError("Anthropic rate limit hit — wait a moment and try again.")
    except anthropic.APIStatusError as e:
        raise ProviderError(f"Anthropic API error ({e.status_code}): {e.message}")
    except anthropic.APIConnectionError:
        raise ProviderError("Could not reach the Anthropic API — check your network.")

    if response.stop_reason == "refusal":
        raise ProviderError("Anthropic declined to answer this request.")

    text_blocks = [b.text for b in response.content if b.type == "text"]
    answer = "\n".join(text_blocks)
    if not answer:
        if response.stop_reason == "max_tokens":
            raise ProviderError(
                f"Anthropic ran out of tokens (max_tokens={max_tokens}) before producing visible "
                "text — likely spent on thinking. Try again, or raise MAX_TOKENS in providers.py."
            )
        raise ProviderError(f"Anthropic returned no text (stop_reason={response.stop_reason}).")
    return answer


def call_openai(api_key, system_prompt, messages, max_tokens=MAX_TOKENS):
    client = openai.OpenAI(api_key=api_key)
    openai_messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m["content"]} for m in messages
    ]
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=max_tokens,
            messages=openai_messages,
        )
    except openai.AuthenticationError:
        raise ProviderError("OpenAI rejected the API key — check it's correct.")
    except openai.NotFoundError:
        raise ProviderError(f"OpenAI model '{OPENAI_MODEL}' was not found.")
    except openai.RateLimitError:
        raise ProviderError("OpenAI rate limit hit — wait a moment and try again.")
    except openai.APIStatusError as e:
        raise ProviderError(f"OpenAI API error ({e.status_code}): {e.message}")
    except openai.APIConnectionError:
        raise ProviderError("Could not reach the OpenAI API — check your network.")

    choice = response.choices[0]
    if choice.finish_reason == "content_filter":
        raise ProviderError("OpenAI declined to answer this request.")

    if not choice.message.content:
        if choice.finish_reason == "length":
            raise ProviderError(
                f"OpenAI ran out of tokens (max_completion_tokens={max_tokens}) before producing "
                "visible text — likely spent on reasoning. Try again, or raise MAX_TOKENS in providers.py."
            )
        raise ProviderError(f"OpenAI returned no text (finish_reason={choice.finish_reason}).")
    return choice.message.content
