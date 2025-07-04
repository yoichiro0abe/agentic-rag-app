import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_ext.tools.code_execution import PythonCodeExecutionTool
from dotenv import load_dotenv
import logging
import os
from autogen_core.models import ModelInfo
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient


async def main() -> None:
    load_dotenv("./.env_gpt4.1", override=True)

    # LLM設定（Azure OpenAI）
    model_info = ModelInfo(
        vision=False,
        function_calling=True,
        json_output=False,
        family="unknown",
        structured_output=True,
    )
    azure_endpoint = os.environ.get("AZURE_AI_AGENT_ENDPOINT")
    api_key = os.environ.get("AZURE_API_KEY")
    model_deployment = os.environ.get("AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME")
    api_version = os.environ.get("AZURE_API_VERSION")
    model_client = AzureOpenAIChatCompletionClient(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        model=model_deployment,
        api_version=api_version,
        model_info=model_info,
    )
    tool = PythonCodeExecutionTool(LocalCommandLineCodeExecutor(work_dir="coding"))
    agent = AssistantAgent(
        "assistant",
        model_client,
        tools=[tool],
        reflect_on_tool_use=True,
    )
    await Console(
        agent.run_stream(
            task="Create a plot of MSFT stock prices in 2024 and save it to a file. Use yfinance and matplotlib."
        )
    )


asyncio.run(main())
