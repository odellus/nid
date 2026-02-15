"""
Agent orchestration - ReAct loop with tools and LLM.

Encapsulates:
- LLM interaction
- Tool execution via MCP
- Response processing
- Main react loop
"""

import json
import traceback
from typing import Any

from fastmcp import Client
from openai import OpenAI

from .session import Session


class Agent:
    """
    Orchestration layer for the agent.
    
    Responsibilities:
    - Manage LLM interactions
    - Execute tools via MCP
    - Process streaming responses
    - Run the main ReAct loop
    """
    
    def __init__(
        self,
        session: Session,
        llm: OpenAI,
        mcp_client: Client,
        tools: list[dict],
        model: str,
    ):
        """
        Initialize agent with session and configuration.
        
        Args:
            session: Session instance for state management
            llm: OpenAI client instance
            mcp_client: FastMCP client instance
            tools: List of tool definitions
            model: Model identifier string
        """
        self.session = session
        self.llm = llm
        self.mcp_client = mcp_client
        self.tools = tools
        self.model = model
    
    def send_request(self):
        """
        Send request to LLM.
        
        Returns:
            Streaming response from LLM
        """
        return self.llm.chat.completions.create(
            model=self.model,
            messages=self.session.messages,
            tools=self.tools,
            stream=True,
        )
    
    def process_chunk(
        self,
        chunk,
        thinking: list[str],
        content: list[str],
        tool_calls: dict,
        tool_call_id: str | None,
    ) -> tuple[list[str], list[str], dict, str | None, tuple[str | None, Any]]:
        """
        Process a single streaming chunk.
        
        Args:
            chunk: Streaming chunk from LLM
            thinking: Accumulated thinking tokens
            content: Accumulated content tokens
            tool_calls: Accumulated tool calls
            tool_call_id: Current tool call ID
            
        Returns:
            Tuple of (thinking, content, tool_calls, tool_call_id, new_token)
        """
        delta = chunk.choices[0].delta
        new_token = (None, None)
        
        if not delta.tool_calls:
            if not hasattr(delta, "reasoning_content"):
                verbal_chunk = delta.content
                if verbal_chunk:
                    content.append(verbal_chunk)
                    new_token = ("content", verbal_chunk)
            else:
                reasoning_chunk = delta.reasoning_content
                if reasoning_chunk:
                    thinking.append(reasoning_chunk)
                    new_token = ("thinking", reasoning_chunk)
        else:
            for call in delta.tool_calls:
                if call.id is not None:
                    tool_call_id = call.id
                    if call.id not in tool_calls:
                        tool_calls[call.id] = {
                            "function_name": call.function.name,
                            "arguments": [call.function.arguments],
                        }
                        new_token = (
                            "tool_call",
                            (call.function.name, call.function.arguments),
                        )
                else:
                    arg_fragment = call.function.arguments
                    tool_calls[tool_call_id]["arguments"].append(arg_fragment)
                    new_token = ("tool_args", arg_fragment)
        
        return thinking, content, tool_calls, tool_call_id, new_token
    
    def process_response(self, response):
        """
        Process streaming response from LLM.
        
        Args:
            response: Streaming response from LLM
            
        Yields:
            Tuple of (message_type, token) for each chunk
            
        Returns:
            Tuple of (thinking, content, tool_call_inputs, usage) when done
        """
        thinking, content, tool_calls, tool_call_id = [], [], {}, None
        final_usage = None
        
        for chunk in response:
            # Capture usage from the chunk (if present)
            if hasattr(chunk, "usage") and chunk.usage:
                final_usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }
            
            thinking, content, tool_calls, tool_call_id, new_token = self.process_chunk(
                chunk, thinking, content, tool_calls, tool_call_id
            )
            msg_type, token = new_token
            if msg_type:
                yield msg_type, token
        
        return thinking, content, self.process_tool_call_inputs(tool_calls), final_usage
    
    def process_tool_call_inputs(self, tool_calls: dict) -> list[dict]:
        """
        Process tool call inputs into OpenAI format.
        
        Args:
            tool_calls: Dictionary of tool calls
            
        Returns:
            List of tool call objects in OpenAI format
        """
        tool_call_inputs = []
        for tool_call_id, tool_call in tool_calls.items():
            tool_call_inputs.append({
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": tool_call["function_name"],
                    "arguments": "".join(tool_call["arguments"]),
                },
            })
        return tool_call_inputs
    
    async def execute_tool_calls(self, tool_call_inputs: list[dict]) -> list[dict]:
        """
        Execute tool calls via MCP.
        
        Args:
            tool_call_inputs: List of tool calls to execute
            
        Returns:
            List of tool results
        """
        tool_results = []
        for tool_call in tool_call_inputs:
            result = await self.mcp_client.call_tool(
                tool_call["function"]["name"],
                json.loads(tool_call["function"]["arguments"]),
            )
            tool_results.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result.content[0].text,
            })
        return tool_results
    
    async def react_loop(self, max_turns: int = 50000):
        """
        Main ReAct loop.
        
        Args:
            max_turns: Maximum number of turns to execute
            
        Yields:
            Dictionary with 'type' and 'token' or 'messages' keys
        """
        for _ in range(max_turns):
            # Send request to LLM
            response = self.send_request()
            
            # Process streaming response
            gen = self.process_response(response)
            while True:
                try:
                    msg_type, token = next(gen)
                    yield {"type": msg_type, "token": token}
                except StopIteration as e:
                    thinking, content, tool_call_inputs, usage = e.value
                    break
            
            # If no tool calls, we're done
            if not tool_call_inputs:
                self.session.add_assistant_response(thinking, content, [], [])
                yield {"type": "final_history", "messages": self.session.messages}
                return
            
            # Execute tools
            tool_results = await self.execute_tool_calls(tool_call_inputs)
            
            # Add response to session
            self.session.add_assistant_response(
                thinking, content, tool_call_inputs, tool_results
            )
