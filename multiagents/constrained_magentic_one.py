import warnings
from typing import Awaitable, Callable, List, Optional, Union

from autogen_agentchat.agents import UserProxyAgent
# from autogen_agentchat.agents import CodeExecutorAgent
from multiagents.gemini.code_executor_agent import CodeExecutorAgent
from autogen_agentchat.base import ChatAgent
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_core import CancellationToken
from autogen_agentchat.conditions import TextMentionTermination
from autogen_core.models import ChatCompletionClient

# from autogen_ext.agents.file_surfer import FileSurfer
from multiagents.gemini.file_surfer import FileSurfer
from autogen_ext.agents.magentic_one import MagenticOneCoderAgent
from autogen_ext.agents.web_surfer import MultimodalWebSurfer
from autogen_ext.agents.video_surfer import VideoSurfer
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_ext.models.openai._openai_client import BaseOpenAIChatCompletionClient
from multiagents.constrained_utils.ConstrainedMAOrchestrator import ConstrainedMAOrchestrator
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage, MessageFactory
from autogen_agentchat.teams._group_chat._events import GroupChatTermination
from autogen_agentchat.teams._group_chat._base_group_chat import BaseGroupChat
from autogen_agentchat.base import TerminationCondition
import asyncio
from autogen_agentchat.teams._group_chat._magentic_one._prompts import ORCHESTRATOR_FINAL_ANSWER_PROMPT




SyncInputFunc = Callable[[str], str]
AsyncInputFunc = Callable[[str, Optional[CancellationToken]], Awaitable[str]]
InputFuncType = Union[SyncInputFunc, AsyncInputFunc]


