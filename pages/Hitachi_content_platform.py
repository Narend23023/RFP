# -*- coding: utf-8 -*-
"""Netapp_retrieval.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1hz5A3FxAirODDdJt3cveDJLnPXxB6P3g
"""


# ! pip install -U langchain openai chromadb langchain-experimental
# !apt-get install tesseract-ocr
# !pip install openai
# !pip install langchain_chroma langchain_community langchain_openai
# !apt-get install poppler-utils
# !pip install google.generativeai langchain-google-genai

from langchain.storage import InMemoryByteStore,LocalFileStore
from langchain.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings,ChatOpenAI
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain_core.documents import Document
import uuid
import base64
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage
# from google.colab import files
from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_google_genai import ChatGoogleGenerativeAI
#import google.generativeai as genai
from langchain.agents import tool
from langchain_core.messages import HumanMessage, SystemMessage
import streamlit as st
import io
import re
from IPython.display import HTML, display
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from PIL import Image

st.set_page_config(layout="wide")
st.title("HCP RFP")
#################################APIKeY################################################
with st.sidebar:
    GEMINI_API_KEY = st.text_input("GEMINI API KEY", key="chatbot_api_key", type="password")
#################################APIKEY################################################

__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import chromadb


# from google.colab import userdata
# OPENAI_API_KEY=userdata.get('OPENAI_API_KEY')
# GEMINI_API_KEY=userdata.get('GEMINI_API_KEY')

embedding_func = OpenAIEmbeddings(api_key=st.secrets['OPENAI_API_KEY'])


################################# Loading Vector Database #############################
db3 = Chroma(persist_directory="/mount/src/RFP/VECTORS_HCP/", collection_name="netapp_embeddings",embedding_function=embedding_func)
embeddings = db3.get(include=['documents','metadatas','embeddings'])

retriever1=db3.as_retriever()
#######################################################################################


#################Initialize session state to store history#############################

# if "gemini_model" not in st.session_state:
#     st.session_state["gemini_model"] = "gemini-1.5-pro"

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
#######################################################################################


################################ Initialize the storage layer##########################
store_netapp  = LocalFileStore(root_path="/mount/src/RFP/PARENT_DOCUMENTS_HCP/")
id_key = "doc_id"

# Create the multi-vector retriever
retriever_test = MultiVectorRetriever(
        vectorstore=db3,
        docstore=store_netapp,
        id_key=id_key,
    )
#######################################################################################

############################## Functions Required for Retrieval #######################
def plt_img_base64(img_base64):
    """Disply base64 encoded string as image"""
    # Create an HTML img tag with the base64 string as the source
    image_html = f'<img src="data:image/jpeg;base64,{img_base64}" />'
    # Display the image by rendering the HTML
    display(HTML(image_html))


def looks_like_base64(sb):
    """Check if the string looks like base64"""
    # Decode the bytes object to a string before applying the regex
    if isinstance(sb, bytes):
        sb = sb.decode('utf-8')
    return re.match("^[A-Za-z0-9+/]+[=]{0,2}$", sb) is not None


def is_image_data(b64data):
    """
    Check if the base64 data is an image by looking at the start of the data
    """
    image_signatures = {
        b"\xff\xd8\xff": "jpg",
        b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a": "png",
        b"\x47\x49\x46\x38": "gif",
        b"\x52\x49\x46\x46": "webp",
    }
    try:
        header = base64.b64decode(b64data)[:8]  # Decode and get the first 8 bytes
        for sig, format in image_signatures.items():
            if header.startswith(sig):
                return True
        return False
    except Exception:
        return False


def resize_base64_image(base64_string, size=(128, 128)):
    """
    Resize an image encoded as a Base64 string
    """
    # Decode the Base64 string
    img_data = base64.b64decode(base64_string)
    img = Image.open(io.BytesIO(img_data))

    # Resize the image
    resized_img = img.resize(size, Image.LANCZOS)

    # Save the resized image to a bytes buffer
    buffered = io.BytesIO()
    resized_img.save(buffered, format=img.format)

    # Encode the resized image to Base64
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def split_image_text_types(docs):
    """
    Split base64-encoded images and texts
    """
    b64_images = []
    texts = []
    for doc in docs:
        # Check if the document is of type Document and extract page_content if so
        if isinstance(doc, Document):
            doc = doc.page_content
        if looks_like_base64(doc) and is_image_data(doc):
            doc = resize_base64_image(doc, size=(1300, 600))
            b64_images.append(doc)
        else:
          if isinstance(doc,bytes):
            doc=doc.decode('utf-8')
          texts.append(doc)
    return {"images": b64_images, "texts": texts}


