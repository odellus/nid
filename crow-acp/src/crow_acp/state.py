"""
In-memory session state with Pydantic models.

This is the core state that crow-acp manages. Persistence is handled
via callbacks to external plugins (crow-persistence).
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of events in a session."""
    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    ASSISTANT_THINKING = "assistant_thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class Event(BaseModel):
    """
    A single event in the conversation.
    
    Events are aggregated messages - not individual tokens.
    One event = one complete message/tool-call/tool-result.
    """
    event_type: EventType
    conv_index: int  # Linear order in conversation
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Message content
    content: str | None = None
    reasoning_content: str | None = None  # For thinking tokens
    
    # Tool call fields
    tool_call_id: str | None = None
    tool_call_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    
    # Usage tracking (optional, for assistant messages)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    
    # Additional metadata
    event_metadata: dict[str, Any] | None = None
    
    def to_openai_message(self) -> dict[str, Any]:
        """Convert event to OpenAI message format for LLM."""
        msg: dict[str, Any] = {"role": self.event_type.value.split("_")[0]}
        
        if self.content is not None:
            msg["content"] = self.content
        if self.reasoning_content is not None:
            msg["reasoning_content"] = self.reasoning_content
        if self.tool_call_id is not None:
            msg["tool_call_id"] = self.tool_call_id
        if self.tool_call_name is not None:
            msg["function"] = {
                "name": self.tool_call_name,
                "arguments": self.tool_arguments or {}
            }
        
        return msg


class SessionState(BaseModel):
    """
    In-memory state for a single session.
    
    This is what crow-acp manages directly. Persistence is delegated
    to callbacks so we don't couple to any specific storage backend.
    """
    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # The conversation history (OpenAI format)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    
    # Event log (for persistence/replay)
    events: list[Event] = Field(default_factory=list)
    
    # Session config
    system_prompt: str = ""
    tool_definitions: list[dict[str, Any]] = Field(default_factory=list)
    model_identifier: str = "glm-5"
    request_params: dict[str, Any] = Field(default_factory=dict)
    
    # Runtime state
    conv_index: int = 0  # Current position in conversation
    is_active: bool = True
    
    def add_user_message(self, content: str) -> Event:
        """Add a user message to the session."""
        event = Event(
            event_type=EventType.USER_MESSAGE,
            conv_index=self.conv_index,
            content=content,
        )
        self.events.append(event)
        self.messages.append({"role": "user", "content": content})
        self.conv_index += 1
        return event
    
    def add_assistant_message(
        self,
        content: str | None = None,
        reasoning_content: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> Event:
        """Add an assistant message to the session."""
        event = Event(
            event_type=EventType.ASSISTANT_MESSAGE,
            conv_index=self.conv_index,
            content=content,
            reasoning_content=reasoning_content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        self.events.append(event)
        
        # Build message for LLM
        msg: dict[str, Any] = {"role": "assistant"}
        if content:
            msg["content"] = content
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content
        self.messages.append(msg)
        
        self.conv_index += 1
        return event
    
    def add_tool_call(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_arguments: dict[str, Any],
    ) -> Event:
        """Add a tool call to the session."""
        event = Event(
            event_type=EventType.TOOL_CALL,
            conv_index=self.conv_index,
            tool_call_id=tool_call_id,
            tool_call_name=tool_name,
            tool_arguments=tool_arguments,
        )
        self.events.append(event)
        
        # Add to messages as assistant tool_calls
        # Note: We might need to merge with previous assistant message
        # For now, we append as separate message with tool_calls
        import json
        self.messages.append({
            "role": "assistant",
            "tool_calls": [{
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(tool_arguments),
                }
            }]
        })
        
        self.conv_index += 1
        return event
    
    def add_tool_result(
        self,
        tool_call_id: str,
        content: str,
    ) -> Event:
        """Add a tool result to the session."""
        event = Event(
            event_type=EventType.TOOL_RESULT,
            conv_index=self.conv_index,
            tool_call_id=tool_call_id,
            content=content,
        )
        self.events.append(event)
        
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })
        
        self.conv_index += 1
        return event
    
    def get_events_since(self, conv_index: int) -> list[Event]:
        """Get all events after a given index (for incremental persistence)."""
        return [e for e in self.events if e.conv_index >= conv_index]
    
    def to_persistence_dict(self) -> dict[str, Any]:
        """Serialize session state for persistence."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "system_prompt": self.system_prompt,
            "tool_definitions": self.tool_definitions,
            "model_identifier": self.model_identifier,
            "request_params": self.request_params,
            "conv_index": self.conv_index,
        }
    
    @classmethod
    def from_persistence_dict(cls, data: dict[str, Any]) -> "SessionState":
        """Deserialize session state from persistence."""
        return cls(
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            system_prompt=data.get("system_prompt", ""),
            tool_definitions=data.get("tool_definitions", []),
            model_identifier=data.get("model_identifier", "glm-5"),
            request_params=data.get("request_params", {}),
            conv_index=data.get("conv_index", 0),
        )
