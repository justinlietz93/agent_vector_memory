"""Prompt Formatter Service for UI layer.

Purpose:
    Generate structured prompt envelopes that include retrieved vector memory
    snippets so downstream UI widgets can display rich context alongside the
    original prompt text.

External Dependencies:
    Relies only on the Python standard library (``json`` and ``datetime``);
    performs no CLI or HTTP calls.

Fallback Semantics:
    No fallbacks are implemented. All formatting operations either succeed or
    raise the underlying exception to the caller.

Timeout Strategy:
    Not applicable. All operations are purely in-memory transformations.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, List

from ...shared.dto import QueryRequest, QueryResponse


class PromptFormatter:
    """Format query prompts and associated vector memory into UI-ready text.

    The formatter is responsible for emitting deterministic XML envelopes that
    encapsulate relevance metadata, retrieved snippets, and their associated
    metadata. The class is stateless and safe for reuse across threads provided
    callers avoid mutating the supplied DTOs while formatting is in progress.
    """

    def format_with_vector_memory(self, request: QueryRequest, response: QueryResponse) -> str:
        """Compose the original prompt and vector memory envelope.

        Args:
            request: Query information describing the originating prompt and
                retrieval parameters.
            response: Retrieval results produced by the vector memory service.

        Returns:
            str: Concatenation of the original prompt text and the generated
            ``<vector_memory>`` XML envelope separated by two newlines.

        Raises:
            ValueError: Propagated when the response payload cannot be
                serialized (e.g., non-JSON-serializable metadata values).

        Side Effects:
            None. The method only reads from the provided DTOs.

        Timeout & Retries:
            Not applicable—no blocking I/O is performed.

        Notes:
            Policy: Only the top-1 memory from the retrieval results is
            injected into the formatted prompt. The query may retrieve ``k``
            items for display/inspection elsewhere in the UI, but the prompt
            envelope embeds only the highest-ranked item.
        """
        envelope = self._create_vector_memory_envelope(request, response)
        return f"{request.prompt}\n\n{envelope}"

    def _create_vector_memory_envelope(self, request: QueryRequest, response: QueryResponse) -> str:
        """Create the ``<vector_memory>`` XML envelope for recall results.

        Args:
            request: Query context containing collection metadata.
            response: Retrieved matches that should be embedded into the envelope.

        Returns:
            str: XML representation of the relevance block containing the
            retrieved items.

        Side Effects:
            None.

        Timeout & Retries:
            Not applicable.
        """
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")

        lines = [
            "<vector_memory>",
            f'  <relevance collection="{self._escape_xml(request.collection, for_attribute=True)}" '
            f'k="{request.k}" ts="{self._escape_xml(timestamp, for_attribute=True)}">',
        ]

        # Policy: inject only the top-1 memory into the formatted prompt.
        # We assume results are already sorted by relevance (highest first).
        if response.results:
            result = response.results[0]
            max_chars = 1500
            text = result.text_preview
            if len(text) > max_chars:
                text = f"{text[: max(0, max_chars - 3) ]}..."
            lines.extend(self._format_result_item(1, result, text))

        lines.extend([
            "  </relevance>",
            "</vector_memory>"
        ])

        return "\n".join(lines)

    def _format_result_item(self, index: int, result: Any, text: str) -> List[str]:
        """Format a single retrieval result into XML list elements.

        Args:
            index: One-based ordinal used for deterministic ordering in the
                envelope output.
            result: Retrieval match object exposing ``id``, ``score``,
                ``text_preview``, and ``metadata`` attributes.
            text: Possibly truncated text preview that will be emitted.

        Returns:
            List[str]: Individual XML lines representing the formatted item.

        Raises:
            KeyError: Propagated if ``result.metadata`` lacks expected keys
                mocked by downstream tests.

        Side Effects:
            None.

        Timeout & Retries:
            Not applicable.
        """
        lines = [
            f'    <item index="{index}" id="{self._escape_xml(result.id, for_attribute=True)}" '
            f'score="{result.score:.4f}">',
        ]

        if text:
            lines.append(f"      <text>{self._escape_xml(text)}</text>")
        else:
            lines.append("      <text />")

        # Add metadata excluding text_preview
        metadata = {k: v for k, v in result.metadata.items() if k != "text_preview"}
        if metadata:
            metadata_json = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
            lines.append(
                "      <other_metadata>"
                f"{self._escape_xml(metadata_json, preserve_quotes=True)}"
                "</other_metadata>"
            )
        else:
            lines.append("      <other_metadata>{}</other_metadata>")

        lines.append("    </item>")
        return lines

    def _escape_xml(
        self,
        text: str,
        *,
        for_attribute: bool = False,
        preserve_quotes: bool = False,
    ) -> str:
        """Escape XML-sensitive characters in element content or attributes.

        Args:
            text: Raw value to be inserted into the XML output.
            for_attribute: When ``True``, escape quotation marks so the value can
                be safely embedded inside an attribute.
            preserve_quotes: When ``True``, retain both single and double quotes
                in element text for JSON readability.

        Returns:
            str: Escaped text suitable for inclusion in XML content.

        Raises:
            TypeError: Propagated if ``text`` cannot be converted to ``str``.

        Side Effects:
            None.

        Timeout & Retries:
            Not applicable.
        """
        escaped = (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        if for_attribute or not preserve_quotes:
            escaped = escaped.replace('"', "&quot;").replace("'", "&apos;")

        return escaped