def img_prompt_func(data_dict):
    """
    Join the context into a single string
    """
    formatted_texts = "\n".join(data_dict["context"]["texts"])
    messages = []

    # Adding image(s) to the messages if present
    if data_dict["context"]["images"]:
        for image in data_dict["context"]["images"]:
            image_message = {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image}"},
            }
            messages.append(image_message)

    # Adding the text for analysis
    text_message = {
        "type": "text",
        "text": (
            f"""
              You are an expert Hitachi Content Platform(HCP) consultant. Your role is to provide professional advice based on the information provided to you. Use the following context, which may include text, tables, and images, to answer the user's question. Ensure that your response does not mention the provided context, text, or document.

              Instructions:
              1. If there is no relevant context or exact information available; the output should be “No Answer”. 
              2. If Partial Answer is available; The output should include “Partial Answer Available” followed by the answer and also mention which aspect of the question you were unable to answer.
              3. Answer length should be not exceed more than 75-80 words or 7-8 lines.
              4. As you are Hitachi Content Platform consultant(HCP), in your response you should not mention about the context, text, or document that you are provided with for any reason.
              5. Your only source of information required to answer will be in the context provided and do not use your previous training to answer these questions.
              6. You are Hitachi Content Platform(HCP) consultant. Hence, you should refrain from telling user to visit HCP documentation or any other refrences at the end of your response.
              7. Use bullet points where necessary.



Context:
{formatted_texts}

User-provided question:
{data_dict['question']}
"""
# 4. If there is insufficient information, state: "There is not enough information to provide a complete answer to your question."
            # "Note: if you dont have any information, dont mention that the given context/document/text doesnt contain the answer, just state that you dont have enough information to provide a complete answer. \n"
            # "You are an expert NET App Storage grid consultant. Hence, dont mention anything to the user about the given context/text or the document you are provided with. \n"
            # "You will be given a mixed of text, tables, and image(s) usually of charts or graphs.\n"
            # "Use this information to provide response related to the user question in detail. structure your ouput properly and use bullet points as and when needed. \n"
            # f"User-provided question: {data_dict['question']}\n\n"
            # "Text and / or tables:\n"
            # f"{formatted_texts}"
        ),
    }
    messages.append(text_message)
    #print(messages)
    return [HumanMessage(content=messages)]


def multi_modal_rag_chain(retriever,GEMINI_API_KEY):
    """
    Multi-modal RAG chain
    """

    # Multi-modal LLM
    gemini_model=ChatGoogleGenerativeAI(model= "gemini-1.5-flash",google_api_key=GEMINI_API_KEY)
    #model = ChatOpenAI(temperature=0, model="gpt-4", max_tokens=1024,api_key=OPENAI_API_KEY)

    # RAG pipeline
    chain = (
        {
            "context": retriever | RunnableLambda(split_image_text_types),
            "question": RunnablePassthrough(),
        }
        | RunnableLambda(img_prompt_func)
        | gemini_model
        | StrOutputParser()
    )

    return chain


# Create RAG chain
if GEMINI_API_KEY:
    chain_multimodal_rag = multi_modal_rag_chain(retriever_test,GEMINI_API_KEY)
    gemini_model = ChatGoogleGenerativeAI(model='gemini-1.5-flash',api_key=GEMINI_API_KEY,temperature=0)
else:
    st.write('Provide gemini API key to proceed')



def get_modified_prompt(user_prompt):
    """Get the user prompt and reframe it to our vendor specific format"""
    messages = [
    SystemMessage(
        content=f"""
        You are an expert Hitachi Content Platform (HCP) consultant. \n 
        Always consider the questions asked by the user from Hitachi Content Platform (HCP) consultant perspective. \n
        Here Solution, software, proposed solution is referred to Hitachi Content Platform (HCP) consultant. \n
        Your job is to take the user question and replace it according to the Hitachi Content Platform (HCP) consultant and provide just the 
        modified question as output. You dont have to reframe or paraphrase the question. \n
        While replacing keep it short and simple, you dont have to add complex words. \n
        While replacing you should cover all aspects of the question and Dont add extra and irrelevant information while generating output. \n
        ----------------------------------------------- \n
        Example: \n
        Query - Provide a detailed description of the proposed solution?
        Response - Provide a detailed description of Hitachi Content Platform.
        """
    ),
    HumanMessage(
        content=f"""{user_prompt}"""
    )
  ]

    return gemini_model.invoke(messages).content

def get_final_response(user_prompt):
    """Get the user prompt and reframe it to our vendor specific and pass it to the chain for final answer"""
    modified_prompt = get_modified_prompt(user_prompt)
    print(modified_prompt)
    return chain_multimodal_rag.invoke(modified_prompt)

#######################################################################################

# Accept user input
if query := st.chat_input("Enter your query here?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": query})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(query)   

    with st.chat_message("assistant"):
        response = get_final_response(query)
    st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})


# ###############################################################################
