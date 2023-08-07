from dotenv import load_dotenv
import os
from flask import Flask, Response, request
import threading
import pinecone
from langchain.llms import OpenAI
from langchain.callbacks.manager import CallbackManager
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Pinecone
from langchain.llms import OpenAI

from langchain.chains import ConversationalRetrievalChain
from flask_cors import CORS
from langchain.chains.conversational_retrieval.prompts import CONDENSE_QUESTION_PROMPT
from utils import PROMPT,ChainStreamHandler,ThreadedGenerator

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')
PINECONE_ENV = os.getenv('PINECONE_ENV')

index_name = 'shubhampanchal'

app = Flask(__name__)
CORS(app=app, resources={r'/*': {'origins': '*'}})

# @app.route('/', methods=['GET','POST'])
# def index():
#     return Response('''
#     <!DOCTYPE html>
#     <html>
#     <head><title>Flask Streaming Langchain Example</title></head>
#     <body>
#         <div id="output"></div>
#         <script>
#             const outputEl = document.getElementById('output');
#             (async function() {  // wrap in async function to use await
#                 try {
#                     const response = await fetch('/chain', {method: 'GET'});
#                     const reader = response.body.getReader();
#                     const decoder = new TextDecoder();
#                     while (true) {
#                         const { done, value } = await reader.read();
#                         if (done) { break; }
#                         const decoded = decoder.decode(value, {stream: true});
#                         outputEl.innerText += decoded;
#                     }
#                 } catch (err) {
#                     console.error(err);
#                 }
#             })();
#         </script>
#     </body>
#     </html>
#     ''', mimetype='text/html')




def llm_thread(g, prompt):
    try:
        streaming_llm = OpenAI(
            verbose=True,
            streaming=True,
            callback_manager=CallbackManager([ChainStreamHandler(g)]),
            openai_api_key=OPENAI_API_KEY,
            temperature=0,
        )
        if index_name not in pinecone.list_indexes():
            return "Index does not exist: "

        embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

        vector_store = Pinecone.from_existing_index(
            index_name, embedding=embeddings)

        vector_store_as_retriever = vector_store.as_retriever(kwargs={'k': 2})

        question_generatorLLM = OpenAI(verbose=True,
                                       streaming=False,
                                       openai_api_key=OPENAI_API_KEY,
                                       temperature=0)

        qa = ConversationalRetrievalChain.from_llm(
            llm=streaming_llm, retriever=vector_store_as_retriever,
            condense_question_prompt=CONDENSE_QUESTION_PROMPT,
            chain_type="stuff",
            condense_question_llm=question_generatorLLM,
            combine_docs_chain_kwargs={"prompt": PROMPT},
        )

        chat_history = []

        qa({"question": prompt, "chat_history": chat_history})
    finally:
        g.close()


def chain(prompt):
    g = ThreadedGenerator()
    # while after returning g from ThreadedGenerator, start llm_thread function in parallel.
    threading.Thread(target=llm_thread, args=(g, prompt)).start()
    return g


@app.route('/chain',methods=['POST','GET'])
def _chain():
    if request.method == 'POST':
        data = request.json
        print(data) 
        query = data["query"]
        return Response(chain(f"{query}\n\n"), mimetype='text/event-stream')
    else:
        return Response(chain(f"what would be your most loved change in this world?\n\n"), mimetype='text/event-stream')

def PineconeSetup():
    pinecone.init(
        api_key=PINECONE_API_KEY,
        environment=PINECONE_ENV
    )
    dbObj = pinecone.describe_index(name=index_name)

    print(dbObj.status)
    if index_name not in pinecone.list_indexes():
        return "Index does not exist: "
    else:
        print("Index exists: " + index_name)


def create_app():
    load_dotenv()
    PineconeSetup()
    # app.run(port=os.getenv('PORT') or 5000, debug=True, threaded=True)
    return app
