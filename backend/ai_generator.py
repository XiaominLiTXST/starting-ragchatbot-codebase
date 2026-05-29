from typing import List, Optional

import anthropic


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    MAX_TOOL_ROUNDS = 2

    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Tool Usage:
- **Outline or structure questions** ("what is the outline", "list the lessons", "what lessons does X have"): use `get_course_outline`. Return the course title, course link, and every lesson as a numbered list showing the lesson number and lesson title.
- **Content or detail questions** about specific course material: use `search_course_content`.
- **General knowledge questions**: answer using existing knowledge without any tool call.
- Synthesize tool results into accurate, fact-based responses.
- If a tool returns no results, state this clearly without offering alternatives.

Multi-step reasoning:
- For complex questions that require information from multiple sources (e.g. "find a course that covers the same topic as lesson 4 of course X"), you may make up to 2 sequential tool calls — use the result of the first call to inform the second.
- After receiving tool results, synthesize them into a single answer without requesting further tools.
- For straightforward questions, a single tool call is sufficient.

Response Protocol:
- **No meta-commentary**: provide direct answers only — no reasoning process, tool explanations, or question-type analysis.
- Do not mention "based on the search results".

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with up to MAX_TOOL_ROUNDS sequential tool calls.

        Each round is a separate API request so Claude can reason about previous
        results before deciding whether to call another tool. Terminates when:
          (a) MAX_TOOL_ROUNDS rounds have been used up,
          (b) Claude's response contains no tool_use block, or
          (c) a tool call raises an exception.
        In cases (a) and (c) a final synthesis call is made without tools.
        """
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages = [{"role": "user", "content": query}]
        has_tools = bool(tools and tool_manager)

        for _ in range(self.MAX_TOOL_ROUNDS):
            api_params = {
                **self.base_params,
                "messages": messages,
                "system": system_content,
            }
            if has_tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = {"type": "auto"}

            response = self.client.messages.create(**api_params)

            # Termination (b): Claude answered directly — return immediately
            if response.stop_reason != "tool_use" or not has_tools:
                return response.content[0].text

            # Append Claude's tool_use turn to the growing transcript
            messages.append({"role": "assistant", "content": response.content})

            # Execute every tool call requested in this round
            tool_results = []
            execution_failed = False
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result = tool_manager.execute_tool(block.name, **block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            }
                        )
                    except Exception as exc:
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Tool '{block.name}' raised an error: {exc}",
                                "is_error": True,
                            }
                        )
                        execution_failed = True
                        break

            messages.append({"role": "user", "content": tool_results})

            if execution_failed:
                # Termination (c): skip remaining rounds, fall through to synthesis
                break

        # Termination (a)/(c): synthesis call without tools so Claude must answer
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content,
        }
        final_response = self.client.messages.create(**final_params)
        return final_response.content[0].text
