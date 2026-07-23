"""Small helpers shared across routers."""

import asyncio
from datetime import datetime, timezone
from functools import partial


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_db(fn, *args, **kwargs):
    """Run a blocking DB call on the default executor so the event loop keeps serving."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(fn, *args, **kwargs))


def clean_json_response(text: str) -> str:
    """Strip ```-fenced wrappers that the model sometimes puts around JSON."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:] if lines[0].strip().startswith("```") else lines
        lines = lines[:-1] if lines and lines[-1].strip().startswith("```") else lines
        text = "\n".join(lines).strip()
    return text
