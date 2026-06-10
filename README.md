# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->

My system covers UConn professor reviews. This knowledge is valuable because these are real reviews that students who have taken the class have submitted. 

---

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

| # | Source | Description | URL or location |
|---|--------|-------------|-----------------|
| 1 |Rate my Professor | Lina Kloub RMP and her ratings | https://www.ratemyprofessors.com/professor/2754387|
| 2 |Rate my Professor | Olga Glebova RMP and her ratings | https://www.ratemyprofessors.com/professor/2963544|
| 3 |Rate my Professor | Swamy Narayan Jignaas Pattipati RMP and his ratings | https://www.ratemyprofessors.com/professor/3044671|
| 4 |Rate my Professor | Justin Furuness RMP and his ratings| https://www.ratemyprofessors.com/professor/3127655|
| 5 |Rate my Professor | David Strimple RMP and his ratings| https://www.ratemyprofessors.com/professor/2872422|
| 6 |Rate my Professor | Derek Aguiar RMP and his ratings| https://www.ratemyprofessors.com/professor/2460362|
| 7 |Rate my Professor | Laurent Michel RMP and ratings| https://www.ratemyprofessors.com/professor/1135923|
| 8 |Rate my Professor | Zhijie 'Jerry Shi RMP and ratings| https://www.ratemyprofessors.com/professor/1282131|
| 9 |Rate my Professor | Yufeng WU RMP and ratings| https://www.ratemyprofessors.com/professor/1756272|
| 10 |Rate my Professor| Jonathan Clark RMP and ratings| https://www.ratemyprofessors.com/professor/2898389|

---

## Chunking Strategy

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:**

128 tokens

**Overlap:**

20 tokens   

**Reasoning:**

Since each review is seperate from each other, the overlap doesn't have to be as drastic since it will be searching for keywords only. Recursive chunking strategy is probably best for this document type.

**Final chunk count:**

128 tokens

---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Embedding model:**

all-MiniLM-L6-v2

**Production tradeoff reflection:**

If cost were not a constraint, I would most likely use a larger hosted embedding model such as OpenAi's embedding model. This is due to the fact that larger models will usually provide more accurate responses when asked complex questions.

When choosing a production model, I would weigh things like accuracy, context length limits, multilingual support, and latency. While a larger model might perform better and support more languages it can cause more latency as well. This is why all-MiniLM-L6-v2 which runs locally on the computer, provides fast response times, is simplier and provides low latency compared to larger hosted models.

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction:**

My system enforces grounding since the model recieves only the retrieved chunks. The model does not have web access, or conversation memory which means it only uses the source material which are the text files it contains. Also,. in my prompt I told it to only use context recieved from the text files and if there isn't enough context for an answer reply with the reviews don't contain enough information to answer that.

**How source attribution is surfaced in the response:**

Source attribution is displayed through numbered citations embedded in the generated response. Each citation corresponds to a specfic chunk or review used to support the response. Also, below the response, are the top 5 sources listed with the original text, and its relavance score. This allows users to verify the information recieved. 

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 |Is Swamy a good lecturer and does he make class engaging? | Yes, he is a great lecturer who makes class engaging and challenging for students. | He is a good lecturer and many students find his lectures interesting and engaging. There are few that find it not engaging. Overall mixed reviews mostly positive.| Relevant | Accurate|
| 2 |Does Lina Kloub prepare students for exams and are they difficult? | Lina Kloub's exams tend to be a little difficult but most of the work on the exams are similar to those on her homework assignments and lectures.| Lina Kloub prepares her students for their exams through her study materials. The difficulty of the exams can vary but most students say its manageable.| Relevant | Accurate|
| 3 |Does Olga Glbova give a lot of homework throughout the week? | Yes, She assigns Zybooks every couple days and these can take a long time to complete.| Olga assigns a significant amount of homework with students describing it as "homework heavy."| Relevant| Accurate|
| 4 |Does Justin Furuness have lots of office hours for help when needed? |Yes, He is very acessible outside of class and tries to help  of his students to the best of his abilities. | Justin is availble outside of class and is described as "incredible helpful."| Relevant| Accurate |
| 5 |Is David Strimple a tough grader? | Yes, He is an extremely tough grader that assigns lots of homework.| David is considered a tough grader since he takes points off for minor mistakes and grades harshly.| Relevant |Accurate |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:**

Which professor is the toughest grader?

**What the system returned:**

The system returned this response:

Yufeng Wu and Swamy Narayan Jignaas Pattipati are both considered tough graders [1][2][3][4][5]. Yufeng Wu's exams have no curve and extremely difficult, with an average of a failing grade [2], while Swamy Narayan Jignaas Pattipati's exams are also extremely difficult and strict on cheating [5]. However, the difficulty level of Yufeng Wu's classes is rated as 5.0 [2][3][4], which is higher than Swamy Narayan Jignaas Pattipati's average difficulty level of 3.6 [1] and 5.0 in one specific class [5].

I would say this is a partial fail or at least it didn't work as it should have. This is due to the fact that since my system only uses the top 5 chunks the model will not see all the professors. This makes it so the model gives a response based on just the 5 nearest chunks instead of 1-2 chunks per professor.

**Root cause (tied to a specific pipeline stage):**

The Root cause is in my retrieval since it only takes the top-k=5 which makes it only takes 5 chunks.

**What you would change to fix it:**

One thing I would have to change is how my system works when asked these type of questions. Since my system takes the nearest chunks even if the chunks increase to 10 to match the amount of professors it might get multiple chunks instead of 1-2 chunks per professor. I would try to make it so it detects a multiple professor question and instead of top-k search it will get 1-2 chunks from each professor that are relevant to the question and then compare those chunks with each other. This would make the response less bias and allow for more context.

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:**

Having to think out the pipeline and create it helped have not only the visual model, but also the understanding of how my system will work and what needs to be implemented for it to work. Also, the evaluation questions created was helpful when having to see how accurate my responses came out.

**One way your implementation diverged from the spec, and why:**

One way I diverged was I changed the the amount of tokens or the chunks to 128 instead of 250 and the overlap to 20. This was due to the fact that after running I was getting 44 chunks which was fewer than I had intended to have and reducing the tokens made it so one review was one chunk whihc made things flow better.

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- *What I gave the AI:* 

I gave AI the pipeline and asked it to generate responses using the text files and to cite the sources to make sure they are valid.

- *What it produced:*

It created the code to generate the responses but when testing it only showed the citations and the link to the website where the reviews could be found instead of the review and then the link.

- *What I changed or overrode:*

I changed the format_sources_md function slightly to where it has the actual review text where the chunk chunk came from.

**Instance 2**

- *What I gave the AI:*

I gave AI the pipeline and asked it to generate code to retreive my code from embedding.py and implement the loading of the chunks and storing into ChromaDB.

- *What it produced:*

It created code that generated a response and put the chunks that are relevant below. Only issue is that it showed chunks that were from other professors.

- *What I changed or overrode:*

Made a retrieve function that detects the professor and then auto filters to that professor. This way if the user searches a specific professor without the dropdown on their names it will auto do it for them.
