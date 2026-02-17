"""
Callback hooks for persistence and skills.

These are the interfaces that external packages (crow-persistence, crow-skills)
implement to extend crow-acp functionality.

Pre-request hooks (skills): Modify state before LLM call
Post-response hooks (persistence): Save state after LLM response
"""

from abc import ABC, abstractmethod
from typing import Any, Callable

from .state import Event, SessionState


# Type aliases for clarity
PreRequestHook = Callable[[SessionState], None]
PostResponseHook = Callable[[SessionState, list[Event]], None]
OnShutdownHook = Callable[[SessionState], None]


class PersistenceBackend(ABC):
    """
    Abstract interface for persistence backends.
    
    Implement this in crow-persistence-sqlite, crow-persistence-json, etc.
    The agent calls these methods at appropriate times.
    """
    
    @abstractmethod
    async def save_session(self, state: SessionState) -> None:
        """
        Save/update session metadata.
        
        Called when session is created or config changes.
        """
        pass
    
    @abstractmethod
    async def save_events(
        self, 
        session_id: str, 
        events: list[Event],
        is_flush: bool = False,
    ) -> None:
        """
        Save events to persistence.
        
        Args:
            session_id: The session ID
            events: List of events to save
            is_flush: True if this is a forced flush (shutdown, interrupt)
        
        This may be called incrementally (every N events) or as a flush.
        """
        pass
    
    @abstractmethod
    async def load_session(self, session_id: str) -> SessionState | None:
        """
        Load session state from persistence.
        
        Returns None if session doesn't exist.
        """
        pass
    
    @abstractmethod
    async def load_events(self, session_id: str) -> list[Event]:
        """
        Load all events for a session.
        
        Used to reconstruct conversation history on load_session.
        """
        pass
    
    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        """Delete a session and all its events."""
        pass


class EventQueue:
    """
    Batches events for persistence.
    
    Flushes when:
    - Queue reaches max_size events
    - Time since last flush exceeds max_age_seconds
    - Manual flush() is called (shutdown, interrupt)
    """
    
    def __init__(
        self,
        backend: PersistenceBackend,
        max_size: int = 50,
        max_age_seconds: float = 30.0,
    ):
        self.backend = backend
        self.max_size = max_size
        self.max_age_seconds = max_age_seconds
        
        self._queue: list[tuple[str, Event]] = []  # (session_id, event)
        self._last_flush: float = 0.0
        self._session_id: str | None = None
    
    def add(self, session_id: str, event: Event) -> None:
        """Add an event to the queue."""
        self._session_id = session_id
        self._queue.append((session_id, event))
    
    def should_flush(self) -> bool:
        """Check if we should flush based on size or time."""
        import time
        if len(self._queue) >= self.max_size:
            return True
        if time.time() - self._last_flush >= self.max_age_seconds:
            return True
        return False
    
    async def flush_if_needed(self) -> None:
        """Flush if conditions are met."""
        if self.should_flush():
            await self.flush()
    
    async def flush(self) -> None:
        """Force flush all queued events."""
        if not self._queue:
            return
        
        # Group by session_id
        by_session: dict[str, list[Event]] = {}
        for session_id, event in self._queue:
            if session_id not in by_session:
                by_session[session_id] = []
            by_session[session_id].append(event)
        
        # Save each session's events
        for session_id, events in by_session.items():
            await self.backend.save_events(session_id, events, is_flush=True)
        
        # Clear queue
        self._queue.clear()
        
        import time
        self._last_flush = time.time()
    
    async def force_flush(self) -> None:
        """Force flush - called on shutdown/interrupt."""
        await self.flush()


class HookRegistry:
    """
    Registry for callback hooks.
    
    Skills register pre-request hooks.
    Persistence registers post-response hooks.
    """
    
    def __init__(self):
        self._pre_request_hooks: list[PreRequestHook] = []
        self._post_response_hooks: list[PostResponseHook] = []
        self._on_shutdown_hooks: list[OnShutdownHook] = []
    
    def register_pre_request(self, hook: PreRequestHook) -> None:
        """Register a pre-request hook (skills)."""
        self._pre_request_hooks.append(hook)
    
    def register_post_response(self, hook: PostResponseHook) -> None:
        """Register a post-response hook (persistence)."""
        self._post_response_hooks.append(hook)
    
    def register_on_shutdown(self, hook: OnShutdownHook) -> None:
        """Register an on-shutdown hook."""
        self._on_shutdown_hooks.append(hook)
    
    async def run_pre_request(self, state: SessionState) -> None:
        """Run all pre-request hooks."""
        for hook in self._pre_request_hooks:
            result = hook(state)
            if result is not None and hasattr(result, '__await__'):
                await result
    
    async def run_post_response(
        self, 
        state: SessionState, 
        events: list[Event]
    ) -> None:
        """Run all post-response hooks."""
        for hook in self._post_response_hooks:
            result = hook(state, events)
            if result is not None and hasattr(result, '__await__'):
                await result
    
    async def run_on_shutdown(self, state: SessionState) -> None:
        """Run all on-shutdown hooks."""
        for hook in self._on_shutdown_hooks:
            result = hook(state)
            if result is not None and hasattr(result, '__await__'):
                await result
