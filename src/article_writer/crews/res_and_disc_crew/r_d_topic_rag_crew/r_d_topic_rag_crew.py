from crewai import Agent, Crew, Process, Task
from crewai.llm import LLM
from crewai.project import CrewBase, agent, crew, task, before_kickoff
from crewai.tasks.conditional_task import ConditionalTask
from src.tools import QueryArticlesTool
from pydantic import BaseModel, Field
from typing import List


class TopicTextContent(BaseModel):
    topic: str = Field(description="Exact name of the topic that writing was requested upon")
    text: str = Field(
        description=(
            "Full multi-paragraph scientific text about the topic, with 500+ words, "
            "written in brazilian portuguese"
        )
    )


@CrewBase
class RDTopicRagCrew():

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    researcher_llm = LLM(
        model="ollama/qwen2.5:7b-instruct",
        base_url="http://localhost:11434",
        timeout=1800.0,
        max_tokens=32000,
        temperature=0.4
    )
    writer_llm = LLM(
        model="ollama/qwen2.5:7b-instruct",
        base_url="http://localhost:11434",
        timeout=1800.0,
        max_tokens=32000,
        temperature=0.6
    )
    __should_execute_ve_research = True
    __should_execute_nr_research = True

    @before_kickoff
    def check_inpus(self, inputs: dict):
        # Checa se existem elementos visuais e resultados numéricos a serem pesquisados.
        # Caso não existão, previne a execução das respectivas tarefas
        # Caso sim, transforma-os de lista para python para string, organizados em uma 
        # lista formatada em markdown
        if inputs.get('visual_elements_to_contextualize') != []:
            self.__should_execute_ve_research = True
            inputs['visual_elements_to_contextualize'] = "\n".join([
                f"- name: {element['name']}; role_in_topic: {element['role_in_topic']}"
                for element in inputs['visual_elements_to_contextualize']
            ])
        else:
            self.__should_execute_ve_research = False

        if inputs.get('numerical_results_to_include') != []:
            self.__should_execute_nr_research = True
            inputs['numerical_results_to_include'] = "\n".join([
                (
                    f'- verbatim value: {numerical_result["verbatim_value"]}; '
                    f'role_in_topic: {numerical_result["role_in_topic"]}; '
                    f'associated visual: {numerical_result["associated_visual"]}'
                ) 
                for numerical_result in inputs['numerical_results_to_include']
            ])
        else:
            self.__should_execute_nr_research = False
            
        return inputs

    @agent
    def topic_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['topic_researcher'],
            llm=self.researcher_llm,
            tools=[QueryArticlesTool()],
            verbose=True,
            memory=True
        )
    
    @agent
    def technical_writer(self) -> Agent:
        return Agent(
            config=self.agents_config['technical_writer'],
            llm=self.writer_llm,
            verbose=True,
        )
    
    @task
    def topic_research(self) -> Task:
        return Task(
            config=self.tasks_config['topic_research'],
            async_execution=False
        )

    @task
    def visual_elements_research(self) -> Task:
        return ConditionalTask(
            config=self.tasks_config['visual_elements_research'],
            async_execution=False,
            condition=lambda x: self.__should_execute_ve_research  # Tem que ser 'callable'
        )

    @task
    def numerical_results_research(self) -> Task:
        return ConditionalTask(
            config=self.tasks_config['numerical_results_research'],
            async_execution=False,
            condition=lambda x: self.__should_execute_nr_research  # Tem que ser 'callable'
        )

    @task
    def write_topic_text(self) -> Task:
        return Task(
            config=self.tasks_config['write_topic_text'],
            output_json=TopicTextContent
        )
    
    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            planning=False
        )
