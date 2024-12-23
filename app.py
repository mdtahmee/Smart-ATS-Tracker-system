import streamlit as st
import google.generativeai as genai
import os
import PyPDF2 as pdf
from dotenv import load_dotenv
import json
from PIL import Image
import fitz  # PyMuPDF
import plotly.graph_objects as go

# Load external CSS
with open("styles.css") as css_file:
    st.markdown(f"<style>{css_file.read()}</style>", unsafe_allow_html=True)

# Load environment variables
load_dotenv()

# Configure Generative AI API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Function to get a response from Gemini
def get_gemini_response(input):
    try:
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(input)
        return response.text
    except Exception as e:
        st.error(f"Error communicating with the AI model: {str(e)}")
        return None

# Function to extract text from uploaded PDF
def input_pdf_text(uploaded_file):
    try:
        reader = pdf.PdfReader(uploaded_file)
        text = ""
        for page in range(len(reader.pages)):
            page = reader.pages[page]
            text += str(page.extract_text())
        return text
    except Exception as e:
        st.error(f"Error reading the PDF file: {str(e)}")
        return None

# Function to check resume format
def check_resume_format(resume_text):
    ats_friendly = True
    feedback = []

    if len(resume_text.split()) < 200:
        ats_friendly = False
        feedback.append("Your resume text is too short. Consider adding more details.")

    if not any(keyword in resume_text.lower() for keyword in ["skills", "experience", "education"]):
        ats_friendly = False
        feedback.append("Missing standard sections like Skills, Experience, or Education.")

    return ats_friendly, feedback

# Function to convert the first page of the PDF to an image
def pdf_to_image(uploaded_file):
    try:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        page = doc.load_page(0)  # Load the first page
        pix = page.get_pixmap()  # Convert the page to a pixmap (image)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img
    except Exception as e:
        st.error(f"Error converting PDF to image: {str(e)}")
        return None

# Progress circle with only progress bar color change
def circular_progress_bar(value, max_value, label):
    percentage = value / max_value * 100

    # Determine color for the progress bar
    if percentage <= 40:
        color = "darkred"
    elif 41 <= percentage <= 60:
        color = "lightcoral"
    elif 61 <= percentage <= 80:
        color = "orange"
    elif 81 <= percentage <= 90:
        color = "lightgreen"
    else:
        color = "darkgreen"

    # Plotly circular progress bar
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=percentage,
        title={"text": label},  # Dynamically set the label (ATS Score or JD Match %)
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": color},  # Change the progress bar color
            "steps": [  # Keep the background consistent
                {"range": [0, 100], "color": "#e0e0e0"}
            ],
            "threshold": {"line": {"color": "black", "width": 4}, "thickness": 0.75, "value": percentage},
        },
    ))
    st.plotly_chart(fig, use_container_width=True)

# Toggle theme functionality
if "theme" not in st.session_state:
    st.session_state.theme = "light"

def toggle_theme():
    if st.session_state.theme == "light":
        st.session_state.theme = "dark"
    else:
        st.session_state.theme = "light"

st.button("Switch Theme", on_click=toggle_theme)

# Streamlit app UI
st.markdown(
    """
    <div class="main-title">Smart ATS Resume Tracker</div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="description">
        <u class="underline">Upload your resume and paste the job description to get insights on how well your profile matches the role!</u>
    </div>
    """,
    unsafe_allow_html=True,
)

# Input fields
jd = st.text_area(
    "📄 Paste the Job Description (Optional)",
    placeholder="Enter the job description here (Optional)...",
    height=200,
)

uploaded_file = st.file_uploader(
    "📤 Upload Your Resume (PDF)", type="pdf", help="Upload your resume in PDF format."
)

if uploaded_file is not None:
    if uploaded_file.size > 2 * 1024 * 1024:
        st.error("⚠️ File size exceeds 2MB. Please upload a smaller file.")
    else:
        # Show a preview of the uploaded resume
        st.write("📂 **Uploaded Resume:**")
        img = pdf_to_image(uploaded_file)
        if img:
            st.image(img, caption="Uploaded Resume (First Page)", use_container_width=True)

        st.download_button(
            label="📄 View/Download Uploaded Resume",
            data=uploaded_file.getvalue(),
            file_name=uploaded_file.name,
            mime="application/pdf",
        )

# Submit button
submit = st.button("🚀 Evaluate My Resume")

# Evaluation logic with caching to prevent redundant calculations
@st.cache_data
def evaluate_resume(jd_text, resume_text):
    # Ensure input_prompt_with_jd and input_prompt_without_jd are defined
    if jd_text:
        formatted_prompt = f"Job Description: {jd_text}\nResume Text: {resume_text}"
    else:
        formatted_prompt = f"Resume Text: {resume_text}"

    response = get_gemini_response(formatted_prompt)
    return response

if submit:
    if uploaded_file is not None:
        text = input_pdf_text(uploaded_file)
        ats_friendly, feedback = check_resume_format(text)

        if not ats_friendly:
            st.error("⚠️ Your resume is not ATS-friendly.")
            for point in feedback:
                st.write(f"- {point}")
        else:
            response = evaluate_resume(jd, text)
            if response:
                try:
                    response_data = json.loads(response)

                    st.success("🎉 Evaluation Complete!")
                    st.subheader("💼 Your ATS Evaluation Results")

                    if jd:
                        match_percentage = int(response_data.get("JD Match", "0").replace("%", ""))
                        circular_progress_bar(match_percentage, 100, "JD Match %")

                        st.write("🎯 **Role Status:**")
                        if 0 <= match_percentage <= 30:
                            st.write("❌ You are not eligible for this job role.")
                            st.write("💰 Expected Salary: 2k")
                        elif 31 <= match_percentage <= 60:
                            st.write("⚠️ Please update your resume for this job role.")
                            st.write("💰 Expected Salary: 4k")
                        elif 61 <= match_percentage <= 80:
                            st.write("✅ Good, but you need to update your resume.")
                            st.write("💰 Expected Salary: 5k to 6k")
                        elif 81 <= match_percentage <= 100:
                            st.write("🎉 Congrats, you are perfect for this job role!")
                            st.write("💰 Expected Salary: 6k to 7k")

                        st.write("📋 **Missing Keywords:**")
                        missing_keywords = response_data.get("MissingKeywords", [])
                        if missing_keywords:
                            st.write(", ".join(missing_keywords))
                        else:
                            st.write("No keywords are missing. Great job!")
                    else:
                        ats_score = int(response_data.get("ATS Score", "0").replace("%", ""))
                        circular_progress_bar(ats_score, 100, "ATS Score")

                        st.write("📊 **ATS Score**:", ats_score)
                        st.write("💪 **Strong Points in Resume:**")
                        strong_points = response_data.get("StrongPoints", [])
                        if strong_points:
                            st.write(", ".join(strong_points))
                        else:
                            st.write("No strong points identified.")

                        st.write("💡 **Suggestions for Improvement:**")
                        st.write(response_data.get("Suggestions", "No suggestions provided."))

                        st.write("📌 **Conclusion about Resume:**")
                        st.write(response_data.get("Conclusion", "No conclusion provided."))

                except json.JSONDecodeError as e:
                    st.error(f"Failed to parse the response: {str(e)}")
            else:
                st.error("Resume evaluation failed.")
    else:
        st.warning("⚠️ Please upload your resume before submitting!")
      
