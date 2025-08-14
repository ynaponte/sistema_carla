from pydantic import BaseModel
from crewai.flow import Flow, listen, start, and_
from .crews.res_and_disc_crew.r_d_outline_crew.r_d_outline_crew import RDOutlineCrew
from .crews.res_and_disc_crew.r_d_topic_rag_crew.r_d_topic_rag_crew import RDTopicRagCrew
from .crews.conclusion_crew.c_outline_crew.c_outline_crew import COutlineCrew
from .crews.conclusion_crew.c_topic_rag_crew.c_topic_rag_crew import ConclusionTopicRagCrew
from .crews.methodology_crew.methodology_outline_crew.methodology_outline_crew import MethodologyOutlineCrew
from .crews.methodology_crew.methodology_topic_rag_crew.methodology_topic_rag_crew import MethodologyTopicRagCrew
from .crews.theoretical_fdmt_crew.theoretical_fdmt_outline_crew.theoretical_fdmt_outline_crew import TheoreticalFdmtOutlineCrew
from .crews.theoretical_fdmt_crew.theoretical_fdmt_rag_crew.theoretical_fdmt_topic_rag_crew import TheoreticalFdmtTopicRagCrew
from .crews.introduction_crew.introduction_outline_crew.introduction_outline_crew import IntroductionOutlineCrew
from .crews.introduction_crew.introduction_rag_crew.introduction_topic_rag_crew import IntroductionTopicRagCrew
from typing import Dict, List, Any
from ..utils import VectorDatabaseManager, cache_execution
# from .types.doc_report import AnaliseCriticaResultadosDiscussao
import asyncio
import json
import os


class ArticleWriterState(BaseModel):
    draft_report: str = ""
    sections_and_content: List[Dict[str, str]] = []
    return_cache: List[Any] = []
    results_and_discussion_outline: dict = {}
    conclusion_outline: dict = {}
    methodology_outline: dict = {}
    theoretical_fundamentation_outline: dict = {}
    introduction_outline: dict = {}


