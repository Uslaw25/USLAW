import os
import logging
import time
from datetime import datetime
from typing import List, Dict, Tuple, Any, Optional

from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_openai import ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone
# from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_community.document_loaders.text import TextLoader
from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain_community.document_loaders import UnstructuredWordDocumentLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import chainlit as cl
from langsmith import traceable

# Configure logger
logger = logging.getLogger("swedish_law_chat")

class LawAgent:
    """Class to handle Swedish Law Chat functionality"""
    PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
    PINECONE_ENV = os.environ.get("PINECONE_ENV", "us-west1-gcp")
    PINECONE_INDEX = os.environ.get("PINECONE_INDEX")
    # Define supported file loaders
    FILE_LOADERS = {
        "txt": TextLoader,
        "csv": CSVLoader,
        "pdf": PyPDFLoader,
        "doc": UnstructuredWordDocumentLoader,
        "docx": UnstructuredWordDocumentLoader,
    }
    
    # # UI text in Swedish
    # UI_TEXT = {
    #     "processing_question": "Bearbetar din fråga...",
    #     "understanding_context": "Förstår din fråga i sammanhanget...",
    #     "searching": "Söker efter relevant juridisk information...",
    #     "processing_files": "Bearbetar uppladdade filer...",
    #     "retrieved_docs": "Hämtade dokument",
    #     "error_processing": "Fel vid bearbetning av fil",
    #     "unsupported_file": "Filtyp stöds inte",
    #     "supported_formats": "Format som stöds är",
    #     "settings_updated": "Inställningarna har uppdaterats",
    #     "processed": "Bearbetade",
    #     "files": "filer",
    #     "extracted": "extraherade",
    #     "text_chunks": "textavsnitt"
    # }
    
    def __init__(self):
        """Initialize the chat handler"""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        self.vector_store = None
    
    def initialize_pinecone(self) -> Pinecone.Index:
        """Initialize Pinecone client and return the index"""
        logger.info("Initializing Pinecone client")
        start_time = time.time()
        pc = Pinecone(api_key=self.PINECONE_API_KEY)
        index = pc.Index(self.PINECONE_INDEX)
        logger.info(f"Pinecone initialized in {time.time() - start_time:.2f} seconds")
        return index
    
    def create_vector_store(self, index: Pinecone.Index) -> PineconeVectorStore:
        """Create and return a vector store with the given index"""
        logger.info("Creating vector store with OpenAI embeddings")
        start_time = time.time()
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        vector_store = PineconeVectorStore(index=index, embedding=embeddings)
        logger.info(f"Vector store created in {time.time() - start_time:.2f} seconds")
        return vector_store
    
    def setup_vector_store(self) -> Optional[PineconeVectorStore]:
        """Set up the vector store"""
        try:
            index = self.initialize_pinecone()
            self.vector_store = self.create_vector_store(index)
            logger.info("Knowledge base initialized successfully")
            return self.vector_store
        except Exception as e:
            logger.error(f"Error initializing vector store: {e}")
            return None


    @traceable(name="RegenerateQuestionChain")
    def regenerate_question(self, chat_history: List[Dict[str, str]], current_question: str) -> str:
        """
        Regenerate the user's question based on the conversation history to provide context
        for follow-up questions and maintain conversation flow.
        """
        logger.info(f"Regenerating question based on conversation history: '{current_question}'")
        start_time = time.time()
        
        # Initialize the chat model for question regeneration
        chat = ChatOpenAI(model="gpt-4.1-2025-04-14", temperature=0)
        
        # Convert chat history to LangChain message format
        messages = []
        for message in chat_history:
            if message["role"] == "user":
                messages.append(HumanMessage(content=message["content"]))
            else:  # assistant
                messages.append(AIMessage(content=message["content"]))
        
        # Add the current question
        messages.append(HumanMessage(content=current_question))
        
        # Define the system prompt for question regeneration
        system_prompt = """
        Based on the conversation history and the user's current question, generate a comprehensive 
        question that captures the full context of what the user is asking. If the current question 
        is a follow-up or references previous parts of the conversation, incorporate that context 
        into the regenerated question. If the current question is completely new and unrelated to 
        the conversation history, return the original question unchanged.
        Dont add anything in the generated question on your own.
        Output ONLY the regenerated question, nothing else.
        
        
        """
        
        # Create the prompt template
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="history"),
                ("user", "Current question: {question}\nRegenerated question:")
            ]
        )
        
        # Generate the regenerated question
        chain = prompt | chat
        regenerated = chain.invoke({
            "history": messages[-8:-1],  # All messages except the current question
            "question": current_question
        })
        
        result = regenerated.content.strip()
        logger.info(f"Question regenerated in {time.time() - start_time:.2f} seconds")
        logger.info(f"Original: '{current_question}' → Regenerated: '{result}'")
        
        return result
    
    async def process_uploaded_files(self, files: List[Any]) -> Tuple[List[Document], str]:
        """Process uploaded files and extract their content"""
        logger.info(f"Processing {len(files)} uploaded files")
        processed_docs = []
        file_info = []
        
        for file in files:
            try:
                # Extract file extension
                file_extension = file.name.split(".")[-1].lower()
                file_info.append(f"- {file.name} ({file_extension.upper()})")
                
                # Get appropriate loader
                loader_class = self.FILE_LOADERS.get(file_extension)
                
                if loader_class:
                    logger.info(f"Loading file {file.name} with {loader_class.__name__}")
                    loader = loader_class(file.path)
                    docs = loader.load()
                    
                    # Split documents into chunks if they're too large
                    split_docs = self.text_splitter.split_documents(docs)
                    processed_docs.extend(split_docs)
                    
                    logger.info(f"Successfully processed {file.name}, extracted {len(split_docs)} chunks")
                else:
                    logger.warning(f"Unsupported file extension: .{file_extension}")
                    # Note: We'll handle UI messages in the main app
            except Exception as e:
                logger.error(f"Error processing file {file.name}: {str(e)}")
                # Note: We'll handle UI messages in the main app
        
        return processed_docs, "\n".join(file_info)
    
    @traceable(name="RetrieveAndGenerateResponseChain")
    async def retrieve_and_generate_response(
        self,
        msg,
        query: str, 
        chat_history: List[Dict[str, str]], 
        additional_docs: Optional[List[Document]] = None
    ) -> Tuple[str, List[Document]]:
        """Retrieve documents and generate a response"""
        logger.info(f"Starting retrieval and response generation for query: '{query}'")
        retrieval_start_time = time.time()
        
        if not self.vector_store:
            logger.error("Vector store not initialized")
            return "I'm sorry, but the knowledge base is not available right now. Please try again later.", []
        
        # Create a retriever with similarity score threshold
        retriever = self.vector_store.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"k": 50, "score_threshold": 0.6},
        )
        # Retrieve relevant documents
        docs = retriever.invoke(query)[:2]
        logger.info(f"GOT DOCUMENTS FROM RETRIEVER length = {len(docs)}" )
        # Add additional documents from file uploads if available
        if additional_docs:
            docs.extend(additional_docs)
            logger.info(f"Added {len(additional_docs)} documents from uploaded files")
        
        logger.info(f"Retrieved total of {len(docs)} documents in {time.time() - retrieval_start_time:.2f} seconds")
        chat = ChatOpenAI(model="gpt-4.1-2025-04-14", temperature=0.4)
        
        # Define the system template
        uslaw_expert_prompt = """
        You are a legal expert specializing in United States family law, including divorce, child custody, child support, spousal support (alimony), parenting plans, and related areas governed by federal and state statutes.

        **Your Role:**
        Provide expert-level legal analysis by interpreting and summarizing U.S. legal documents, laws, and case rulings strictly based on the contextual data provided from the legal knowledge base.
        
        **Core Requirements:**
        - Analyze provided context (statutes, case law, legal commentary, state codes) and generate accurate, professional answers
        - Use precise legal citation format (e.g., "Cal. Fam. Code § 3020," "42 U.S.C. § 651," "Fla. Stat. § 61.13")
        - Explain laws with in-depth legal detail, proper terminology, and technical precision as an expert attorney would
        - Quote or paraphrase relevant legal text directly from the context
        - When law varies by state, specify which jurisdiction applies
        - Use structured Markdown formatting: headings, bullet points.
        - Distinguish legal terms precisely (e.g., "legal custody" vs. "physical custody")
        - If multiple interpretations exist, explain them objectively
        - State clearly if context is insufficient: "Based on the provided context, a complete answer is not available."
        
        **Privacy Requirements:**
        - NEVER disclose PII from context (names, addresses, case numbers, etc.)
        - Use generic placeholders: "the petitioner," "the respondent," "Party A"
        - Redact personal information from responses
        
        **Restrictions:**
        - Do not provide legal advice—only factual information from context
        - Do not fabricate legal references—use only provided context
        - Do not mention AI, knowledge bases, or information sources
        - Always note that family law varies by state and users should consult licensed attorneys
        
        <context>
        {context}
        </context>
        
        ---
        Note: 
        - Never use tables in your responses
        - Never mention about your context, or phrases like "based on the provided context" 
        Provide detailed legal analysis using proper citations, technical terminology, and professional legal communication standards.
        """

        # Create the prompt template
        question_answering_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    uslaw_expert_prompt,
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        
        # Prepare messages for the chain
        messages = []
        for message in chat_history:
            if message["role"] == "user":
                messages.append(HumanMessage(content=message["content"]))
            else:  # assistant
                messages.append(AIMessage(content=message["content"]))
        
        # Add the current query
        messages.append(HumanMessage(content=query))
        
        # Create the document chain
        document_chain = create_stuff_documents_chain(chat, question_answering_prompt)
        
        # Generate the response
        logger.info("Starting response generation")
        generation_start_time = time.time()
        
        try:
            async for token in document_chain.astream(
                {
                    "context": docs,
                    "messages": messages,
                }
            ):
                await msg.stream_token(token)

            # Update with final content
            await msg.update()
            logger.info(f"Response generated in {time.time() - generation_start_time:.2f} seconds")
            return msg.content, docs
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I'm sorry, but I encountered an error while generating a response. Please try again.", []
