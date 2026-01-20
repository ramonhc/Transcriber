import whisperx
import gc
import torch
import os
import glob
import shutil
import argparse
from dotenv import load_dotenv
import os

load_dotenv()
"""
you can run your script in two ways:
python TranscriberAuto.py (it will use the default language en)
python TranscriberAuto.py sp (it will use the specified language sp)
it also automatically provides a helpful usage message if you run python TranscriberAuto.py -h.
"""
# --- Configuration ---
# 1. Enter your Hugging Face access token
hf_token = os.getenv("HF_TOKEN")
# 2. Specify the language of the audio
#language_code = "en"

# 2. Use argparse to handle language parameter
parser = argparse.ArgumentParser(description="Transcribe audio files with WhisperX.")
parser.add_argument('language', nargs='?', default='en', help="The language code for transcription (e.g., 'es', 'fr', 'sp'). Defaults to 'en'.")
args = parser.parse_args()
language_code = args.language
print(f"Using language: {language_code}")

# --- System Setup ---
device = "cuda" if torch.cuda.is_available() else "cpu"
compute_type = "float16" if device == "cuda" else "float32"
model_size = "large-v3"
print(f"Using device: {device}, compute type: {compute_type}, model size: {model_size}")

# Optional: Enable TF32 for a performance boost on modern GPUs
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# --- Main Processing Logic ---
# Create a "done" folder if it doesn't exist
done_folder = "done"
os.makedirs(done_folder, exist_ok=True)

# Find all .mp3 files in the current directory
audio_files = glob.glob("*.mp3")
print(f"\nFound {len(audio_files)} MP3 file(s) to process.")

if not audio_files:
    print("No .mp3 files found in the current folder. Exiting.")
else:
    # Load all models once before the loop
    print("\nLoading all models once...")
    model = whisperx.load_model(model_size, device, compute_type=compute_type)
    model_a, metadata = whisperx.load_align_model(language_code=language_code, device=device)
    diarize_model = whisperx.diarize.DiarizationPipeline(use_auth_token=hf_token, device=device)
    print("All models loaded.")

    # Loop through each audio file
    for audio_file in audio_files:
        print(f"\n==================================================")
        print(f"Processing file: {audio_file}")
        print(f"==================================================")
        
        # Initialize result to None
        result = None
    
        try:
            # 1. Transcribe with Whisper
            print("\nStep 1: Transcribing audio...")
            batch_size = 4 # Reduce if you run out of VRAM
            audio = whisperx.load_audio(audio_file)
            result = model.transcribe(audio, batch_size=batch_size, language=language_code)
            print("Transcription complete.")

            # 2. Align Whisper output
            print("\nStep 2: Aligning transcription...")
            result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
            print("Alignment complete.")

            # 3. Perform Speaker Diarization
            print("\nStep 3: Performing speaker diarization...")
            diarize_segments = diarize_model(audio)
            result = whisperx.assign_word_speakers(diarize_segments, result)
            print("Diarization complete.")

            # 4. Write the result to a text file
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
                    formatted_line = f"[{start_str} -> {end_str}] {speaker}:{text.strip()}\n"
                    f.write(formatted_line)
                    print(formatted_line, end="")

            # Move the processed file
            print(f"\n--- Moving processed file to '{done_folder}' folder ---")
            shutil.move(audio_file, os.path.join(done_folder, os.path.basename(audio_file)))
            print(f"Successfully moved {audio_file}.")

        except Exception as e:
            print(f"\n--- An error occurred while processing {audio_file}: {e} ---")
            print(f"Skipping this file and moving to the next one.")
            continue # Move to the next file in the list
        finally:
            # Clean up memory after each file
            del audio
            if result is not None:
                del result
            gc.collect()
            torch.cuda.empty_cache()

    print("\nAll files have been processed.")