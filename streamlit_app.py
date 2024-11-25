import streamlit as st
import requests
import datetime
import json
import os
import google.generativeai as genai
import random

# Configure page layout
st.set_page_config(layout="wide", page_title="Professional Course Study Plan")

# Initialize session state
def initialize_session_state():
    if 'user_authenticated' not in st.session_state:
        st.session_state.user_authenticated = False
    if 'conversations' not in st.session_state:
        st.session_state.conversations = {}
    if 'tests' not in st.session_state:
        st.session_state.tests = {}
    if 'flashcards' not in st.session_state:
        st.session_state.flashcards = {}
    if 'gemini_api_key' not in st.session_state:
        st.session_state.gemini_api_key = None
    if 'user_points' not in st.session_state:
        st.session_state.user_points = 0
    if 'current_course' not in st.session_state:
        st.session_state.current_course = None

initialize_session_state()

# Function to authenticate user
def authenticate(username, password):
    return username == "user" and password == "pass"

# Function to query the Gemini API
def query_gemini_api(prompt, api_key, max_retries=3):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text
        except Exception as e:
            if attempt == max_retries - 1:
                raise ValueError(f"Error querying Gemini API after {max_retries} attempts: {str(e)}")
            time.sleep(2 ** attempt)  # Exponential backoff
    
    raise ValueError("No valid response from the Gemini API")


def generate_study_plan_in_batches(course, total_days, level, api_key):
    study_plan = []
    batch_size = 30
    current_day = 1

    while total_days > 0:
        days_to_generate = min(batch_size, total_days)
        prompt = f"""
        Create a {days_to_generate}-day course plan for {course} starting from day {current_day} for a {level} level student. 
        Provide a daily topic breakdown in the following format:

        {current_day}. Topic 1
        {current_day + 1}. Topic 2
        {current_day + 2}. Topic 3
        ...
        {current_day + days_to_generate - 1}. Topic {days_to_generate}

        Ensure each topic is concise (1-5 words) and follows a logical progression.
        """
        
        try:
            response = query_gemini_api(prompt, api_key)
            topics = [line.split('. ', 1)[1].strip() for line in response.split('\n') if line.strip() and '. ' in line]
            if len(topics) != days_to_generate:
                raise ValueError(f"Expected {days_to_generate} topics, but got {len(topics)}")
            study_plan.extend(topics)
        except Exception as e:
            st.error(f"Error generating study plan: {str(e)}")
            return []
        
        current_day += days_to_generate
        total_days -= days_to_generate

    return study_plan



# Function to explain the daily topic
def explain_topic(topic, course, api_key):
    prompt = f"""
    Provide an in-depth explanation of '{topic}' in the context of {course}. Include:
    1. Detailed concept explanation
    2. Relevant theories or frameworks
    3. Real-world applications or case studies
    4. Best practices
    5. Common challenges and how to overcome them
    6. Additional resources for further learning

    Format your response using Markdown for better readability.
    """
    response = query_gemini_api(prompt, api_key)
    return response.strip()

# Function to save the study plan and session data
def save_session_data(course, data):
    with open(f"{course}_session.json", "w") as f:
        json.dump(data, f)

# Function to load the study plan and session data
def load_session_data(course):
    if os.path.exists(f"{course}_session.json"):
        with open(f"{course}_session.json", "r") as f:
            return json.load(f)
    return None

# Load all session data on startup
def load_all_sessions():
    sessions = {}
    for file in os.listdir():
        if file.endswith("_session.json"):
            course = file.replace("_session.json", "")
            sessions[course] = load_session_data(course)
    return sessions

# Function to generate test questions
def generate_test_questions(course, topics, api_key):
    prompt = f"""
    Generate 10 multiple-choice questions to test understanding of the following topics in {course}: {', '.join(topics)}. 
    Format each question as follows:

    Q: [question]
    A) [option]
    B) [option]
    C) [option]
    D) [option]
    Correct: [letter]
    Explanation: [brief explanation of the correct answer]

    Ensure questions cover a range of difficulty levels and aspects of the topics.
    """
    response = query_gemini_api(prompt, api_key)
    return parse_test_questions(response)

