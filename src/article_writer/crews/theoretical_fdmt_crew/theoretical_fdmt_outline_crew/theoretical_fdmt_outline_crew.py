from crewai import Agent, Crew, Task, Process
from crewai.project import CrewBase, agent, crew, task, after_kickoff, before_kickoff
from crewai.llm import LLM
from .pydantic_output.pydantic_output import TheoreticalFdmtSectionOutline
import json

@CrewBase
class TheoreticalFdmtOutlineCrew:

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"
    std_llm = LLM(
        model="ollama/qwen2.5:7b-instruct",
        base_url="http://localhost:11434",
        max_tokens=32000,
        temperature=0.3
    )
    
    @before_kickoff
    def input_formatting(self, inputs):
        inputs['methodology_outline'] = json.dumps(inputs['methodology_outline'], indent=2)
        return inputs

    @after_kickoff
    def final_formatting(self, crew_execution_result):
        theoretical_foundation_outline = next((
            task_output.json_dict for task_output in crew_execution_result.tasks_output 
            if task_output.name == 'expand_theoretical_foundation_subsections'
        ), {})
        return theoretical_foundation_outline

    @agent
    def theoretical_concept_extractor(self) -> Agent:
        return Agent(
            config=self.agents_config['theoretical_concept_extractor'],
            llm=self.std_llm,
        )

    @agent
    def theoretical_foundation_outliner(self) -> Agent:
        return Agent(
            config=self.agents_config['theoretical_foundation_outliner'],
            llm=self.std_llm,
        )
    # ------------ Tarefas ------------
    @task
    def extract_theoretical_context_from_report_and_methodology(self) -> Task:
        return Task(
            config=self.tasks_config['extract_theoretical_context_from_report_and_methodology'],
        )
    
    @task
    def define_theoretical_foundation_subsections(self) -> Task:
        return Task(
            config=self.tasks_config['define_theoretical_foundation_subsections'],
            output_json=TheoreticalFdmtSectionOutline
        )
    
    @task
    def expand_theoretical_foundation_subsections(self) -> Task:
        return Task(
            config=self.tasks_config['expand_theoretical_foundation_subsections'],
            output_json=TheoreticalFdmtSectionOutline
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