class ArticleWriterFlow(Flow[ArticleWriterState]):

  articles_db = VectorDatabaseManager()

  @start()
  def start_flow(self):
    # Define o diretório onde os relatórios estão localizados
    report_directory = "report"
    report_file_name = None

    # Procura por arquivos PDF no diretório especificado
    if os.path.exists(report_directory) and os.path.isdir(report_directory):
      for file in os.listdir(report_directory):
        if file.lower().endswith(".pdf"):
          report_file_name = file
          break # Encontrou o primeiro arquivo PDF, então para
    
    if not report_file_name:
      raise FileNotFoundError(f"Nenhum arquivo PDF encontrado no diretório '{report_directory}'")

    # Inicializa a base de dados para uso das ferramentas
    self.articles_db.initialize_db(
        persist_directory="article_vectorstore",
        collection_name="flow_test_collection"
    )
    report = self.articles_db.search_doc_by_meta(
      source=report_file_name, metadata_only=False
    )

    self.state.draft_report = report[report_file_name]['text_content']
  
  @listen(start_flow)
  @cache_execution(state_variable_to_update='state.results_and_discussion_outline')
  def res_and_disc_outline_generation(self): 
    subsections_outline = RDOutlineCrew().crew().kickoff(
        inputs={
          "report": self.state.draft_report,
        }
    )
    return {
      "section_name" : "Resultados e Discussão",
      "subsections": subsections_outline
    }
  
  @listen(res_and_disc_outline_generation)
  @cache_execution(state_variable_to_update='state.sections_and_content', state_update_action='append')
  async def res_and_disc_chapter_generation(self, results_discussion_outline):
    # Função para permitir chamada assincrona da crew de escrita dos tópicos
    async def acall_write_topic_crew(
      section_title, 
      topic, 
      topic_description,
      visual_elements_to_contextualize, 
      numerical_results_to_include,
      rhetorical_purpose,
      narrative_guidance,
      subsection_flow
    ):
      topic_content = await RDTopicRagCrew().crew().kickoff_async(
        inputs={
          "section_title": section_title,
          "discussion_topic": topic,
          "topic_description": topic_description,
          "visual_elements_to_contextualize": visual_elements_to_contextualize,
          "numerical_results_to_include": numerical_results_to_include,
          "rhetorical_purpose": rhetorical_purpose,
          "narrative_guidance": narrative_guidance,
          "subsection_flow": subsection_flow
        }
      )
      return topic_content

    subs_outlines = results_discussion_outline.get('subsections', [])
    # Inicializa o dicionário para armazenar o conteúdo gerado para a seção e suas subseções
    results_and_discussion_section = {
      "section_name": "Resultado e Discussão", 
      "topics": []
    }
    async_tasks_to_exec = []  # Inicializa a lista de tarefas a ser executada
    async_tasks_tags = []  # Lista para ratreabilidade de a qual subseção o resultado da tarefa pertence
    for subsection in subs_outlines:
      for discussion_topic in subsection['discussion_topics']:
        async_tasks_to_exec.append(
          asyncio.create_task(
            acall_write_topic_crew(
                subsection['subsection_name'], 
                discussion_topic['topic_title'],
                discussion_topic['topic_description'],
                discussion_topic.get('visual_elements', []),
                discussion_topic.get('numerical_results', []), 
                discussion_topic['rhetorical_purpose'],
                discussion_topic['narrative_guidance'],
                subsection['subsection_flow']
            )
          )
        )
        async_tasks_tags.append(subsection['subsection_name'])
    
    subsection_topics_content = await asyncio.gather(*async_tasks_to_exec)
    for subsection_name, topic_content in zip(async_tasks_tags, subsection_topics_content):
      # Prepara os resultados para serem armazenados em formato JSON, seguindo uma estrutura padrão,
      # onde cada tópico, além da informação sobre seu nome e seu conteúdo textual, carrega também a 
      # qual seção ele pertence. Caso seja da principal, se informa como 'null'.
      topic_content = topic_content.json_dict 
      topic_content['subsection'] = subsection_name
      results_and_discussion_section['topics'].append(topic_content)
    
    self.state.sections_and_content.append(results_and_discussion_section)
    return results_and_discussion_section
  
  @listen(res_and_disc_chapter_generation)
  @cache_execution(state_variable_to_update='state.conclusion_outline')
  def conclusion_outline_generation(self, results_and_discussion_section):
    conclusion_outline = COutlineCrew().crew().kickoff(
        inputs={
          "report": self.state.draft_report,
          "generated_sections_content": results_and_discussion_section
        }
    )
    return conclusion_outline

  @listen(conclusion_outline_generation)
  @cache_execution(state_variable_to_update='state.sections_and_content', state_update_action='append')
  # NOTA: talvez seja bom esperar o também o termino da execução de `res_and_disc_chapter_generation`, para evitar muitas tarefas assícronas rodando.
  async def conclusion_chapter_generation(
    self,
    conclusion_outline
  ):
    async def acall_write_topic_crew(
      topic,
      rhetorical_purpose,
      topic_description,
      narrative_guidance
    ):
      conclusion_topic_content = (
        await ConclusionTopicRagCrew()
        .crew()
        .kickoff_async(
          inputs={               
            "conclusion_topic": topic,
            "rhetorical_purpose": rhetorical_purpose,
            "topic_description": topic_description,
            "narrative_guidance": narrative_guidance
          }
        )
      )
      return conclusion_topic_content
    
    discussion_topics = conclusion_outline['discussion_topics']
    async_tasks_to_exec = []
    conclusion_section = {
      "section_name": "Conclusão",
      "topics": []
    }
    for discussion_topic in discussion_topics:
      # Não é necessário rastrear subseção, pois as mesmas não são geradas para a conclusão
      async_tasks_to_exec.append(
        asyncio.create_task(
          acall_write_topic_crew(
            discussion_topic['topic_title'],
            discussion_topic['rhetorical_purpose'],
            discussion_topic['topic_description'],
            discussion_topic['narrative_guidance']
          )
        )
      )
    conclusion_topics_content = await asyncio.gather(*async_tasks_to_exec)
    for topic_content in conclusion_topics_content:
      topic_content = topic_content.json_dict
      topic_content['subsection'] = 'main'
      conclusion_section['topics'].append(topic_content)

    self.state.sections_and_content.append(conclusion_section)
    return conclusion_section
  
  @listen(conclusion_chapter_generation)
  @cache_execution(state_variable_to_update='state.methodology_outline')
  def methodology_outline_generation(self):
    methodology_outline = MethodologyOutlineCrew().crew().kickoff(
        inputs={
          "report": self.state.draft_report,
          "generated_sections_content": self.state.sections_and_content
        }
    )
    return methodology_outline
  
  @listen(methodology_outline_generation)
  @cache_execution(state_variable_to_update='state.sections_and_content', state_update_action='append')
  async def methodology_chapter_generation(self, methodology_outline):
    async def acall_write_topic_crew(
      subsection_name,
      subsection_description,
      topic_title,
      rhetorical_purpose,
      topic_description,
      narrative_guidance
    ):
      methodology_topics_content = (
        await MethodologyTopicRagCrew()
        .crew()
        .kickoff_async(
          inputs={               
            "methodology_subsection_name": subsection_name,
            "methodology_subsection_description": subsection_description,
            "methodology_topic_title": topic_title,
            "methodology_topic_description": topic_description,
            "methodology_rhetorical_purpose": rhetorical_purpose,
            "methodology_narrative_guidance": narrative_guidance
          }
        )
      )
      return methodology_topics_content
    
    methodology_section = {
      "section_name": "Metodologia",
      "topics": []
    }
    async_tasks_to_exec = []  # Inicia a lista de tarefas
    async_tasks_tags = []  # Lista para ratreabilidade de a qual subseção o resultado da tarefa pertence
    for subsecion in methodology_outline['subsections']:
      subsection_name = subsecion['subsection_name']

      for discussion_topic in subsecion['discussion_topics']:
        # Cria a tarefa assíncrona de execução da equipe de geração de conteúdo para o tópico
        async_tasks_to_exec.append(
          asyncio.create_task(
            acall_write_topic_crew(
              subsection_name=subsection_name,
              subsection_description=subsecion['subsection_description'],
              topic_title=discussion_topic['topic_title'],
              topic_description=discussion_topic['topic_description'],
              rhetorical_purpose=discussion_topic['rhetorical_purpose'],
              narrative_guidance=discussion_topic['narrative_guidance']
            )
          )
        )
        # Adiciona o nome da subseção como uma tag de controle, de modo que se possibilita a 
        # reorganização do conteúdo na ordem correta
        async_tasks_tags.append(subsection_name)
  
    methodology_topics_content = await asyncio.gather(*async_tasks_to_exec)
    for subsection_name,topic_content in zip(async_tasks_tags, methodology_topics_content):
      topic_content = topic_content.json_dict
      topic_content['subsection'] = subsection_name  # Cria uma nova chave no dicionário para armazenar a que seção o tópico pertence
      methodology_section['topics'].append(topic_content)

    self.state.sections_and_content.append(methodology_section)
    return methodology_section    
  
  @listen(and_(methodology_chapter_generation, methodology_outline_generation))
  @cache_execution(state_variable_to_update='state.theoretical_fundamentation_outline')
  def theoretical_fdmt_outline_generation(self, methodology_outline):
    theoretical_fdmt_outline = TheoreticalFdmtOutlineCrew().crew().kickoff(
      inputs={
        "report": self.state.draft_report,
        "methodology_outline": methodology_outline
      }
    )
    return theoretical_fdmt_outline

  @listen(theoretical_fdmt_outline_generation)
  @cache_execution(state_variable_to_update='state.sections_and_content', state_update_action='append')
  async def theoretical_fdmt_chapter_generation(self, theoretical_fdmt_outline):
    async def acall_write_topic_crew(
      subsection_title,
      subsection_description,
      topic_title,
      rhetorical_purpose,
      topic_description,
      narrative_guidance
    ):
      theoretical_fdmt_topics_content = (
        await TheoreticalFdmtTopicRagCrew()
        .crew()
        .kickoff_async(
          inputs={
            "theoretical_foundation_subsection_name": subsection_title,
            "theoretical_foundation_subsection_description": subsection_description,            
            "theoretical_foundation_topic_title": topic_title,
            "theoretical_foundation_rhetorical_purpose": rhetorical_purpose,
            "theoretical_foundation_topic_description": topic_description,
            "theoretical_foundation_narrative_guidance": narrative_guidance
          }
        )
      )
      return theoretical_fdmt_topics_content
    
    theoretical_fdmt_section = {
      "section_name": "Fundamentação Teórica",
      "topics": []
    }
    async_tasks_to_exec = []  # Inicia a lista de tarefas
    async_tasks_tags = []  # Lista para ratreabilidade de a qual subseção o resultado da tarefa pertence
    for subsecion in theoretical_fdmt_outline['subsections']:
      subsecion_name = subsecion['subsection_name']

      for discussion_topic in subsecion['discussion_topics']:
        # Cria a tarefa assíncrona de execução da equipe de geração de conteúdo para o tópico
        async_tasks_to_exec.append(
          asyncio.create_task(
            acall_write_topic_crew(
              subsection_title=subsecion_name,
              subsection_description=subsecion['subsection_description'],
              topic_title=discussion_topic['topic_title'],
              topic_description=discussion_topic['topic_description'],
              rhetorical_purpose=discussion_topic['rhetorical_purpose'],
              narrative_guidance=discussion_topic['narrative_guidance']
            )
          )
        )
        # Adiciona o nome da subseção como uma tag de controle, de modo que se possibilita a 
        # reorganização do conteúdo na ordem correta
        async_tasks_tags.append(subsecion_name)
  
    theoretical_fdmt_topics_content = await asyncio.gather(*async_tasks_to_exec)
    for subsecion_name, topic_content in zip(async_tasks_tags,theoretical_fdmt_topics_content):
      # Desempacota e organiza os conteúdos gerados na ordem correta
      topic_content = topic_content.json_dict
      topic_content['subsection'] = subsecion_name  # Cria uma nova chave no dicionário para armazenar a que seção o tópico pertence
      theoretical_fdmt_section['topics'].append(topic_content)

    self.state.sections_and_content.append(theoretical_fdmt_section)
    return theoretical_fdmt_section
  
  @listen(theoretical_fdmt_chapter_generation)
  @cache_execution(state_variable_to_update='state.introduction_outline')
  def introduction_outline_generation(self):
    introduction_context, introduction_outline = IntroductionOutlineCrew().crew().kickoff(
      inputs={
        "report": self.state.draft_report,
        "other_sections_outlines": [
          self.state.results_and_discussion_outline,
          self.state.conclusion_outline,
          self.state.methodology_outline,
          self.state.theoretical_fundamentation_outline
        ]
      }
    )
    return introduction_context, introduction_outline
  
  @listen(introduction_outline_generation)
  @cache_execution(state_variable_to_update='state.sections_and_content', state_update_action='append')
  async def introduction_chapter_generation(self, outline_generation_result):    
    async def acall_write_topic_crew(
      introduction_context,
      subsection_name,
      subsection_description,
      topic_title,
      rhetorical_purpose,
      topic_description,
      narrative_guidance
    ):
      introduction_topics_content = (
        await IntroductionTopicRagCrew()
        .crew()
        .kickoff_async(
          inputs={
            "introduction_consolidated_context": introduction_context,
            "introduction_subsection_name": subsection_name,
            "introduction_subsection_description": subsection_description,
            "introduction_topic_title": topic_title,
            "introduction_rhetorical_purpose": rhetorical_purpose,
            "introduction_topic_description": topic_description,
            "introduction_narrative_guidance": narrative_guidance
          }
        )
      )
      return introduction_topics_content
    
    # CrewAI empacota multiplos outputs em uma lista. Essa etapa os desempacota e os nomeia de modo a melhorar a legibilidade
    introduction_context = outline_generation_result[0]  # Contém o contexto introdutório
    introduction_outline = outline_generation_result[1]  # Contém o dicionário do outline gerado
    introduction_section = {
      "section_name": "Introdução",
      "topics": []
    }
    async_tasks_to_exec = []  # Inicializa a lista de tarefas a ser executada
    async_tasks_tags = []  # Lista para ratreabilidade de a qual subseção o resultado da tarefa pertence
    for subsection in introduction_outline['subsections']:
      for discussion_topic in subsection['discussion_topics']:
        async_tasks_to_exec.append(
          asyncio.create_task(
            acall_write_topic_crew(
              introduction_context=introduction_context,
              subsection_name=subsection['subsection_name'],
              subsection_description=subsection['subsection_description'],
              topic_title=discussion_topic['topic_title'],
              rhetorical_purpose=discussion_topic['rhetorical_purpose'],
              topic_description=discussion_topic['topic_description'],
              narrative_guidance=discussion_topic['narrative_guidance']
            )
          )
        )
        # Adiciona o nome da subseção como uma tag de controle, de modo que se possibilita a 
        # reorganização do conteúdo na ordem correta
        async_tasks_tags.append(subsection['subsection_name'])

    introduction_topics_content = await asyncio.gather(*async_tasks_to_exec)
    for subsection_name, topic_content in zip(async_tasks_tags, introduction_topics_content):
      topic_content = topic_content.json_dict
      topic_content['subsection'] = subsection_name
      introduction_section['topics'].append(topic_content)

    self.state.sections_and_content.append(introduction_section)
    return introduction_section

  @listen(introduction_chapter_generation)
  def save_results(self):
    RESULTS_STORAGE_FOLDER = "results"
    os.makedirs(RESULTS_STORAGE_FOLDER, exist_ok=True)
    print("Resultado:\n")
    print(self.state.sections_and_content)
    if not os.path.exists(os.path.join(RESULTS_STORAGE_FOLDER, "resultados.json")):
      print("\nSalvando Resultados...")
      try:
        with open("resultados.json", "w", encoding="utf-8") as json_file:
          json.dump(self.state.sections_and_content, json_file, ensure_ascii=False, indent=4)
      except (TypeError, IOError) as e:
        # TypeError ocorre se 'result' não for serializável para JSON
        print(f"AVISO: Erro ao salvar resultado: {e}. Resultado não foi salvo.")

def kickoff():
    article_flow = ArticleWriterFlow()
    article_flow.kickoff()


def plot():
    article_flow = ArticleWriterFlow()
    article_flow.plot()


if __name__ == "__main__":
    kickoff()