def parse_test_questions(response):
    questions = []
    current_question = {}
    for line in response.split('\n'):
        line = line.strip()
        if line.startswith('Q:'):
            if current_question:
                if 'options' in current_question and 'correct' in current_question:
                    questions.append(current_question)
                current_question = {'question': line[2:].strip(), 'options': []}
        elif line.startswith(('A)', 'B)', 'C)', 'D)')):
            current_question['options'].append(line[3:].strip())
        elif line.startswith('Correct:'):
            current_question['correct'] = line.split(':')[1].strip()
        elif line.startswith('Explanation:'):
            current_question['explanation'] = line.split(':', 1)[1].strip()
    
    if current_question and 'options' in current_question and 'correct' in current_question:
        questions.append(current_question)
    
    # Validate and filter questions
    valid_questions = []
    for q in questions:
        if len(q['options']) == 4 and q['correct'] in 'ABCD' and len(q['correct']) == 1:
            valid_questions.append(q)
    
    return valid_questions

# Function to generate flashcards
def generate_flashcards(course, topics, api_key):
    prompt = f"""
    Create 5 flashcards for the following topics in {course}: {', '.join(topics)}. 
    Format each flashcard as:

    Front: [concept or question]
    Back: [explanation or answer]

    Ensure the flashcards cover key concepts and potential areas of confusion.
    """
    response = query_gemini_api(prompt, api_key)
    return parse_flashcards(response)

def parse_flashcards(response):
    flashcards = []
    lines = response.strip().split('\n')
    current_card = {}
    for line in lines:
        if line.startswith('Front:'):
            if current_card:
                flashcards.append(current_card)
            current_card = {'front': line[6:].strip()}
        elif line.startswith('Back:'):
            current_card['back'] = line[5:].strip()
    if current_card:
        flashcards.append(current_card)
    return flashcards

# Login page
def login_page():
    st.title("Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login", key="login_button"):
        if authenticate(username, password):
            st.session_state.user_authenticated = True
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid credentials")

# Main application
def main_app():
    st.title("Professional Course Study Plan")
    
    # Sidebar
    with st.sidebar:
        st.title("Menu")
        menu = st.radio("Select:", ["Home", "Courses", "Tests", "Flashcards"])
        
        if menu == "Courses":
            st.subheader("Your Courses")
            for course in st.session_state.conversations:
                if st.button(course, key=f"course_{course}"):
                    st.session_state.current_course = course
                    st.rerun()
            if st.button("+ New Course", key="new_course_button"):
                st.session_state.new_course = True
                st.rerun()
        
        elif menu == "Tests":
            st.subheader("Tests")
            for course in st.session_state.conversations:
                with st.expander(course):
                    for test in st.session_state.tests.get(course, []):
                        if st.button(f"Test {test['number']}", key=f"test_{course}_{test['number']}"):
                            st.session_state.current_test = (course, test['number'])
                            st.rerun()
                    if st.button("+ New Test", key=f"new_test_{course}"):
                        st.session_state.new_test = course
                        st.rerun()
        
        elif menu == "Flashcards":
            st.subheader("Flashcards")
            for course in st.session_state.flashcards:
                if st.button(f"{course} Flashcards", key=f"flashcards_{course}"):
                    st.session_state.current_flashcards = course
                    st.rerun()
    
    # Main content area
    if menu == "Home":
        display_home()
    elif menu == "Courses":
        if hasattr(st.session_state, 'new_course') and st.session_state.new_course:
            create_new_course()
        elif st.session_state.current_course:
            display_course_content(st.session_state.current_course)
    elif menu == "Tests":
        if hasattr(st.session_state, 'new_test'):
            create_new_test(st.session_state.new_test)
        elif hasattr(st.session_state, 'current_test'):
            display_test()
    elif menu == "Flashcards":
        if hasattr(st.session_state, 'current_flashcards'):
            display_flashcards()

def display_home():
    st.header("Welcome to Your Professional Course Study Plan")
    st.write("Here's an overview of your progress:")
    
    for course, course_data in st.session_state.conversations.items():
        progress = (course_data['current_day'] - 1) / course_data['max_day'] * 100
        st.write(f"**{course}:** Day {course_data['current_day']} of {course_data['max_day']}")
        st.progress(progress)
    
    st.write(f"Total Points: {st.session_state.user_points}")

