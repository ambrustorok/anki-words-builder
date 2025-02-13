import numpy as np
import pydub
import tempfile


def string_to_html_div(input_string):
    if not isinstance(input_string, str):
        raise ValueError("Input must be a string")

    # Replace newlines with <br> tags
    html_content = input_string.replace("\n", "<br>")

    # Wrap the content in a div
    html_div = f"<div>{html_content}</div>"

    return html_div


def convert_string_to_html(raw_string):
    # Convert special HTML characters to their escape sequences
    escaped_string = (
        raw_string.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )

    # Replace newline characters with <br> tags
    html_string = escaped_string.replace("\n", "<br>\n")

    # Wrap the escaped string in a <div> tag
    html_output = f"<div>{html_string}</div>"

    return html_output


def get_read_aloud_text(lang):
    texts = {
        "danish": "Læs dette på dansk",
    }
    return texts[lang.lower()]

def convert_audio_to_numpy(audio_bytes):
    if audio_bytes is None:
        return None
        
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as temp_file:
        temp_file.write(audio_bytes)
        temp_file.flush()
        
        # Convert MP3 file to NumPy array, ensuring correct sample rate and mono
        audio = pydub.AudioSegment.from_file(temp_file.name, format="mp3").set_frame_rate(44100).set_channels(1)
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        if audio.channels > 1:
            samples = samples.reshape((-1, audio.channels)).mean(axis=1)  # Convert stereo to mono
        samples /= np.iinfo(np.int16).max  # Normalize to range [-1, 1]
    
    return samples  # Return just the samples, as rate is fixed at 44100