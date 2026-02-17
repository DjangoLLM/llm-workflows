import asyncio
import json
import logging
import os
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, AsyncIterator, Dict, Any, List, Callable
from collections import defaultdict

# Configure logging for CLI interactions
#
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OutputFormat(Enum):
    """
    Supported output formats for CLI commands.
    """
    TEXT = "text"
    JSON = "json"
    STREAM_JSON = "stream_json"


@dataclass
class CLIEvent:
    """
    Unified event structure for both Codex and Gemini CLIs.
    
    *   `type`: The event type (e.g., content, tool_call, done).
    *   `data`: The parsed JSON data for the event.
    *   `raw`: The original raw string from the stream.
    *   `timestamp`: When the event was received.
    """
    type: str
    data: Dict[str, Any]
    raw: str
    timestamp: float


@dataclass
class CLIResponse:
    """
    Complete response with metadata from a CLI execution.
    
    *   `final_output`: The accumulated text output.
    *   `events`: List of all events received during execution.
    *   `session_id`: Unique identifier for the conversation session.
    *   `exit_code`: The process exit code.
    *   `usage`: Token or resource usage statistics if available.
    *   `stderr`: Captured stderr output for debugging.
    """
    final_output: str
    events: List[CLIEvent]
    session_id: Optional[str]
    exit_code: int
    usage: Optional[Dict[str, Any]]
    stderr: str


class AuthenticationError(Exception):
    """
    Raised when CLI authentication fails.
    """
    pass


