from crewai import Agent, Crew, Task, Process
from crewai.project import CrewBase, agent, crew, task, after_kickoff, before_kickoff
from crewai.llm import LLM
from .pydantic_output.pydantic_output import IntroductionSectionOutline
import json

@CrewBase
class IntroductionOutlineCrew:

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"
    std_llm = LLM(
        model="ollama/qwen2.5:7b-instruct",
        base_url="http://localhost:11434",
        max_tokens=32000,
        temperature=0.3
    )
    
    # ------------ Formatação de Input/Output ------------

    @before_kickoff
    def input_formatting(self, inputs):
        inputs['other_sections_outlines'] = json.dumps(inputs['other_sections_outlines'], indent=2)
        return inputs

    @after_kickoff
    def final_formatting(self, crew_execution_result):
        introduction_context = next((
            task_output.raw for task_output in crew_execution_result.tasks_output 
            if task_output.name == 'synthesize_introduction_context'
        ), {})
        introduction_outline = next((
            task_output.json_dict for task_output in crew_execution_result.tasks_output 
            if task_output.name == 'expand_introduction_subsections'
        ), {})
        return introduction_context, introduction_outline

    # ------------ Agentes ------------

    @agent
    def introduction_context_extractor(self) -> Agent:
        return Agent(
            config=self.agents_config['introduction_context_extractor'],
            llm=self.std_llm,
        )

    @agent
    def introduction_outline_architect(self) -> Agent:
        return Agent(
            config=self.agents_config['introduction_outline_architect'],
            llm=self.std_llm,
        )
    
    # ------------ Tarefas ------------
    
    @task
    def extract_context_from_analytical_report(self) -> Task:
        return Task(
            config=self.tasks_config['extract_context_from_analytical_report'],
        )
    
    @task
    def extract_context_from_section_outlines(self) -> Task:
        return Task(
            config=self.tasks_config['extract_context_from_section_outlines'],
        )
    
    @task
    def synthesize_introduction_context(self) -> Task:
        return Task(
            config=self.tasks_config['synthesize_introduction_context'],
        )

    @task
    def define_introduction_subsections(self) -> Task:
        return Task(
            config=self.tasks_config['define_introduction_subsections'],
            output_json=IntroductionSectionOutline
        )
    
    @task
    def expand_introduction_subsections(self) -> Task:
        return Task(
            config=self.tasks_config['expand_introduction_subsections'],
            output_json=IntroductionSectionOutline
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