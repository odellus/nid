"""
Extension system - Reflective SDK for Crow agents.

This module provides the extension context and hook registry for extending
Crow agent behavior through callbacks/hooks.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session as SQLAlchemySession

from .session import Session
from .config import Config


@dataclass
class ExtensionContext:
    """
    Service-like interface for extensions.
    
    Extensions receive this context and can call methods to interact with
    the agent. This is more robust than direct attribute access.
    
    The context gives extensions access to:
    - Agent state (messages, tools, config)
    - Agent control (stop, restart, modify flow)
    - Database access
    - LLM access
    - Tool access
    - Hook management
    """
    
    # Agent references
    session: Session
    config: Config
    db_session: SQLAlchemySession
    
    # Internal state (not for extensions to access directly)
    _agent: Any = field(repr=False, default=None)  # Reference to Agent
    _hooks: Any = field(repr=False, default=None)  # Reference to HookRegistry
    
    # ========================================================================
    # MESSAGE ACCESS (Read-only, for inspection)
    # ========================================================================
    
    async def get_messages(self) -> List[dict]:
        """Get current conversation messages"""
        return self.session.messages.copy()
    
    async def get_latest_user_message(self) -> Optional[str]:
        """Get the latest user message"""
        for msg in reversed(self.session.messages):
            if msg.get("role") == "user" and msg.get("content"):
                return msg["content"]
        return None
    
    async def get_system_prompt(self) -> str:
        """Get the current system prompt"""
        for msg in self.session.messages:
            if msg.get("role") == "system" and msg.get("content"):
                return msg["content"]
        return ""
    
    # ========================================================================
    # MESSAGE MODIFICATION (Write, for injecting context)
    # ========================================================================
    
    async def inject_context(self, text: str, prepend: bool = False) -> None:
        """
        Inject context into the conversation.
        
        Args:
            text: Context to inject
            prepend: If True, inject before user message. If False, after.
        """
        if prepend:
            # Insert before the last user message
            for i in reversed(range(len(self.session.messages))):
                if self.session.messages[i].get("role") == "user":
                    self.session.messages.insert(i, {
                        "role": "user",
                        "content": text
                    })
                    self.session.add_message("user", text)
                    return
            # No user message found, append at the end
            self.session.messages.append({"role": "user", "content": text})
            self.session.add_message("user", text)
        else:
            # Append after the last user message
            self.session.messages.append({"role": "user", "content": text})
            self.session.add_message("user", text)
    
    async def modify_user_message(self, new_content: str) -> None:
        """
        Modify the latest user message.
        
        Args:
            new_content: New content for the user message
        """
        for i in reversed(range(len(self.session.messages))):
            if self.session.messages[i].get("role") == "user":
                self.session.messages[i]["content"] = new_content
                # TODO: Update the event in the database
                return
    
    # ========================================================================
    # AGENT CONTROL (Flow control)
    # ========================================================================
    
    async def stop_current_turn(self) -> None:
        """
        Stop the current react loop.
        
        This is used by compaction to interrupt the agent and start fresh.
        """
        # TODO: Implement this
        # This needs to signal the react loop to stop
        raise NotImplementedError("stop_current_turn not yet implemented")
    
    async def restart_with_new_session(self, new_system_prompt: Optional[str] = None) -> str:
        """
        Create a new session and restart the agent.
        
        Args:
            new_system_prompt: Optional new system prompt for the new session
            
        Returns:
            The new session_id
        """
        # TODO: Implement this
        # This needs to:
        # 1. Create a new session
        # 2. Load compressed history into the new session
        # 3. Return the new session_id
        raise NotImplementedError("restart_with_new_session not yet implemented")
    
    async def continue_with_current_session(self) -> None:
        """
        Continue with the current session after a stop.
        
        This is used after compaction to resume the agent.
        """
        # TODO: Implement this
        raise NotImplementedError("continue_with_current_session not yet implemented")
    
    # ========================================================================
    # SESSION MANAGEMENT
    # ========================================================================
    
    async def get_session_id(self) -> str:
        """Get the current session ID"""
        return self.session.session_id
    
    async def get_session_state(self, key: str) -> Any:
        """Get state from the session"""
        # TODO: Implement session state storage
        raise NotImplementedError("get_session_state not yet implemented")
    
    async def set_session_state(self, key: str, value: Any) -> None:
        """Set state in the session"""
        # TODO: Implement session state storage
        raise NotImplementedError("set_session_state not yet implemented")
    
    # ========================================================================
    # DATABASE ACCESS
    # ========================================================================
    
    async def query_db(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Query the database.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of rows
        """
        if params is None:
            params = {}
        
        result = self.db_session.execute(query, params)
        # Convert to list of dicts
        columns = result.keys()
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    
    async def execute_db(self, query: str, params: Optional[Dict] = None) -> None:
        """
        Execute a database write operation.
        
        Args:
            query: SQL query string
            params: Query parameters
        """
        if params is None:
            params = {}
        
        self.db_session.execute(query, params)
        self.db_session.commit()
    
    # ========================================================================
    # HOOK MANAGEMENT
    # ========================================================================
    
    def register_hook(self, point: str, hook: Callable) -> None:
        """
        Register a new hook at a specific point.
        
        Args:
            point: Hook point (pre_request, mid_react, post_react_loop, post_request)
            hook: Async function to call
        """
        if self._hooks is None:
            raise RuntimeError("HookRegistry not initialized")
        self._hooks.register(point, hook)
    
    def remove_hook(self, point: str, hook: Callable) -> None:
        """
        Remove a hook from a specific point.
        
        Args:
            point: Hook point
            hook: Hook function to remove
        """
        if self._hooks is None:
            raise RuntimeError("HookRegistry not initialized")
        self._hooks.remove(point, hook)
    
    def list_hooks(self, point: str) -> List[Callable]:
        """
        List all hooks registered at a specific point.
        
        Args:
            point: Hook point
            
        Returns:
            List of hook functions
        """
        if self._hooks is None:
            raise RuntimeError("HookRegistry not initialized")
        return self._hooks.list(point)
    
    # ========================================================================
    # LLM ACCESS
    # ========================================================================
    
    async def call_llm(
        self,
        messages: List[dict],
        **params
    ) -> dict:
        """
        Call the LLM directly.
        
        Args:
            messages: Conversation history
            **params: LLM parameters (temperature, top_p, etc.)
            
        Returns:
            LLM response with content and usage
        """
        # TODO: Implement this
        # This needs access to the LLM client
        raise NotImplementedError("call_llm not yet implemented")
    
    async def stream_llm(
        self,
        messages: List[dict],
        **params
    ):
        """
        Stream LLM responses.
        
        Args:
            messages: Conversation history
            **params: LLM parameters
            
        Yields:
            LLM response chunks
        """
        # TODO: Implement this
        raise NotImplementedError("stream_llm not yet implemented")
    
    # ========================================================================
    # TOOL ACCESS
    # ========================================================================
    
    async def call_tool(self, tool_name: str, args: dict) -> Any:
        """
        Call an MCP tool.
        
        Args:
            tool_name: Name of the tool
            args: Tool arguments
            
        Returns:
            Tool result
        """
        # TODO: Implement this
        # This needs access to the MCP client
        raise NotImplementedError("call_tool not yet implemented")
    
    async def list_tools(self) -> List[dict]:
        """List all available tools"""
        # TODO: Implement this
        raise NotImplementedError("list_tools not yet implemented")
    
    # ========================================================================
    # SKILL SYSTEM
    # ========================================================================
    
    async def load_skill(self, skill_name: str) -> SkillContext:
        """
        Load a skill and get its context.
        
        Args:
            skill_name: Name of the skill
            
        Returns:
            SkillContext with skill-specific methods
        """
        # TODO: Implement this
        raise NotImplementedError("load_skill not yet implemented")
    
    async def check_skill_relevance(self, skill_name: str, message: str) -> bool:
        """
        Check if a skill is relevant to a message.
        
        Args:
            skill_name: Name of the skill
            message: User message to check
            
        Returns:
            True if skill is relevant
        """
        # TODO: Implement this
        raise NotImplementedError("check_skill_relevance not yet implemented")
    
    # ========================================================================
    # METADATA
    # ========================================================================
    
    async def get_token_count(self) -> dict:
        """
        Get current token count.
        
        Returns:
            Dict with prompt_tokens, completion_tokens, total_tokens
        """
        # TODO: Implement this
        raise NotImplementedError("get_token_count not yet implemented")
    
    async def get_config(self) -> dict:
        """Get agent configuration"""
        return self.config.model_dump()
    
    async def get_timestamp(self) -> float:
        """Get current timestamp"""
        import time
        return time.time()
    
    # ========================================================================
    # UTILITY
    # ========================================================================
    
    async def log(self, level: str, message: str) -> None:
        """
        Log a message.
        
        Args:
            level: Log level (debug, info, warning, error)
            message: Log message
        """
        import logging
        logger = logging.getLogger("crow.extensions")
        getattr(logger, level)(message)
    
    async def sleep(self, seconds: float) -> None:
        """Sleep for a specified time"""
        await asyncio.sleep(seconds)
    
    async def raise_error(self, message: str) -> None:
        """
        Raise an error that will be handled by the agent.
        
        Args:
            message: Error message
        """
        raise RuntimeError(message)
    
    async def get_extension_state(self, key: str) -> Any:
        """Get state specific to this extension"""
        # TODO: Implement extension state storage
        raise NotImplementedError("get_extension_state not yet implemented")
    
    async def set_extension_state(self, key: str, value: Any) -> None:
        """Set state specific to this extension"""
        # TODO: Implement extension state storage
        raise NotImplementedError("set_extension_state not yet implemented")


