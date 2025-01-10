import streamlit as st
import os
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
import io
import os
from google.cloud import speech
import google.generativeai as genai
import re
key = st.secrets["key"]
import imageio
def convert_mp4_to_flac(mp4_file, flac_file):
    # Load the video file
    video = VideoFileClip(mp4_file)

    # Save the audio in WAV format temporarily
    temp_wav = "temp_audio.wav"
    video.audio.write_audiofile(temp_wav, codec='pcm_s16le')

    # Load the temporary WAV file and convert it to FLAC
    audio = AudioSegment.from_wav(temp_wav)
    audio.export(flac_file, format="flac")
from google.cloud import storage

def upload_blob(bucket_name, source_file_name, destination_blob_name, generation_match_precondition = 0):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    generation_match_precondition = 0

    blob.upload_from_filename(source_file_name, if_generation_match=generation_match_precondition)

    print(
        f"File {source_file_name} uploaded to {destination_blob_name}."
    )

def transcribe_gcs(gcs_uri, dialect):
    client = speech.SpeechClient()

    audio = speech.RecognitionAudio(uri=gcs_uri)
    config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
                enable_automatic_punctuation=True,
                audio_channel_count=2,
                language_code=dialect,
            )
    operation = client.long_running_recognize(config=config, audio=audio)
    print("Waiting for operation to complete...")
    response = operation.result(timeout=None)
    transcript_builder = []
    for result in response.results:
      transcript_builder.append(f"\nTranscript: {result.alternatives[0].transcript}")
    transcript = "".join(transcript_builder)
    filename = os.path.basename(gcs_uri).split('.')[0] + '.txt'
    with open(filename, 'w', encoding='utf-8') as f:
       f.write(transcript)
       print(f"Transcript saved to {filename}")
    return transcript

def feedback_tutor(transcript_file):
  genai.configure(api_key= key)
  model = genai.GenerativeModel('models/gemini-1.5-flash')
  # Extract metadata from the filename

  with open(transcript_file, 'r', encoding='utf-8') as file:
    transcript = file.read()
  response = model.generate_content([
    """You are an expert in providing feedback for AlGooru, a learning organization. Your task is to give thoughtful, human-centered feedback to tutors based on their transcripts from online classes. These classes involve one tutor and one student. While tutors should aim to follow the AlGooru session outline (introduction, ice-breakers, interactive explanations, fun and engaging activities, closure, and next session planning), remember that human variability in teaching styles should be considered. Be constructive but also recognize the positive efforts tutors put into their sessions. Give balanced feedback, and be lenient when scoring minor imperfections. Always highlight areas of strength and where improvements can be made, but avoid being overly harsh for small deviations from the outline.

For scoring (1-3), consider the following parameters:

1. **Session Introduction**
2. **Session Structure**
3. **Time Management**
4. **Teaching & Explanation**
5. **Student Interaction & Engagement**
6. **Feedback & Encouragement**
7. **Session Closure**

Scoring Guidelines (1-3):

1. **Session Introduction**:
   (a) 1 = The tutor jumped right into the lesson without any introduction or objectives.
   (b) 2 = The tutor gave an introduction but could have been more engaging or clear.
   (c) 3 = The tutor offered a warm greeting, explained the session objectives, and created a welcoming atmosphere.

2. **Session Structure**:
   (a) 1 = The session was disorganized, with no clear flow, and the AlGooru outline was not followed.
   (b) 2 = The session had some structure but could improve transitions and organization.
   (c) 3 = The session was well-structured, following the AlGooru outline, and maintained a logical flow.

3. **Time Management**:
   (a) 1 = The tutor struggled with time, leading to incomplete activities or rushed content.
   (b) 2 = The tutor managed time well but could improve pacing or transitions.
   (c) 3 = The tutor managed time effectively, covering all planned activities at a comfortable pace.

4. **Teaching & Explanation**:
   (a) 1 = The tutor dominated the conversation without much student interaction.
   (b) 2 = The tutor encouraged student involvement but could be more patient or student-centered.
   (c) 3 = The tutor balanced explanations and student participation, fostering a positive, student-centered environment.

5. **Student Interaction & Engagement**:
   (a) 1 = The student had minimal participation, with the tutor doing most of the talking.
   (b) 2 = There was interaction, but the student didn't get enough time to ask questions or think independently.
   (c) 3 = The student had ample opportunities to engage and ask questions, with sufficient time to respond.

6. **Feedback & Encouragement**:
   (a) 1 = The tutor offered little encouragement or corrective feedback.
   (b) 2 = The tutor was friendly but could have been more encouraging and specific in feedback.
   (c) 3 = The tutor provided positive feedback, encouragement, and constructive corrections.

7. **Session Closure**:
   (a) 1 = The session ended abruptly without summarizing key points or follow-up plans.
   (b) 2 = The session closure was positive but lacked clarity or completeness in reviewing objectives.
   (c) 3 = The tutor concluded the session with a clear summary, key points review, and an effective plan for the next session.

Remember, the aim is to provide feedback that reflects both strengths and areas of improvement while being mindful of the tutor’s efforts. When scoring, lean towards more lenient assessments if the tutor made reasonable efforts to engage the student, even if there were some minor issues.

Please analyze the transcript, provide scores, and include actionable feedback with possible solutions for improvement, ensuring the tone is supportive and constructive."""
    f"Transcript: {transcript}"

]) # ! add total score

  return response.text


def web_app(mp4file,dialect):
  base_name = os.path.splitext(mp4file)[0]
  gcs_uri = 'gs://eqa_1/' + base_name + '.flac'
  flac_file = os.path.join(base_name + '.flac')
  txt_file = os.path.basename(gcs_uri).split('.')[0] + '.txt'
  os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "arabic_stt.json"
  try:
    convert_mp4_to_flac(mp4file, flac_file)
    upload_blob('eqa_1', flac_file, base_name + '.flac')
    transcript = transcribe_gcs(gcs_uri, dialect)
  except:
    transcript = transcribe_gcs(gcs_uri, dialect)
  return feedback_tutor( txt_file)




def main():
    st.title("Tutor Feedback Generator")

    st.write("Upload an MP4 file and specify the dialect to get tutor feedback.")

    # File upload widget
    uploaded_file = st.file_uploader("Upload your MP4 file", type=["mp4"])

    # Text input for dialect
    dialect = st.text_input("Enter the dialect (e.g., en-US, ar-SA):")

    if uploaded_file and dialect:
        # Save the uploaded file locally
        with open(uploaded_file.name, "wb") as f:
            f.write(uploaded_file.getbuffer())

        st.write("File uploaded successfully.")
        
        try:
            # Call the web_app function
            feedback = web_app(uploaded_file.name, dialect)

            # Display the generated feedback
            st.subheader("Generated Feedback")
            st.markdown("Feedback", feedback, height=300)

        except Exception as e:
            st.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()

