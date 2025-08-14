from pydantic import BaseModel, Field
from typing import List
from enum import Enum

class SectionTitle(str, Enum):
  THEORETICAL_FUNDAMENTATION = "Introduction"

class DiscussionTopic(BaseModel):
  topic_title: str = Field(description="Concise title or description of the introductory  topic (e.g., 'Preparação de Amostras', 'Análise Estatística').")
  rhetorical_purpose: str = Field(
    description="Rhetorical purpose of the introductory  topic (e.g., 'Describe research design', 'Detail experimental procedure')."
  )
  topic_description: str = Field(
    description="Brief summary of the topics's focus, key parameters, or specific details relevant for writting about it."
  )
  narrative_guidance: str = Field(
    description="Clear and actionable guidance for the Writer Agent on how to elaborate on this topic, emphasizing clarity, detail, and replicability."
  )

class IntroductionSubSection(BaseModel):
  subsection_name: str = Field(
    description="A concise title for the subsection"
  )
  subsection_description: str = Field(
    description="A brief summary outlining the key elements that will be covered within this subsection."
  )
  discussion_topics: List[DiscussionTopic] = Field(
    default_factory=list,
    description="List of topics to be discussed in the subsection."
  )

class IntroductionSectionOutline(BaseModel):
  section_name: SectionTitle = Field(
    description="Name of the section, set to 'Introduction'."
  )
  subsections: List[IntroductionSubSection] = Field(
    default_factory=list,
    description="List of the subsections of the main section."
  )