@dataclass
class SkillContext:
    """
    Context for a specific skill.
    
    Skills are a special type of extension that can be loaded and reused.
    """
    
    name: str
    description: str
    context: ExtensionContext
    
    async def execute(self, user_message: str) -> str:
        """
        Execute the skill with the given user message.
        
        Args:
            user_message: User message to process
            
        Returns:
            Skill output
        """
        # TODO: Implement skill execution
        raise NotImplementedError("execute not yet implemented")
    
    async def is_relevant(self, user_message: str) -> bool:
        """
        Check if the skill is relevant to the user message.
        
        Args:
            user_message: User message to check
            
        Returns:
            True if skill is relevant
        """
        # TODO: Implement relevance check
        raise NotImplementedError("is_relevant not yet implemented")


class HookRegistry:
    """
    Registry for hooks at different points in the agent flow.
    
    Hooks are async functions that can modify agent behavior at specific points.
    """
    
    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = {
            "pre_request": [],
            "mid_react": [],
            "post_react_loop": [],
            "post_request": [],
        }
    
    def register(self, point: str, hook: Callable) -> None:
        """
        Register a hook at a specific point.
        
        Args:
            point: Hook point (pre_request, mid_react, post_react_loop, post_request)
            hook: Async function to call
        """
        if point not in self._hooks:
            raise ValueError(f"Unknown hook point: {point}")
        self._hooks[point].append(hook)
    
    def remove(self, point: str, hook: Callable) -> None:
        """
        Remove a hook from a specific point.
        
        Args:
            point: Hook point
            hook: Hook function to remove
        """
        if point not in self._hooks:
            raise ValueError(f"Unknown hook point: {point}")
        self._hooks[point].remove(hook)
    
    def list(self, point: str) -> List[Callable]:
        """
        List all hooks registered at a specific point.
        
        Args:
            point: Hook point
            
        Returns:
            List of hook functions
        """
        if point not in self._hooks:
            raise ValueError(f"Unknown hook point: {point}")
        return self._hooks[point].copy()
    
    async def run(self, point: str, ctx: ExtensionContext) -> None:
        """
        Run all hooks at a specific point.
        
        Args:
            point: Hook point
            ctx: Extension context
        """
        if point not in self._hooks:
            raise ValueError(f"Unknown hook point: {point}")
        
        for hook in self._hooks[point]:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(ctx)
                else:
                    hook(ctx)
            except Exception as e:
                import logging
                logger = logging.getLogger("crow.hooks")
                logger.error(f"Hook {hook} failed: {e}")