def create_new_course():
    st.subheader("Create New Course")
    
    if not st.session_state.gemini_api_key:
        st.session_state.gemini_api_key = st.text_input("Enter your Gemini API key:", type="password", key="api_key_input")
        if st.session_state.gemini_api_key:
            genai.configure(api_key=st.session_state.gemini_api_key)
        else:
            st.warning("Please enter your Gemini API key to continue.")
            return
    
    all_courses = ["Artificial Intelligence and Machine Learning", "Computer Science Engineering", "MBA", "Data Science", "Cyber Security", "Digital Marketing", "Project Management", "Finance", "Healthcare Management", "Human Resource Management"]
    course = st.selectbox("Select a professional course:", [course for course in all_courses if course not in st.session_state.conversations], key="new_course_select")
    time_frame = st.number_input("Enter the course duration (days):", min_value=180, max_value=730, value=365, key="new_course_duration")
    level = st.selectbox("Select your level of study:", ["Beginner", "Intermediate", "Advanced"], key="new_course_level")
    
    if st.button("Generate Course", key="generate_course_button"):
        with st.spinner("Generating course content..."):
            try:
                study_plan = generate_study_plan_in_batches(course, time_frame, level, st.session_state.gemini_api_key)
                if study_plan:
                    session_data = {
                        "study_plan": study_plan,
                        "start_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                        "current_day": 1,
                        "max_day": time_frame,
                        "level": level
                    }
                    st.session_state.conversations[course] = session_data
                    save_session_data(course, session_data)
                    st.success(f"Course for {course} created successfully!")
                    st.session_state.new_course = False
                    st.session_state.current_course = course
                    st.rerun()
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

def display_course_content(course):
    if course not in st.session_state.conversations:
        st.error(f"No data found for course: {course}")
        return

    session_data = st.session_state.conversations[course]
    study_plan = session_data.get('study_plan', [])
    current_day = session_data.get('current_day', 1)
    max_day = session_data.get('max_day', len(study_plan))
    
    st.header(f"Course Content for {course}")
    st.write(f"Current Progress: Day {current_day} of {max_day}")
    
    if not study_plan:
        st.warning("No study plan available for this course.")
        return

    if 0 <= current_day - 1 < len(study_plan):
        topic = study_plan[current_day - 1]
        st.subheader(f"Day {current_day}: {topic}")
        
        if st.button("Explain Today's Topic", key="explain_topic_button"):
            with st.spinner("Generating explanation..."):
                try:
                    explanation = explain_topic(topic, course, st.session_state.gemini_api_key)
                    if explanation:
                        st.markdown(explanation)
                except Exception as e:
                    st.error(f"Error explaining topic: {str(e)}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous Day", key="prev_day_button", disabled=current_day <= 1):
                session_data['current_day'] = max(1, current_day - 1)
                save_session_data(course, session_data)
                st.rerun()
        with col2:
            if st.button("Next Day", key="next_day_button", disabled=current_day >= max_day):
                session_data['current_day'] = min(max_day, current_day + 1)
                save_session_data(course, session_data)
                st.rerun()
    else:
        st.warning("You've reached the end of the course content.")


def create_new_test(course):
    st.subheader(f"Create New Test for {course}")
    
    if course not in st.session_state.conversations:
        st.error(f"No data found for course: {course}")
        return

    session_data = st.session_state.conversations[course]
    current_day = session_data.get('current_day', 1)
    study_plan = session_data.get('study_plan', [])
    
    if not study_plan:
        st.error(f"No study plan found for {course}. Please recreate the course.")
        return

    # Retrieving recent topics based on current day
    recent_topics = study_plan[max(0, current_day-3):current_day]
    
    if len(recent_topics) < 3:
        st.warning("Not enough topics covered yet to create a test. Please progress further in the course.")
        return

    with st.spinner("Generating test questions..."):
        try:
            questions = generate_test_questions(course, recent_topics, st.session_state.gemini_api_key)
            if not questions:
                st.error("Failed to generate valid questions. Please try again.")
                return
            
            test_number = len(st.session_state.tests.get(course, [])) + 1
            new_test = {
                'number': test_number,
                'questions': questions,
                'user_answers': {},
                'score': 0
            }
            if course not in st.session_state.tests:
                st.session_state.tests[course] = []
            st.session_state.tests[course].append(new_test)
            st.success(f"Test {test_number} for {course} created successfully!")
            st.session_state.new_test = None
            st.session_state.current_test = (course, test_number)
            st.rerun()
        except Exception as e:
            st.error(f"An error occurred while creating the test: {str(e)}")
            st.write("Please try again. If the problem persists, contact support.")

