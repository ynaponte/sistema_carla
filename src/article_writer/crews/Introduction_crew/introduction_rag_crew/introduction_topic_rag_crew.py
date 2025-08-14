from crewai import Agent, Crew, Task, Process
from crewai.project import CrewBase, agent, crew, task
from crewai.llm import LLM
from pydantic import BaseModel, Field
from src.tools import QueryArticlesTool


class TopicTextContent(BaseModel):
    topic: str = Field(description="Exact name of the topic that writing was requested upon")
    text: str = Field(
        description=(
            "Full multi-paragraph scientific text about the topic, with 200-500 words, "
            "written in brazilian portuguese"
        )
    )


@CrewBase
class IntroductionTopicRagCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"
    researcher_llm = LLM(
        model="ollama/qwen2.5:7b-instruct",
        base_url="http://localhost:11434",
        timeout=1800.0,
        max_tokens=32000,
        temperature=0.3
    )
    writer_llm = LLM(
        model="ollama/qwen2.5:7b-instruct",
        base_url="http://localhost:11434",
        timeout=1800.0,
        max_tokens=32000,
        temperature=0.6
    )

    @agent
    def introduction_topic_researcher(self) -> Agent:
        return Agent(
          config=self.agents_config['introduction_topic_researcher'],
          llm=self.researcher_llm,
          verbose=True,
          memory=True
        )

    @agent
    def introduction_topic_writer(self) -> Agent:
      return Agent(
        config=self.agents_config['introduction_topic_writer'],
        llm=self.writer_llm,
        verbose=True,
      )
    
    @task
    def extract_introduction_topic_context(self) -> Task:
      return Task(
        config=self.tasks_config['extract_introduction_topic_context'],
        async_execution=False
      )
    
    @task
    def introduction_topic_external_citations_research(self) -> Task:
      return Task(
        config=self.tasks_config['introduction_topic_external_citations_research'],
        async_execution=False,
        tools=[QueryArticlesTool()]
      )
    
    @task
    def write_introduction_topic_text(self) -> Task:
      return Task(
        config=self.tasks_config['write_introduction_topic_text'],
        output_json=TopicTextContent
      )
    
    @crew
    def crew(self) -> Crew:
      crew = Crew(
        agents=self.agents,
        tasks=self.tasks,
        process=Process.sequential,
        verbose=True
      )
      return crew