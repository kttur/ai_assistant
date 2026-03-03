from __future__ import annotations

from ai_assistant.core.models import TerminalCommandResult


def format_terminal_result_chunks(
    result: TerminalCommandResult,
    chunk_size: int = 3500,
) -> list[str]:
    header = f"[{result.shell}] $ {result.command}"
    parts = [header]
    if result.timed_out and result.error:
        parts.append(result.error)
    elif result.error:
        parts.append(f"Execution error: {result.error}")
    elif result.running:
        parts.append("Interactive process is running. Send next input or /exit to stop terminal mode.")
        if result.stdout.strip():
            parts.append(result.stdout.rstrip())
        if result.stderr.strip():
            parts.append("[stderr]")
            parts.append(result.stderr.rstrip())
    else:
        parts.append(f"Exit code: {result.exit_code}")
        if result.stdout.strip():
            parts.append(result.stdout.rstrip())
        if result.stderr.strip():
            parts.append("[stderr]")
            parts.append(result.stderr.rstrip())

    full_text = "\n".join(parts).strip()
    if not full_text:
        full_text = "(no output)"

    chunks: list[str] = []
    while full_text:
        chunks.append(full_text[:chunk_size])
        full_text = full_text[chunk_size:]
    return chunks