class BaseCLIWrapper(ABC):
    """
    Base class for CLI wrappers providing common execution logic.
    
    This class handles the asynchronous execution of subprocesses,
    streaming of stdout/stderr, and basic event parsing.
    """
    
    def __init__(
        self,
        working_dir: Optional[Path] = None,
        env_vars: Optional[Dict[str, str]] = None,
        timeout: int = 300
    ):
        """
        Initialize the base CLI wrapper.
        
        :param working_dir: The directory to run commands in.
        :param env_vars: Specific environment variables to set.
        :param timeout: Maximum execution time in seconds.
        """
        # Set working directory or use current
        #
        self.working_dir = working_dir or Path.cwd()
        
        # Merge provided env vars
        #
        self.env_vars = env_vars or {}
        
        # execution timeout
        #
        self.timeout = timeout
        
        # Track session ID for resumption
        #
        self.session_id: Optional[str] = None
        
    @abstractmethod
    def build_command(
        self,
        prompt: str,
        output_format: OutputFormat,
        **kwargs
    ) -> List[str]:
        """
        Build the CLI command with appropriate arguments.
        
        :param prompt: The user prompt to execute.
        :param output_format: Requested output format.
        :param kwargs: Additional CLI-specific arguments.
        :return: List of command arguments.
        """
        pass
    
    @abstractmethod
    def parse_event(self, line: str) -> Optional[CLIEvent]:
        """
        Parse a single line of output into a CLIEvent.
        
        :param line: The raw output line from the CLI.
        :return: A CLIEvent instance or None if unparseable.
        """
        pass
    
    async def execute(
        self,
        prompt: str,
        output_format: OutputFormat = OutputFormat.STREAM_JSON,
        on_event: Optional[Callable[[CLIEvent], None]] = None,
        stdin_data: Optional[str] = None,
        **kwargs
    ) -> CLIResponse:
        """
        Execute a CLI command with streaming support.
        
        :param prompt: The input prompt for the model.
        :param output_format: How the CLI should return data.
        :param on_event: Optional callback for each received event.
        :param stdin_data: Optional data to pipe to command stdin.
        :param kwargs: Additional arguments for building the command.
        :return: A CLIResponse object.
        """
        
        # Generate command arguments
        #
        cmd = self.build_command(prompt, output_format, **kwargs)
        logger.info(f"Executing: {' '.join(cmd)}")
        
        # Prepare execution environment
        #
        env = {**os.environ, **self.env_vars}
        
        events: List[CLIEvent] = []
        stderr_lines: List[str] = []
        final_output: List[str] = []
        
        try:
            # Launch subprocess with piped streams
            #
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if stdin_data else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.working_dir),
                env=env
            )
            
            # Handle stdin if data is provided
            #
            if stdin_data and process.stdin:
                process.stdin.write(stdin_data.encode('utf-8'))
                await process.stdin.drain()
                process.stdin.close()
            
            # Stream stdout and stderr concurrently
            #
            await asyncio.gather(
                self._read_stream(
                    process.stdout,
                    output_format,
                    events,
                    final_output,
                    on_event
                ),
                self._read_stderr(process.stderr, stderr_lines)
            )
            
            # Wait for process termination
            #
            try:
                exit_code = await asyncio.wait_for(
                    process.wait(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                # Terminate process on timeout
                #
                process.kill()
                raise TimeoutError(f"Command timed out after {self.timeout}s")
            
            return CLIResponse(
                final_output="\n".join(final_output),
                events=events,
                session_id=self.session_id,
                exit_code=exit_code,
                usage=self._extract_usage(events),
                stderr="\n".join(stderr_lines)
            )
            
        except Exception as e:
            # Log failure details
            #
            logger.error(f"Execution failed: {e}")
            raise
    
    async def _read_stream(
        self,
        stream: asyncio.StreamReader,
        output_format: OutputFormat,
        events: List[CLIEvent],
        final_output: List[str],
        on_event: Optional[Callable]
    ):
        """
        Read and parse the stdout stream in chunks.
        
        :param stream: The StreamReader for stdout.
        :param output_format: The format used for parsing.
        :param events: Accumulator for parsed events.
        :param final_output: Accumulator for text content.
        :param on_event: Optional callback for processing events.
        """
        while True:
            line_bytes = await stream.readline()
            if not line_bytes:
                break
                
            line = line_bytes.decode('utf-8').strip()
            
            if output_format in [OutputFormat.JSON, OutputFormat.STREAM_JSON]:
                # Attempt to parse as JSON event
                #
                event = self.parse_event(line)
                if event:
                    events.append(event)
                    
                    # Notify listener if present
                    #
                    if on_event:
                        on_event(event)
                    
                    # Update session tracking
                    #
                    if event.type in ["thread.started", "session.started"]:
                        self.session_id = event.data.get("thread_id") or event.data.get("session_id")
                    
                    # Collect content for final output
                    #
                    if event.type in ["item.completed", "content", "done"]:
                        # Check various common locations for text/content
                        #
                        if "text" in event.data:
                            final_output.append(event.data["text"])
                        elif "content" in event.data:
                            final_output.append(event.data["content"])
                        elif "item" in event.data:
                            item = event.data["item"]
                            if isinstance(item, dict):
                                if "text" in item:
                                    final_output.append(item["text"])
                                elif "content" in item:
                                    final_output.append(item["content"])
            else:
                # Text mode - collect raw lines
                #
                final_output.append(line)
    
    async def _read_stderr(
        self,
        stream: asyncio.StreamReader,
        stderr_lines: List[str]
    ):
        """
        Read the stderr stream for logs and errors.
        
        :param stream: The StreamReader for stderr.
        :param stderr_lines: Accumulator for stderr output.
        """
        while True:
            line_bytes = await stream.readline()
            if not line_bytes:
                break
            line = line_bytes.decode('utf-8').strip()
            stderr_lines.append(line)
            
            # Log debug info from stderr
            #
            logger.debug(f"stderr: {line}")
    
    @abstractmethod
    def _extract_usage(self, events: List[CLIEvent]) -> Optional[Dict[str, Any]]:
        """
        Extract resource usage information from events.
        
        :param events: List of events to scan.
        :return: usage dictionary or None.
        """
        pass


class CodexCLIWrapper(BaseCLIWrapper):
    """
    Wrapper for the OpenAI Codex CLI.
    
    Handles session resumption, sandboxing, and JSONL events.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        working_dir: Optional[Path] = None,
        **kwargs
    ):
        """
        Initialize Codex CLI wrapper.
        
        :param api_key: Optional API key; if missing, relies on system auth.
        :param working_dir: Path to project context.
        """
        env_vars = {}
        if api_key:
            env_vars["CODEX_API_KEY"] = api_key
        
        super().__init__(
            working_dir=working_dir,
            env_vars=env_vars,
            **kwargs
        )
    
    def build_command(
        self,
        prompt: str,
        output_format: OutputFormat,
        sandbox: str = "read-only",
        full_auto: bool = False,
        output_schema: Optional[Path] = None,
        resume_last: bool = False,
        resume_session: Optional[str] = None,
        **kwargs
    ) -> List[str]:
        """
        Construct the 'codex exec' command.
        
        :param prompt: User prompt.
        :param output_format: Format (supports JSON).
        :param sandbox: Sandbox permission level (read-only, workspace-write, danger-full-access).
        :param full_auto: Enable full-auto execution.
        :param output_schema: Path to JSON schema for structured output.
        :param resume_last: Resume the very last session.
        :param resume_session: Resume specific session ID.
        :return: List of command arguments.
        """
        
        cmd = ["codex", "exec"]
        
        # Handle session resumption logic
        #
        if resume_last or resume_session:
            cmd.append("resume")
            if resume_last:
                cmd.append("--last")
            elif resume_session:
                cmd.append(resume_session)
        
        # Configure output format
        #
        if output_format != OutputFormat.TEXT:
            cmd.append("--json")
        
        # Set execution flags
        #
        if full_auto:
            cmd.append("--full-auto")
        
        cmd.extend(["--sandbox", sandbox])
        
        # Apply structured output schema
        #
        if output_schema:
            cmd.extend(["--output-schema", str(output_schema)])
        
        # Prompt is usually the final argument
        #
        cmd.append(prompt)
        
        return cmd
    
    def parse_event(self, line: str) -> Optional[CLIEvent]:
        """
        Parse Codex JSONL events.
        
        :param line: JSON string from stream.
        :return: Typed CLIEvent.
        """
        try:
            data = json.loads(line)
            event_type = data.get("type", "unknown")
            
            return CLIEvent(
                type=event_type,
                data=data,
                raw=line,
                timestamp=time.time()
            )
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON: {line}")
            return None
    
    def _extract_usage(self, events: List[CLIEvent]) -> Optional[Dict[str, Any]]:
        """
        Scan events for 'turn.completed' usage data.
        """
        for event in reversed(events):
            if event.type == "turn.completed" and "usage" in event.data:
                return event.data["usage"]
        return None
    
    async def resume(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        **kwargs
    ) -> CLIResponse:
        """
        Resume an existing session with a new prompt.
        
        :param prompt: The follow-up question/command.
        :param session_id: Session ID to continue.
        :return: CLIResponse.
        """
        return await self.execute(
            prompt,
            resume_session=session_id or self.session_id,
            **kwargs
        )

    async def execute_with_stdin(
        self,
        prompt: str,
        stdin_data: str,
        **kwargs
    ) -> CLIResponse:
        """
        Execute Codex with data piped to its stdin.
        
        :param prompt: User prompt.
        :param stdin_data: Multi-line string to pipe into stdin.
        :return: CLIResponse.
        """
        return await self.execute(
            prompt,
            stdin_data=stdin_data,
            **kwargs
        )


class GeminiCLIWrapper(BaseCLIWrapper):
    """
    Wrapper for the Google Gemini CLI.
    
    Handles tool restrictions, model selection, and NDJSON events.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        project: Optional[str] = None,
        working_dir: Optional[Path] = None,
        **kwargs
    ):
        """
        Initialize Gemini CLI wrapper.
        
        :param api_key: Optional API key.
        :param project: Optional GCP project ID.
        :param working_dir: Working directory.
        """
        env_vars = {}
        if api_key:
            env_vars["GEMINI_API_KEY"] = api_key
        if project:
            env_vars["GOOGLE_CLOUD_PROJECT"] = project
        
        super().__init__(
            working_dir=working_dir,
            env_vars=env_vars,
            **kwargs
        )
    
    def build_command(
        self,
        prompt: str,
        output_format: OutputFormat,
        approval_mode: str = "default",
        allowed_tools: Optional[List[str]] = None,
        model: str = "gemini-2.0-flash",
        **kwargs
    ) -> List[str]:
        """
        Construct 'gemini' command arguments.
        
        :param prompt: The prompt text.
        :param output_format: Requested format.
        :param approval_mode: Tool execution policy.
        :param allowed_tools: List of herramienta names to allow.
        :param model: Specific Gemini model version.
        :return: Command list.
        """
        
        cmd = ["gemini"]
        
        # Map output formats to Gemini flags
        #
        if output_format == OutputFormat.JSON:
            cmd.extend(["--output-format", "json"])
        elif output_format == OutputFormat.STREAM_JSON:
            cmd.extend(["--output-format", "stream-json"])
        
        # Set tool approval behavior
        #
        cmd.extend(["--approval-mode", approval_mode])
        
        # specify target model
        #
        cmd.extend(["--model", model])
        
        # Restrict tools if specified
        #
        if allowed_tools:
            cmd.extend(["--allowed-tools", ",".join(allowed_tools)])
        
        # Final prompt argument
        #
        cmd.extend(["--prompt", prompt])
        
        return cmd
    
    def parse_event(self, line: str) -> Optional[CLIEvent]:
        """
        Parse Gemini NDJSON events and map types.
        """
        try:
            data = json.loads(line)
            event_type = data.get("type", "unknown")
            
            # Normalize Gemini event types
            #
            if "content" in data:
                event_type = "content"
            elif "toolCall" in data:
                event_type = "tool_call"
            elif "toolResult" in data:
                event_type = "tool_result"
            elif "error" in data:
                event_type = "error"
            elif "done" in data:
                event_type = "done"
            
            return CLIEvent(
                type=event_type,
                data=data,
                raw=line,
                timestamp=time.time()
            )
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON: {line}")
            return None
    
    def _extract_usage(self, events: List[CLIEvent]) -> Optional[Dict[str, Any]]:
        """
        Get token usage from the 'done' event statistics.
        """
        for event in reversed(events):
            if event.type == "done" and "statistics" in event.data:
                return event.data["statistics"]
        return None


class PiCLIWrapper(BaseCLIWrapper):
    """
    Wrapper for the Pi CLI in RPC mode.
    
    Handles provider/model selection, thinking levels, and JSON event streaming.
    """
    
    def __init__(
        self,
        provider: str = "google-antigravity",
        model: str = "gemini-3-flash",
        thinking_level: str = "medium",
        tools_enabled: bool = True,
        working_dir: Optional[Path] = None,
        **kwargs
    ):
        """
        Initialize Pi CLI wrapper.
        
        :param provider: AI provider (e.g., 'gemini', 'anthropic').
        :param model: Specific model ID (e.g., 'gemini-3-flash').
        :param thinking_level: 'off'|'minimal'|'low'|'medium'|'high'|'xhigh'.
        :param tools_enabled: Whether to enable tools.
        :param working_dir: Working directory.
        """
        super().__init__(
            working_dir=working_dir,
            **kwargs
        )
        self.provider = provider
        self.model = model
        self.thinking_level = thinking_level
        self.tools_enabled = tools_enabled

    def build_command(
        self,
        prompt: str,
        output_format: OutputFormat,
        **kwargs
    ) -> List[str]:
        """
        Construct 'pi' command arguments for RPC mode.
        
        :param prompt: The initial prompt text (handled via stdin in RPC).
        :return: Command list.
        """
        # Base command for RPC mode without session
        #
        cmd = ["pi", "--mode", "rpc", "--no-session"]
        
        # Add configuration flags
        #
        if self.provider:
            cmd.extend(["--provider", self.provider])
        
        if self.model:
            cmd.extend(["--model", self.model])
            
        if self.thinking_level:
            cmd.extend(["--thinking", self.thinking_level])
            
        # Handle tools mode
        #
        if self.tools_enabled:
            cmd.append("--tools")
        else:
            cmd.append("--no-tools")
            
        return cmd

    def parse_event(self, line: str) -> Optional[CLIEvent]:
        """
        Parse Pi RPC JSON events.
        """
        try:
            data = json.loads(line)
            event_type = data.get("type", "unknown")
            
            # Map Pi events to unified CLIEvent types
            #
            if event_type == "message_update":
                # Pi sends partial updates
                #
                delta = data.get("assistantMessageEvent", {})
                if delta.get("type") == "text_delta":
                    # Create a content event for the text chunk
                    #
                    return CLIEvent(
                        type="content",
                        data={"content": delta.get("delta", "")},
                        raw=line,
                        timestamp=time.time()
                    )
            elif event_type == "agent_end":
                return CLIEvent(
                    type="done",
                    data=data,
                    raw=line,
                    timestamp=time.time()
                )
            
            # Return other events as-is
            #
            return CLIEvent(
                type=event_type,
                data=data,
                raw=line,
                timestamp=time.time()
            )
            
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON: {line}")
            return None

    def _extract_usage(self, events: List[CLIEvent]) -> Optional[Dict[str, Any]]:
        """
        Extract usage stats if available in agent_end/done event.
        """
        for event in reversed(events):
            if event.type == "done" and "usage" in event.data:
                return event.data["usage"]
        return None

    async def execute(
        self,
        prompt: str,
        output_format: OutputFormat = OutputFormat.STREAM_JSON,
        on_event: Optional[Callable[[CLIEvent], None]] = None,
        stdin_data: Optional[str] = None,
        **kwargs
    ) -> CLIResponse:
        """
        Execute Pi command.
        
        Pi in RPC mode expects directives via stdin:
        {"type": "prompt", "message": "..."}
        """
        # Construct the JSON command to send to Pi's stdin
        #
        rpc_command = json.dumps({
            "type": "prompt",
            "message": prompt
        }) + "\n"
        
        # If stdin_data is provided (e.g. piped content), append it
        #
        final_stdin = rpc_command
        if stdin_data:
            final_stdin += stdin_data
            
        return await super().execute(
            prompt,
            output_format,
            on_event,
            stdin_data=final_stdin,
            **kwargs
        )


class WorkflowSession:
    """
    Manages multi-step CLI workflows by tracking history and state.
    """
    
    def __init__(self, wrapper: BaseCLIWrapper):
        """
        Initialize workflow session.
        
        :param wrapper: The CLI wrapper to use.
        """
        self.wrapper = wrapper
        self.history: List[CLIResponse] = []
    
    async def execute_step(
        self,
        prompt: str,
        **kwargs
    ) -> CLIResponse:
        """
        Execute a single step in the workflow.
        
        Automatically uses 'resume' if the wrapper supports it and a
        session is already active.
        
        :param prompt: The current step prompt.
        :return: CLIResponse.
        """
        
        # Decide whether to resume or start new
        #
        if self.history and hasattr(self.wrapper, 'resume'):
            response = await self.wrapper.resume(prompt, **kwargs)
        else:
            response = await self.wrapper.execute(prompt, **kwargs)
        
        self.history.append(response)
        return response
    
    def get_full_transcript(self) -> str:
        """
        Get a formatted transcript of all steps.
        """
        return "\n\n---\n\n".join(
            f"Step {i+1}:\n{resp.final_output}"
            for i, resp in enumerate(self.history)
        )


class ResilientCLIWrapper:
    """
    Wrapper adding retry logic and error handling to an existing wrapper.
    """
    
    def __init__(
        self,
        wrapper: BaseCLIWrapper,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ):
        """
        Initialize resilient wrapper.
        
        :param wrapper: Base wrapper instance.
        :param max_retries: Limit on retry attempts.
        :param retry_delay: Base delay for exponential backoff.
        """
        self.wrapper = wrapper
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def execute_with_retry(
        self,
        prompt: str,
        **kwargs
    ) -> CLIResponse:
        """
        Execute with exponential backoff on failure.
        
        :param prompt: User prompt.
        :return: Successful CLIResponse.
        :raises RuntimeError: If all attempts fail.
        """
        
        last_error: Optional[Exception] = None
        
        for attempt in range(self.max_retries):
            try:
                response = await self.wrapper.execute(prompt, **kwargs)
                
                # Check exit codes for specific failures
                #
                if response.exit_code == 0:
                    return response
                elif response.exit_code == 41:
                    raise AuthenticationError("CLI authentication failed")
                elif response.exit_code == 42:
                    raise ValueError(f"Invalid input: {response.stderr}")
                else:
                    logger.warning(f"Non-zero exit code: {response.exit_code}")
                    last_error = RuntimeError(f"Exit code {response.exit_code}")
                    
            except (asyncio.TimeoutError, RuntimeError) as e:
                last_error = e
                # Retry if attempts remain
                #
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Attempt {attempt+1} failed, retrying in {delay}s")
                    await asyncio.sleep(delay)
                continue
        
        raise RuntimeError(f"Failed after {self.max_retries} attempts") from last_error


class EventAggregator:
    """
    Aggregates and filters events for summary reporting.
    """
    
    def __init__(self):
        """
        Initialize aggregator state.
        """
        self.events_by_type = defaultdict(list)
        self.tool_calls = []
        self.file_changes = []
    
    def process_event(self, event: CLIEvent):
        """
        Categorize a single event based on type and content.
        
        :param event: The event to process.
        """
        self.events_by_type[event.type].append(event)
        
        # Extract specific structured data
        #
        if event.type in ["tool_call", "toolCall"]:
            self.tool_calls.append(event.data)
        
        if event.type == "item.completed":
            item = event.data.get("item", {})
            if item.get("type") == "file_change":
                self.file_changes.append(item)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Provide a statistical summary of the execution.
        """
        return {
            "total_events": sum(len(events) for events in self.events_by_type.values()),
            "event_types": {k: len(v) for k, v in self.events_by_type.items()},
            "tool_calls": len(self.tool_calls),
            "files_changed": len(self.file_changes)
        }