class ConstrainedMagenticOne(MagenticOneGroupChat):
    """
    MagenticOne is a specialized group chat class that integrates various agents
    such as FileSurfer, WebSurfer, Coder, and Executor to solve complex tasks.
    To read more about the science behind Magentic-One, see the full blog post: `Magentic-One: A Generalist Multi-Agent System for Solving Complex Tasks <https://www.microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks>`_ and the references below.

    Installation:

    .. code-block:: bash

        pip install "autogen-ext[magentic-one]"


    Args:
        client (ChatCompletionClient): The client used for model interactions.
        hil_mode (bool): Optional; If set to True, adds the UserProxyAgent to the list of agents.

    .. warning::
        Using Magentic-One involves interacting with a digital world designed for humans, which carries inherent risks. To minimize these risks, consider the following precautions:

        1. **Use Containers**: Run all tasks in docker containers to isolate the agents and prevent direct system attacks.
        2. **Virtual Environment**: Use a virtual environment to run the agents and prevent them from accessing sensitive data.
        3. **Monitor Logs**: Closely monitor logs during and after execution to detect and mitigate risky behavior.
        4. **Human Oversight**: Run the examples with a human in the loop to supervise the agents and prevent unintended consequences.
        5. **Limit Access**: Restrict the agents' access to the internet and other resources to prevent unauthorized actions.
        6. **Safeguard Data**: Ensure that the agents do not have access to sensitive data or resources that could be compromised. Do not share sensitive information with the agents.

        Be aware that agents may occasionally attempt risky actions, such as recruiting humans for help or accepting cookie agreements without human involvement. Always ensure agents are monitored and operate within a controlled environment to prevent unintended consequences. Moreover, be cautious that Magentic-One may be susceptible to prompt injection attacks from webpages.

    Architecture:

    Magentic-One is a generalist multi-agent system for solving open-ended web and file-based tasks across a variety of domains. It represents a significant step towards developing agents that can complete tasks that people encounter in their work and personal lives.

    Magentic-One work is based on a multi-agent architecture where a lead Orchestrator agent is responsible for high-level planning, directing other agents, and tracking task progress. The Orchestrator begins by creating a plan to tackle the task, gathering needed facts and educated guesses in a Task Ledger that is maintained. At each step of its plan, the Orchestrator creates a Progress Ledger where it self-reflects on task progress and checks whether the task is completed. If the task is not yet completed, it assigns one of Magentic-One's other agents a subtask to complete. After the assigned agent completes its subtask, the Orchestrator updates the Progress Ledger and continues in this way until the task is complete. If the Orchestrator finds that progress is not being made for enough steps, it can update the Task Ledger and create a new plan.

    Overall, Magentic-One consists of the following agents:

    - Orchestrator: The lead agent responsible for task decomposition and planning, directing other agents in executing subtasks, tracking overall progress, and taking corrective actions as needed.
    - WebSurfer: An LLM-based agent proficient in commanding and managing the state of a Chromium-based web browser. It performs actions on the browser and reports on the new state of the web page.
    - FileSurfer: An LLM-based agent that commands a markdown-based file preview application to read local files of most types. It can also perform common navigation tasks such as listing the contents of directories and navigating a folder structure.
    - Coder: An LLM-based agent specialized in writing code, analyzing information collected from other agents, or creating new artifacts.
    - ComputerTerminal: Provides the team with access to a console shell where the Coder’s programs can be executed, and where new programming libraries can be installed.

    Together, Magentic-One’s agents provide the Orchestrator with the tools and capabilities needed to solve a broad variety of open-ended problems, as well as the ability to autonomously adapt to, and act in, dynamic and ever-changing web and file-system environments.

    Examples:

        .. code-block:: python

            # Autonomously complete a coding task:
            import asyncio
            from autogen_ext.models.openai import OpenAIChatCompletionClient
            from autogen_ext.teams.magentic_one import MagenticOne
            from autogen_agentchat.ui import Console


            async def example_usage():
                client = OpenAIChatCompletionClient(model="gpt-4o")
                m1 = MagenticOne(client=client)
                task = "Write a Python script to fetch data from an API."
                result = await Console(m1.run_stream(task=task))
                print(result)


            if __name__ == "__main__":
                asyncio.run(example_usage())


        .. code-block:: python

            # Enable human-in-the-loop mode
            import asyncio
            from autogen_ext.models.openai import OpenAIChatCompletionClient
            from autogen_ext.teams.magentic_one import MagenticOne
            from autogen_agentchat.ui import Console


            async def example_usage_hil():
                client = OpenAIChatCompletionClient(model="gpt-4o")
                # to enable human-in-the-loop mode, set hil_mode=True
                m1 = MagenticOne(client=client, hil_mode=True)
                task = "Write a Python script to fetch data from an API."
                result = await Console(m1.run_stream(task=task))
                print(result)


            if __name__ == "__main__":
                asyncio.run(example_usage_hil())

    References:
        .. code-block:: bibtex

            @article{fourney2024magentic,
                title={Magentic-one: A generalist multi-agent system for solving complex tasks},
                author={Fourney, Adam and Bansal, Gagan and Mozannar, Hussein and Tan, Cheng and Salinas, Eduardo and Niedtner, Friederike and Proebsting, Grace and Bassman, Griffin and Gerrits, Jack and Alber, Jacob and others},
                journal={arXiv preprint arXiv:2411.04468},
                year={2024},
                url={https://arxiv.org/abs/2411.04468}
            }


    """

    def __init__(
        self,
        client: ChatCompletionClient,
        hil_mode: bool = False,
        input_func: InputFuncType | None = None,
        include_web_surfer: bool = False,
        include_video_surfer: bool = False,
        input_type: str | None = None,
        error_type: str | None = None,
        query_num: int | None = None,
        trial_num: int | None = None,
    ):
        self.client = client
        self._validate_client_capabilities(client)
        self._cfg_constraints = {'test': 'test'}

        fs = FileSurfer("FileSurfer", model_client=client)
        ws = MultimodalWebSurfer("WebSurfer", model_client=client)
        vs = VideoSurfer("VideoSurfer", model_client=client)
        coder = MagenticOneCoderAgent("Coder", model_client=client)
        # executor = CodeExecutorAgent("Executor", code_executor=DockerCommandLineCodeExecutor())
        executor = CodeExecutorAgent(
            "Executor", 
            code_executor=LocalCommandLineCodeExecutor(),
            orchestrator="magentic-one",
            model=client.model_info["family"],
            input_type=input_type,
            error_type=error_type,
            query_num=query_num,
            trial_num=trial_num,
        )
        agents: List[ChatAgent] = [fs, coder, executor]
        if include_web_surfer:
            agents.append(ws)
        if include_video_surfer:
            agents.append(vs)

        print(f"Agents: {[a.name for a in agents]}")
        if hil_mode:
            user_proxy = UserProxyAgent("User", input_func=input_func)
            agents.append(user_proxy)

        termination = TextMentionTermination("TERMINATE")

        BaseGroupChat.__init__(
            self,
            participants=agents,
            group_chat_manager_name="ConstrainedMAOrchestrator",
            group_chat_manager_class=ConstrainedMAOrchestrator,
            termination_condition=termination,
            max_turns=20,
            runtime=None,
            custom_message_types=None,
            emit_team_events=False,
        )
        self._model_client = client
        self._max_stalls = 3
        self._final_answer_prompt = ORCHESTRATOR_FINAL_ANSWER_PROMPT



    def _validate_client_capabilities(self, client: ChatCompletionClient) -> None:
        capabilities = client.model_info
        required_capabilities = ["vision", "function_calling", "json_output"]

        if not all(capabilities.get(cap) for cap in required_capabilities):
            warnings.warn(
                "Client capabilities for MagenticOne must include vision, " "function calling, and json output.",
                stacklevel=2,
            )

        if not isinstance(client, BaseOpenAIChatCompletionClient):
            warnings.warn(
                "MagenticOne performs best with OpenAI GPT-4o model either " "through OpenAI or Azure OpenAI.",
                stacklevel=2,
            )
    
    def _create_group_chat_manager_factory(
        self,
        name: str,
        group_topic_type: str,
        output_topic_type: str,
        participant_topic_types: List[str],
        participant_names: List[str],
        participant_descriptions: List[str],
        output_message_queue: asyncio.Queue[BaseAgentEvent | BaseChatMessage | GroupChatTermination],
        termination_condition: TerminationCondition | None,
        max_turns: int | None,
        message_factory: MessageFactory,
    ) -> Callable[[], ConstrainedMAOrchestrator]:
        return lambda: ConstrainedMAOrchestrator(
            name,
            group_topic_type,
            output_topic_type,
            participant_topic_types,
            participant_names,
            participant_descriptions,
            max_turns,
            message_factory,
            self._model_client,
            self._max_stalls,
            self._final_answer_prompt,
            output_message_queue,
            termination_condition,
            self._emit_team_events,
        )