def display_test():
    course, test_number = st.session_state.current_test
    test_data = next(test for test in st.session_state.tests[course] if test['number'] == test_number)
    
    st.subheader(f"{course} - Test {test_number}")
    
    if 'current_question' not in st.session_state:
        st.session_state.current_question = 0
    
    if st.session_state.current_question < len(test_data['questions']):
        question = test_data['questions'][st.session_state.current_question]
        st.write(f"Question {st.session_state.current_question + 1}: {question['question']}")
        
        user_answer = st.radio("Select your answer:", question['options'], key=f"q_{st.session_state.current_question}")
        
        if st.button("Submit Answer", key="submit_answer"):
            test_data['user_answers'][st.session_state.current_question] = user_answer
            correct_answer = question['options'][ord(question['correct']) - ord('A')]
            if user_answer == correct_answer:
                st.success("Correct!")
                test_data['score'] += 1
            else:
                st.error(f"Incorrect. The correct answer is: {correct_answer}")
            st.write(f"Explanation: {question['explanation']}")
            
            st.session_state.current_question += 1
            if st.session_state.current_question < len(test_data['questions']):
                st.rerun()
            else:
                st.success("Test completed!")
                st.write(f"Your score: {test_data['score']}/{len(test_data['questions'])}")
                
                incorrect_topics = [q['question'].split()[0] for i, q in enumerate(test_data['questions']) 
                                    if test_data['user_answers'].get(i) != question['options'][ord(question['correct']) - ord('A')]]
                
                if incorrect_topics:
                    st.write("Topics to review:")
                    st.write(", ".join(set(incorrect_topics)))
                    
                    if st.button("Generate Flashcards for Review", key="generate_flashcards"):
                        generate_review_flashcards(course, list(set(incorrect_topics)))
                
                if st.button("Retake Test", key="retake_test"):
                    test_data['user_answers'] = {}
                    test_data['score'] = 0
                    st.session_state.current_question = 0
                    st.rerun()
    else:
        st.write("Test completed. You can retake the test or go back to the course content.")

def generate_review_flashcards(course, topics):
    with st.spinner("Generating flashcards..."):
        try:
            flashcards = generate_flashcards(course, topics, st.session_state.gemini_api_key)
            if course not in st.session_state.flashcards:
                st.session_state.flashcards[course] = []
            st.session_state.flashcards[course].extend(flashcards)
            st.success("Flashcards generated successfully!")
            st.session_state.current_flashcards = course
            st.rerun()
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

def display_flashcards():
    course = st.session_state.current_flashcards
    flashcards = st.session_state.flashcards[course]
    
    st.subheader(f"Flashcards for {course}")
    
    if 'current_card' not in st.session_state:
        st.session_state.current_card = 0
    
    if flashcards:
        card = flashcards[st.session_state.current_card]
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("Front:")
            st.write(card['front'])
        with col2:
            if st.button("Reveal Answer", key="reveal_answer"):
                st.write("Back:")
                st.write(card['back'])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Previous Card", key="prev_card", disabled=st.session_state.current_card <= 0):
                st.session_state.current_card -= 1
                st.rerun()
        with col2:
            if st.button("Next Card", key="next_card", disabled=st.session_state.current_card >= len(flashcards) - 1):
                st.session_state.current_card += 1
                st.rerun()
        with col3:
            if st.button("Shuffle", key="shuffle_cards"):
                random.shuffle(flashcards)
                st.session_state.current_card = 0
                st.rerun()
    else:
        st.write("No flashcards available for this course.")

# User progress tracking
def update_user_progress(course, day_completed):
    if 'progress' not in st.session_state:
        st.session_state.progress = {}
    if course not in st.session_state.progress:
        st.session_state.progress[course] = set()
    st.session_state.progress[course].add(day_completed)
    save_progress(course)

def save_progress(course):
    progress_file = f"{course}_progress.json"
    with open(progress_file, 'w') as f:
        json.dump(list(st.session_state.progress[course]), f)

def load_progress(course):
    progress_file = f"{course}_progress.json"
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            return set(json.load(f))
    return set()

# Gamification elements
def award_points(points):
    st.session_state.user_points += points
    st.success(f"You earned {points} points!")

def display_achievements():
    st.sidebar.write(f"Total Points: {st.session_state.user_points}")
    
    achievements = [
        ("Beginner", 100, "Started your learning journey"),
        ("Intermediate", 500, "Making good progress"),
        ("Advanced", 1000, "Becoming an expert"),
        ("Master", 5000, "True mastery achieved")
    ]
    
    for title, points, description in achievements:
        if st.session_state.user_points >= points:
            st.sidebar.write(f"🏆 {title}: {description}")

# Main execution
if __name__ == "__main__":
    if not st.session_state.user_authenticated:
        login_page()
    else:
        main_app()
        display_achievements()

# Logout functionality
if st.sidebar.button("Logout", key="logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# Error handling and graceful degradation
try:
    # Your main application logic here
    pass
except Exception as e:
    st.error(f"An unexpected error occurred: {str(e)}")
    st.write("Please try refreshing the page or contact support if the issue persists.")

# Performance optimization
@st.cache_data
def load_course_data(course):
    # Load and cache course-specific data
    pass

# Accessibility features
st.markdown("""
<style>
    body {
        font-family: Arial, sans-serif;
        line-height: 1.6;
    }
    .stButton>button {
        font-size: 16px;
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)

