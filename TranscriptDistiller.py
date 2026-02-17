
import os
import shutil
import glob
from llmlingua import PromptCompressor

# --- Configuration ---
SOURCE_DIR = "done txt"
DISTILLED_DIR = "DistilledTxt"
ORIGINAL_DIR = "OriginalTxt"
COMPRESSION_RATE = 0.9
MODEL_NAME = "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"

def setup_directories():
    """Creates the necessary directories if they don't exist."""
    os.makedirs(DISTILLED_DIR, exist_ok=True)
    os.makedirs(ORIGINAL_DIR, exist_ok=True)
    print(f"Ensured directories exist: '{DISTILLED_DIR}' and '{ORIGINAL_DIR}'")

def extract_metadata(filename):
    """
    Extracts Date and Meeting Name from the filename.
    Format: YYYY-MM-DD <Meeting Name>_transcription.txt
    
    Returns:
        date_str (str): The extracted date.
        meeting_name (str): The extracted meeting name.
    """
    # Remove extension
    base_name = os.path.splitext(filename)[0]
    
    # Check if it has the suffix (it should based on requirements)
    if base_name.endswith("_transcription"):
        content_part = base_name[:-len("_transcription")]
    else:
        content_part = base_name
        
    # Extract data - usually the first 10 chars are the date "YYYY-MM-DD"
    # We assume the user follows the pattern strictly as described
    if len(content_part) > 10 and content_part[10] == ' ':
         date_str = content_part[:10]
         meeting_name = content_part[11:].strip()
    else:
        # Fallback if pattern doesn't match exactly
        date_str = "Unknown Date"
        meeting_name = content_part.strip()
        
    return date_str, meeting_name

def process_files():
    """
    Scans SOURCE_DIR, compresses, adds metadata, and moves files.
    """
    files = glob.glob(os.path.join(SOURCE_DIR, "*.txt"))
    
    if not files:
        print(f"No .txt files found in '{SOURCE_DIR}' to process.")
        return

    print(f"Found {len(files)} files to process in '{SOURCE_DIR}'...")
    
    # Initialize the compressor
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading model: {MODEL_NAME} on {device}...")
    compressor = PromptCompressor(
        model_name=MODEL_NAME, 
        use_llmlingua2=True,
        device_map=device
    )
    print("Model loaded.")

    import re
    # Timestamp pattern: [HH:MM:SS.mm -> HH:MM:SS.mm]
    timestamp_pattern = re.compile(r'^\[\d{2}:\d{2}:\d{2}\.\d{2}\s*->\s*\d{2}:\d{2}:\d{2}\.\d{2}\]\s*')

    for file_path in files:
        filename = os.path.basename(file_path)
        
        # Skip if it's already a distilled file (just in case)
        if "_Distilled.txt" in filename:
            print(f"Skipping already distilled file: {filename}")
            continue

        print(f"\nProcessing: {filename}")
        
        try:
            # 1. Read content
            with open(file_path, "r", encoding="utf-8") as f:
                raw_text = f.read()
            
            # 2. Extract Metadata
            date_str, meeting_name = extract_metadata(filename)
            print(f"  > Date: {date_str}, Meeting: {meeting_name}")

            # 3. Clean Text and Identify Speakers
            cleaned_lines = []
            speakers = set()
            
            for line in raw_text.splitlines():
                # Remove timestamp
                line_clean = timestamp_pattern.sub('', line)
                
                # Identify speaker (Start of line until first ":")
                # We assume if the line starts with text ending in :, it's a speaker or label
                # We want to preserve it.
                match = re.match(r'^([^:]+?:)', line_clean)
                if match:
                    speakers.add(match.group(1))
                
                cleaned_lines.append(line_clean)
            
            cleaned_text = "\n".join(cleaned_lines)
            
            # 4. Compress
            print("  > Compressing...")
            # 'rate' means we keep only that percentage of tokens
            # We add identified speakers to force_tokens to preserve them
            force_tokens = ['\n', '.', '!', '?', ','] + list(speakers)
            
            compression_results = compressor.compress_prompt(
                cleaned_text, 
                rate=COMPRESSION_RATE, 
                force_tokens=force_tokens
            )
            distilled_text = compression_results['compressed_prompt']
            
            # 5. Preparing Output Content
            final_content = f"Meeting Name: {meeting_name}\nDate: {date_str}\n\n{distilled_text}"
            
            # 6. Write to Distilled File
            # New name: <Date> <Meeting Name>_Distilled.txt
            # Essentially replacing "_transcription" with "_Distilled" in the original base name
            # But the user also said "extract meeting name... rule is remove date and suffix" 
            # and then "new distilled file... remove _transcription suffix, replaced with _Distilled"
            # So "2025-10-14 HPEFS..._transcription.txt" -> "2025-10-14 HPEFS..._Distilled.txt"
            
            new_filename = filename.replace("_transcription.txt", "_Distilled.txt")
            if new_filename == filename: # If replacement didn't happen (suffix missing)
                 new_filename = os.path.splitext(filename)[0] + "_Distilled.txt"
                 
            distilled_path = os.path.join(DISTILLED_DIR, new_filename)
            
            with open(distilled_path, "w", encoding="utf-8") as f:
                f.write(final_content)
            print(f"  > Saved distilled version to: {distilled_path}")
            
            # 6. Move Original File
            original_dest_path = os.path.join(ORIGINAL_DIR, filename)
            shutil.move(file_path, original_dest_path)
            print(f"  > Moved original to: {original_dest_path}")

        except Exception as e:
            print(f"  > ERROR processing {filename}: {e}")

if __name__ == "__main__":
    setup_directories()
    process_files()
