import whisperx
import gc
import torch
import os # Import the os module to handle file paths
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
# 1. Enter the path to your audio file
audio_file = r"C:\work\Transcriber\2025-08-20 Kristtel 121.mp3"
# 2. Enter your Hugging Face access token
hf_token = os.getenv("HF_TOKEN")
# 3. Specify the language of the audio
language_code = "es" # "en" for English, "es" for Spanish, "fr" for French, etc.

# --- System Setup ---
device = "cuda" if torch.cuda.is_available() else "cpu"
compute_type = "float16" if device == "cuda" else "float32"
model_size = "large-v3"
print(f"Using device: {device}, compute type: {compute_type}, model size: {model_size}")

# --- The Pipeline ---
# 1. Transcribe with Whisper
print("\nStep 1: Transcribing audio...")
# Reduce batch_size if you run out of VRAM on your GPU
batch_size = 4
model = whisperx.load_model(model_size, device, compute_type=compute_type)
audio = whisperx.load_audio(audio_file)

# Transcribe with the specified language
result = model.transcribe(audio, batch_size=batch_size, language=language_code)

del model; gc.collect(); torch.cuda.empty_cache()
print("Transcription complete.")

# 2. Align Whisper output
print("\nStep 2: Aligning transcription...")
# The language_code is now taken from our config variable
model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
del model_a; gc.collect(); torch.cuda.empty_cache()
print("Alignment complete.")

# 3. Perform Speaker Diarization
print("\nStep 3: Performing speaker diarization...")
diarize_model = whisperx.diarize.DiarizationPipeline(use_auth_token=hf_token, device=device)
diarize_segments = diarize_model(audio)
result = whisperx.assign_word_speakers(diarize_segments, result)
print("Diarization complete.")

# 4. Write the result to a text file and print to console
# Create the output filename by taking the base name of the audio file
base_name, _ = os.path.splitext(os.path.basename(audio_file))
output_file = f"{base_name}_transcription.txt"

print(f"\n--- Writing transcription to {output_file} ---")
with open(output_file, "w", encoding="utf-8") as f:
    for segment in result["segments"]:
        speaker = segment.get('speaker', 'UNKNOWN')
        text = segment['text']
        start_time = segment['start']
        end_time = segment['end']
        
        start_str = f"{int(start_time // 3600):02}:{int((start_time % 3600) // 60):02}:{start_time % 60:05.2f}"
        end_str = f"{int(end_time // 3600):02}:{int((end_time % 3600) // 60):02}:{end_time % 60:05.2f}"
        
        # Format the line to be written to the file and printed
        formatted_line = f"[{start_str} -> {end_str}] {speaker}:{text.strip()}\n"
        
        f.write(formatted_line)
        print(formatted_line, end="")

print(f"\n--- Transcription complete. Output saved to {output_file} ---")