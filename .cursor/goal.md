Take Home Assignment: Junior Full Stack AI Developer (AI Product Imagery)
(LangGraph Backend, React/Next.js Frontend)

Assignment Overview
Your task is to build an end-to-end AI-powered solution for extracting and enhancing product images from a YouTube video about a product (review, unboxing, or demo).
Hint: Consider leveraging Google Gemini or similar multimodal models for intelligent frame selection, image segmentation, and generative enhancement.
Tech Stack:
Backend: Python with LangGraph
Frontend: React/Next.js

Assignment Tasks
1. Video Input
Frontend accepts a YouTube video URL (product showcase or review).
2. Key Frame/Image Extraction (LangGraph node/chain)
First identify all products in the video.
Foreach product, let Gemini pick the best frame where the product is shown prominently and clearly.
3. Image Segmentation (LangGraph node/chain)
Segment the product in the selected frame.
Use Gemini’s segmentation capabilities to segment the product image.
Output: Cropped product image
Document your segmentation workflow.
4. Image Enhancement (LangGraph node/chain, Gemini or 3rd-party API)
Enhance the segmented product image to create 2–3 stunning product shots (different backgrounds or styles).
Use Gemini nano banana for this.
Document your enhancement workflow and API integration.
5. Frontend Display (React/Next.js)
Show in the UI:
Identified products and the extracted product frame(s)
Segmented product image(s)
Enhanced product shots
6. Submission
Include a README explaining:
Approach per step
How LangGraph and React communicate (API endpoints, data flow)
Technologies used
How to run/demo
Time spent per section
Challenges faced, how Gemini was utilized, ideas for improvements/scalability

