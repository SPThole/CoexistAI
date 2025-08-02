prompts = {

'youtube_summary_prompt':"""Analyze and respond the task using the given transcript in detail, following these guidelines:

1. Understand the user's intent and perspective.
2. Focus on what would be most interesting and valuable to the user.
3. Provide an informative, engaging response with depth and insight.
4. Use emojis to enhance readability and engagement.
5. Adhere to the specific task: {task}
6. Just focus on task, thats all, dont add additional details about video or creator unless asked.

Transcript to summarize:
{transcript}

Remember to make the response comprehensive, enjoyable to read, and tailored to the user's interests while addressing the specified task.
""",

'reddit_summary_prompt':"""Create a comprehensive response based on of the following Reddit posts and comments, focusing on the objective: {search_query}

Please provide the comprehensive response.

Guidelines:
1. Follow the objective
2. Include hyperlinks to relevant posts/comments.
3. Maintain technical accuracy and detail.

IMPORTANT: Strictly adhere to the provided content. If no relevant discussions are found related to the summary objective, please state this clearly.
""",

"summ_qa": """Your task is to classify given query into 2 categories: Summary or QA on the basis of the nature of query
    If the query explicitly asks for summary, then give "SUMMARY" as output class or else "QA" 
    Give output in json format
    Dict["verdict":str[SUMMARY or QA]]
    
    Query:{query}""",

"summary_generation":"""Your task is to generate detailed response/summary based on the given documents wrt to answer user query :{query}
          Documents: {comb_docs}
          """  ,

"qa_response_generation":"""Instructions:

Understand the query thoroughly, even if it contains misspellings or errors. Use the provided context and related information to interpret the intended meaning.

Answer the query using the context and available information; if the context is insufficient, utilise whatever information is relevant, its fine even if answer is incomplete. utilize your own knowledge to provide a complete answer, including code if requested.

Provide direct answers: If the query asks for code, supply the code rather than a plan to implement it. Learn facts, syntax, and structures from the context to create accurate responses.

Enhance your response with engaging details, clear reasoning, and simple explanations. Use analogies to illustrate difficult concepts when appropriate.

Cite sources for every detail using hyperlinks to the search result URLs; if using your own knowledge, cite as "llm_generated". Structure your answer in markdown format with bullet points. Utilize the context fully, even if it doesn't directly answer the question. Mention any next steps in next_steps; otherwise, write None.

Query:

{query}

Context:

{context}

Provide your response in the following JSON format, KEEP ANSWER CONCISE UNLESS ASKED FOR DETAILED.:
Dict[
  "intent_understanding": "string",
  "synthesized_answer_based_on_various_sources": "Think and implement in step by step manner to get to answer to the query, answer even if limited information is provided, utilise all the info you have",
  "interesting_info_around_query": "string",
  "sources": ["links"],
  "next_steps": "string"
]
""",

"query_agent_basic":"""Context: Today's date is {date}, Bangalore, India.

Instructions:

Use date/location only if the query requires time-sensitive or location-specific information.
Replace time-specific words with context details.
Rephrase the query for search engine optimization and clarity.
Avoid including the date if not necessary.
Emphasize date or location when needed.
When breaking down into multiple tasks, always consider the overall task to ensure every aspect is included. By the end of searching for subqueries, there should be enough information to process the answer.
If necessary, split the query into up to 2 diverse subqueries to cover all aspects.
Subqueries should not be in a numbered list.
Plan searches to answer every part of the query without overemphasizing any term.
Ensure that subqueries include essential keywords and context from the original query to maintain relevance.
Avoid generating subqueries that are too generic or lack specific terms from the original query.
When rephrasing, retain the main subject and important details from the original query in each subquery.

Original Query: {query}

Use this JSON schema:

planning_to_answer_query_to_help_finding_subqueries: [Up to 6 planning steps breaking down the task without overemphasizing any keyword],
subqueries: [Up to 6 rephrased phrases covering all planning steps in independent search phrases , using a maximum of 4 words per subquery, avoiding unnecessary adjectives].
""",

"combine_answers":"""Combine the following two responses into one comprehensive answer that includes all unique, relevant details from both, maintaining all citations and references. Ensure no information is lost; fully integrate both answers. In the field your_view_and_analysis, add your own knowledge and insights, which may or may not be based on the provided context. Avoid generating escape characters or JSON that could cause parsing errors. Think step-by-step about how to utilize your knowledge and the available information to answer the query.

Given:

query: {query}
answer_1: {answer1}
answer_2: {answer2}
Provide the final answer in the following JSON format:
Dict[
  "final_answer": "string",
  "your_view_and_analysis": "string",
  "sources": ["links"]
]
    """,

"llm_review_basic":"""Analyze the query, previous answer, and earlier search phrases. Formulate new search phrases to gather information and complete missing parts of the current answer using the 'Next Steps' section. Avoid ideas requiring apps you cannot access. Think differently if previous context was insufficient. Provide new search phrases to supplement the current answer, thinking like an expert in the field. DONT LOSE OUT ON ANY INFORMATION FROM ANY ANSWER, SUPPELEMENTARILY ADD BOTH

Given:

Query: {query}
Previously used search phrases: {earlier_searches}
Context: {context}
Current answer: {answer}
Plan your searches to fulfill the user query.

Subqueries: List 2 (up to 6 if needed) rephrased phrases covering all planning steps, maximum 4 words per subquery, avoiding unnecessary adjectives.

Provide your response in JSON format:
"subqueries": [
  "phrase1",
  "phrase2"
]
Ensure the new search phrases:

Address all unanswered aspects of the query.
Use the 'Next Steps' section.
Expand on the information in the current answer.
Use URLs or structures from the answer if needed.
Use API knowledge to design keyphrases involving real-time data like flights or rail tickets, as these will be used to search Google.
You can also use URLs as search phrases. DONT LOSE ANY INFO, KEEP ANSWER CONCISE UNLESS ASKED FOR DETAILED.
""",

"web_or_llm":"""You will receive a user message. Determine whether to answer it directly using your internal knowledge (LLM) or by utilizing web search.

Decision Logic:

If the user explicitly requests a web search, use web search.
If the query can be answered confidently based on your existing knowledge and prior chat, answer directly using your LLM capabilities.
You will get the information based on the query, if the query is referring to prior message or not
If the query requires external information or you are unsure of the answer, utilize web search.
Output your decision in the following dictionary format: Dict["verdict":str[web or llm]]. Dont add ``json infront of it.
Query: {query}""",

'qa_response_final_touch':"""Go through the given query in detail, see what all is asked by user: {query}
To this query, this is the answer I have formed till now: {response}
Your task is to fill the gap between the things user asked and my answer, and build upon and refine the answer (if at all it is necessary to answer the query). If some facts are not there, dont make it up, stick to the information given.
Give the final answer which fullfills users request. Facts and sources/citations should not be altered. 
You are given with context, which has real time data, never say that you dont have access to real time data. ALWAYS well structure your answer. Hyperlink the sources in words. Give answer in markdown format and not json.
""",

"summ_qa_url_router":"""Your task is to classify given query into 2 categories: YES or NO
    If the query explicitly asks for information that needs information from maps, say YES else NO
    There are 2 types of functions one which gives information about route, if the query needs to find route between two destinations then give them under SRC_DST else None, this should be filled only when nearby is None
    SRC and DST should be similar to what would you put in google maps
    If the query asks for things like nearby hospitals, then give answer in NEARBY as ['hospital'] else [],add in the list even if there is single element
    Give output in json format
    Dict["verdict":str[YES or NO], "SRC_DST":[SRC, DST] , "NEARBY":[list of str of type of thing you want to find nearby],"if_nearby_then_loc":[list of str of locations around which information is needed if nearby is not none]]

    
    Query:{query}""",

"summary_generation":"""Your task is to generate detailed summary of the given documents to answer user's query :{query}
          Documents: {comb_docs}
          Stick to given documents, summary should look like an answer to the query, enlist assumptions made  (if any)
          """ ,



}

place = 'Bangalore, India'


